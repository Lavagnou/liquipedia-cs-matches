"""Platform for sensor integration."""
from datetime import datetime, timedelta
import logging
import re

import requests
import voluptuous as vol
from bs4 import BeautifulSoup
from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv
from lxml import html

from .const import CONF_PAGE, CONF_TEAMS, DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

# Table de correspondance fuseau horaire
_TZ_OFFSETS = {
    "UTC": 0, "PST": -8, "PDT": -7, "MST": -7, "MDT": -6, 
    "CST": -6, "CDT": -5, "EST": -5, "EDT": -4, "CET": +1, 
    "CEST": +2, "BST": +1, "MSK": +3, "KST": +9, "JST": +9, "AST": +3
}

# Cache des données
_TEAM_DATA_CACHE = {}
_LAST_FETCH = {}

# Configuration du composant
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_TEAMS): vol.All(
            cv.ensure_list,
            [
                vol.Schema(
                    {
                        vol.Required(CONF_PAGE): cv.string,
                        vol.Required(CONF_NAME): cv.string,
                    }
                )
            ],
        ),
    }
)

def setup_platform(hass, config, add_entities, discovery_info=None):
    """Configurer la plateforme du capteur Liquipedia CS Matches."""
    # Récupérer les équipes configurées
    teams_config = config.get(CONF_TEAMS, [])
    entities = []
    for team_config in teams_config:
        name = team_config.get(CONF_NAME)
        page = team_config.get(CONF_PAGE)
        
        # Créer les capteurs pour chaque équipe (prochain match et dernier match)
        next_match_sensor = LiquipediaCsMatchSensor(hass, page, name, "next")
        last_match_sensor = LiquipediaCsMatchSensor(hass, page, name, "last")
        entities.append(next_match_sensor)
        entities.append(last_match_sensor)
        
        # Ajouter l'entité à la liste globale pour le bouton de mise à jour
        if DOMAIN not in hass.data:
            hass.data[DOMAIN] = {}
        if "entities" not in hass.data[DOMAIN]:
            hass.data[DOMAIN]["entities"] = []
            
        hass.data[DOMAIN]["entities"].append(next_match_sensor)
        hass.data[DOMAIN]["entities"].append(last_match_sensor)
    
    # Ajouter toutes les entités à Home Assistant
    if entities:
        add_entities(entities, True)
        _LOGGER.info(f"Ajout de {len(entities)} capteur(s) Liquipedia CS")
    else:
        _LOGGER.warning("Aucune équipe configurée pour Liquipedia CS")

def fetch_team_data(hass, team_page, team_name):
    """Récupère les données pour une équipe depuis Liquipedia."""
    now = datetime.now()
    
    # Vérifier le cache
    if team_page in _TEAM_DATA_CACHE and team_page in _LAST_FETCH:
        if now - _LAST_FETCH[team_page] < SCAN_INTERVAL:
            _LOGGER.debug(f"Utilisation des données en cache pour {team_name}")
            return _TEAM_DATA_CACHE[team_page]
    
    _LOGGER.info(f"Récupération des données pour {team_name} depuis Liquipedia")
    
    # Initialiser les données
    data = {"next": {}, "last": {}}
    
    try:        # Récupérer la page de l'équipe
        team_url = f"https://liquipedia.net/counterstrike/{team_page}/Matches"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; HomeAssistant/2023.2)"}
        
        try:
            response = requests.get(team_url, headers=headers, timeout=10)
            response.raise_for_status()
            _LOGGER.debug(f"Page équipe récupérée avec succès: {team_url}")
        except requests.exceptions.RequestException as e:
            _LOGGER.error(f"Erreur lors de la récupération de la page équipe {team_url}: {e}")
            if team_page in _TEAM_DATA_CACHE:
                return _TEAM_DATA_CACHE[team_page]
            return data
        
        # Analyser avec BeautifulSoup
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Trouver le dernier match
        tables = soup.find_all("table", class_="infobox_matches_content")
        if tables:
            last_match_table = tables[0]
            rows = last_match_table.find_all("tr")
            if len(rows) > 1:  # Ignorer l'en-tête
                last_match_row = rows[1]
                cells = last_match_row.find_all("td")
                
                if len(cells) >= 6:
                    # Extraire les données
                    date_str = cells[0].get_text(strip=True)
                    event_name = cells[5].get_text(strip=True) if len(cells) > 5 else "Unknown"
                    
                    # Score et format
                    score_cell = cells[6] if len(cells) > 6 else None
                    score_text = score_cell.get_text(strip=True) if score_cell else "0:0"
                    
                    # Calculer le format à partir du score
                    format_text = "Bo3"  # Valeur par défaut
                    if ":" in score_text:
                        parts = score_text.split(":")
                        if len(parts) == 2:
                            try:
                                team_score = int(parts[0])
                                opp_score = int(parts[1])
                                max_score = max(team_score, opp_score)
                                if max_score <= 1:
                                    format_text = "Bo1"
                                elif max_score == 2:
                                    format_text = "Bo3"
                                elif max_score == 3:
                                    format_text = "Bo5"
                                elif max_score == 4:
                                    format_text = "Bo7"
                            except ValueError:
                                pass
                    
                    # Adversaire
                    opp_cell = cells[7] if len(cells) > 7 else None
                    opp_name = opp_cell.get_text(strip=True) if opp_cell else "Unknown"
                    
                    # Construire les données
                    data["last"]["match"] = f"{team_name} vs {opp_name}"
                    data["last"]["format"] = format_text
                    data["last"]["date"] = date_str
                    data["last"]["event"] = event_name
                    data["last"]["score"] = f"{team_name} {score_text} {opp_name}"
        
        # Récupérer le prochain match
        central_url = "https://liquipedia.net/counterstrike/Liquipedia:Matches"
        central_soup = None
        try:
            central_response = requests.get(central_url, headers=headers, timeout=10)
            central_response.raise_for_status()
            central_soup = BeautifulSoup(central_response.text, "html.parser")
            _LOGGER.debug(f"Page centrale des matchs récupérée avec succès")
        except requests.exceptions.RequestException as e:
            _LOGGER.error(f"Erreur lors de la récupération de la page centrale {central_url}: {e}")
        
        # Chercher l'équipe dans la liste des matchs à venir
        team_link = None
        for a in central_soup.find_all("a"):
            if a.get("href") == f"/counterstrike/{team_page}":
                team_link = a
                break
    
        if team_link:
            # Trouver la ligne du match
            match_row = team_link.find_parent("tr")
            if match_row:
                # Identifier la position de l'équipe (gauche/droite)
                team_cell = team_link.find_parent("td")
                is_left = team_cell and "team-left" in team_cell.get("class", [])
                
                # Trouver l'adversaire
                if is_left:
                    opp_cell = match_row.find("td", class_="team-right")
                else:
                    opp_cell = match_row.find("td", class_="team-left")
                
                opp_name = opp_cell.get_text(strip=True) if opp_cell else "Unknown"
                
                # Format du match
                vs_cell = match_row.find("td", class_="versus")
                format_text = "Bo3"  # Par défaut
                
                if vs_cell:
                    abbr = vs_cell.find("abbr")
                    if abbr:
                        format_text = abbr.get_text(strip=True)
                
                # Chercher les détails (date et tournoi)
                details_row = match_row.find_next_sibling("tr")
                date_str = "TBD"
                event_name = "Unknown"
                
                if details_row:
                    # Date/heure
                    timer_span = details_row.find("span", class_="timer-object")
                    if timer_span:
                        date_str = timer_span.get_text(strip=True)
                    
                    # Tournoi
                    event_div = details_row.find("div", class_="text-nowrap")
                    if event_div:
                        event_name = event_div.get_text(strip=True)
                
                # Remplir les données du prochain match
                data["next"]["match"] = f"{team_name} vs {opp_name}"
                data["next"]["format"] = format_text
                data["next"]["date"] = date_str
                data["next"]["event"] = event_name
        else:
            # Pas de match à venir trouvé
            data["next"]["match"] = "No upcoming match"
            data["next"]["format"] = None
            data["next"]["date"] = None
            data["next"]["event"] = None
    
    except Exception as err:
        _LOGGER.error("Error fetching data for %s: %s", team_name, err)
        if team_page in _TEAM_DATA_CACHE:
            return _TEAM_DATA_CACHE[team_page]
    
    # Mettre à jour le cache
    _TEAM_DATA_CACHE[team_page] = data
    _LAST_FETCH[team_page] = now
    
    return data

class LiquipediaCsMatchSensor(SensorEntity):
    """Représentation d'un capteur de match Liquipedia CS."""
    
    def __init__(self, hass, team_page, team_name, match_type):
        """Initialiser le capteur."""
        self.hass = hass
        self._team_page = team_page
        self._team_name = team_name
        self._match_type = match_type  # "next" ou "last"
        self._state = None
        self._attributes = {}
        
        # Définir l'ID unique et le nom
        key = team_name.lower().replace(" ", "_")
        self._attr_unique_id = f"liquipedia_cs_{key}_{match_type}"
        self._attr_name = f"Liquipedia CS {team_name} {match_type} match"
        
        # Icône selon le type
        self._attr_icon = "mdi:calendar-clock" if match_type == "next" else "mdi:trophy"
    
    @property
    def state(self):
        """Retourner l'état du capteur."""
        return self._state
    
    @property
    def extra_state_attributes(self):
        """Retourner les attributs du capteur."""
        return self._attributes
    
    def update(self):
        """Mettre à jour le capteur."""
        try:
            # Récupérer les données depuis Liquipedia
            data = fetch_team_data(self.hass, self._team_page, self._team_name)
            
            if self._match_type in data:
                match_data = data[self._match_type]
                
                # Mettre à jour l'état et les attributs
                self._state = match_data.get("match")
                
                self._attributes = {
                    "match": match_data.get("match"),
                    "format": match_data.get("format"),
                    "date": match_data.get("date"),
                    "event": match_data.get("event")
                }
                
                # Ajouter le score pour les matchs passés
                if self._match_type == "last" and "score" in match_data:
                    self._attributes["score"] = match_data["score"]
            else:
                self._state = None
                self._attributes = {}
                
        except Exception as err:
            _LOGGER.error("Error updating sensor %s: %s", self._attr_name, err)
