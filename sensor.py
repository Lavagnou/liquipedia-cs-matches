from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

# Constants et configuration
_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(hours=1)  # Fréquence de mise à jour automatique (modifiable facilement)

# Mapping page Liquipedia -> nom court de l'équipe
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required("teams"): vol.All([
        {
            vol.Required("page"): cv.string,
            vol.Required("name"): cv.string
        }
    ])
})


# Cache des données pour limiter les requêtes
_TEAM_DATA_CACHE: dict[str, dict] = {}
_LAST_FETCH: dict[str, datetime] = {}
# Cache pour la page centrale Liquipedia:Matches (prochains matchs)
_CENTRAL_RESULTS: dict[str, dict] = {}
_LAST_CENTRAL_FETCH: datetime | None = None

# Table de correspondance fuseau horaire (abréviation -> offset heure par rapport à UTC)
_TZ_OFFSETS = {
    "UTC": 0,
    "PST": -8, "PDT": -7,
    "MST": -7, "MDT": -6,
    "CST": -6, "CDT": -5,
    "EST": -5, "EDT": -4,
    "CET": +1, "CEST": +2,
    "BST": +1,
    "MSK": +3,
    "KST": +9, "JST": +9,
    "AST": +3  # AST ici supposé être Arabia Standard Time (UTC+3)
}

def fetch_team_data(team_page: str, hass) -> dict:
    """Récupère et analyse les données Liquipedia pour l'équipe donnée (dernier et prochain match)."""
    now = datetime.utcnow()
    team_name = TEAM_PAGES.get(team_page, team_page.replace("_", " "))
    # Utilisation du cache pour éviter les requêtes trop fréquentes
    if team_page in _TEAM_DATA_CACHE and team_page in _LAST_FETCH:
        if now - _LAST_FETCH[team_page] < SCAN_INTERVAL:
            return _TEAM_DATA_CACHE[team_page]

    # Initialisation du dictionnaire de résultat
    data: dict[str, dict] = {"next": {}, "last": {}}

    # 1. Récupération de la page "Matches" de l'équipe pour le dernier match
    team_url = f"https://liquipedia.net/counterstrike/{team_page}/Matches"
    _LOGGER.debug("Fetching Liquipedia team matches page for %s", team_page)
    try:
        resp = requests.get(team_url, timeout=10)
        resp.raise_for_status()
    except Exception as err:
        _LOGGER.error("Error fetching data for %s: %s", team_page, err)
        # En cas d’erreur réseau, on retourne les données en cache si disponibles, sinon dictionnaire vide
        return _TEAM_DATA_CACHE.get(team_page, {})

    soup_team = BeautifulSoup(resp.text, "lxml")  # utilisation de lxml pour plus de robustesse
    team_short = TEAM_PAGES.get(team_page, team_page.replace("_", " "))
    if team_short.startswith("Team "):
        team_short = team_short[5:]  # Retire le préfixe "Team " si présent (ex: "Team Liquid")

    # ** Dernier match (last_match) **
    last_match_row = None
    # On trouve la table des matchs récents via l'en-tête "Score"
    for table in soup_team.find_all("table"):
        headers = [th.get_text() for th in table.find_all("th")]
        if any("Score" in header for header in headers):
            rows = table.find_all("tr")
            if len(rows) > 1:
                last_match_row = rows[1]  # première ligne de données (après l'entête)
            break

    if last_match_row:
        cells = last_match_row.find_all("td")
        if len(cells) < 7:
            _LOGGER.warning("[%s] Moins de 7 colonnes trouvées dans la ligne du dernier match : %s", 
                            team_name, [c.get_text(strip=True) for c in cells])
            # Données incomplètes – on n'assigne pas de valeurs (None par défaut)
            data["last"]["match"] = None
            data["last"]["format"] = None
            data["last"]["date"] = None
            data["last"]["event"] = None
            data["last"]["score"] = None
        else:
            # Extraction des champs depuis les cellules
            date_text = cells[0].get_text(strip=True)  # ex: "Jun 14, 2025 - 15:45 CDT"
            tournament_text = cells[5].get_text(" ", strip=True)  # ex: "BLAST.tv Austin Major 2025: Stage 3"
            score_cell = cells[6]
            # Score affiché (ex: "2 : 0") – on conserve le format avec espaces autour des ":"
            raw_score = score_cell.get_text()  # conserve les espaces insécables éventuels
            # Calcul du format (Bo1, Bo3, ...) à partir du score
            score_clean = raw_score.replace("\u00a0", "")  # retire les espaces insécables
            format_text = None
            if ":" in score_clean:
                parts = score_clean.split(":")
                try:
                    a = int(parts[0]); b = int(parts[1])
                except ValueError:
                    a = b = 0
                max_maps = max(a, b)
                if max_maps <= 1:
                    format_text = "Bo1"
                elif max_maps == 2:
                    format_text = "Bo3"
                elif max_maps == 3:
                    format_text = "Bo5"
                elif max_maps == 4:
                    format_text = "Bo7"
                elif max_maps == 5:
                    format_text = "Bo9"
            elif "-" in score_clean:
                # Score de carte unique (ex: "16-8") => match en une carte (Bo1)
                format_text = "Bo1"

            # Nom de l'adversaire (utilise le texte du lien, ex: "NAVI" ou "VP")
            opponent_cell = cells[7] if len(cells) > 7 else cells[6]  # l'adversaire est en colonne 7 (indice 7) normalement
            opp_name = opponent_cell.get_text(strip=True)
            # Si le nom contient à la fois nom complet et tag, on ne garde que le tag (court)
            if opp_name and opponent_cell.find("a"):
                opp_link_text = opponent_cell.find("a").get_text(strip=True)
                if opp_link_text:
                    opp_name = opp_link_text

            # Conversion de la date/heure en fuseau horaire local de Home Assistant
            time_part = ""
            if " - " in date_text:
                date_part, time_part = date_text.split(" - ", 1)
            else:
                date_part = date_text
            tz_abbr = ""
            time_only = ""
            if time_part:
                parts = time_part.split()
                if len(parts) >= 2:
                    tz_abbr = parts[-1]
                    time_only = parts[0]
                else:
                    time_only = parts[0]
                    tz_abbr = "UTC"
            else:
                # Pas d'heure dans la date (peu probable), on assume minuit UTC
                time_only = "00:00"
                tz_abbr = "UTC"
            # Analyse de la date (ex: "Jun 14, 2025")
            try:
                dt_date = datetime.strptime(date_part, "%b %d, %Y")
            except ValueError:
                try:
                    dt_date = datetime.strptime(date_part, "%B %d, %Y")
                except ValueError:
                    _LOGGER.warning("Impossible de parser la date '%s' pour l'équipe %s", date_part, team_page)
                    dt_date = datetime.utcnow()
            # Heure et minute
            try:
                hour, minute = map(int, time_only.split(":"))
            except Exception:
                hour = minute = 0
            dt_obj = datetime(dt_date.year, dt_date.month, dt_date.day, hour, minute)
            # Fuseau d'origine -> fuseau local Home Assistant
            offset_hours = _TZ_OFFSETS.get(tz_abbr, 0)
            tzinfo = timezone(timedelta(hours=offset_hours)) if tz_abbr != "UTC" else timezone.utc
            dt_local = dt_obj.replace(tzinfo=tzinfo)
            ha_tz = ZoneInfo(str(hass.config.time_zone))
            dt_local = dt_local.astimezone(ha_tz)
            date_local_str = dt_local.strftime("%H:%M %d/%m/%Y")  # format local "HH:MM JJ/MM/AAAA"

            # Nettoyage du nom du tournoi pour l'affichage (on garde le nom complet y compris phase)
            event_name_full = tournament_text  # ex: "BLAST.tv Austin Major 2025: Stage 3"

            # Construction des données "last"
            data["last"]["match"] = f"{team_short} vs {opp_name}"
            data["last"]["format"] = format_text or "Inconnu"
            data["last"]["date"] = date_local_str
            data["last"]["event"] = event_name_full
            # État du score comme résumé "<Team> X : Y <Opp>"
            # On reformate pour s'assurer d'avoir des espaces autour des ':'
            if ":" in score_clean:
                try:
                    a = int(score_clean.split(":")[0]); b = int(score_clean.split(":")[1])
                except ValueError:
                    a = b = 0
                score_display = f"{a} : {b}"
            else:
                score_display = score_clean  # e.g. "16-8"
            data["last"]["score"] = f"{team_short} {score_display} {opp_name}"
    else:
        # Aucun match trouvé (cas peu probable pour une équipe établie)
        _LOGGER.debug("[%s] Aucune table de matches récente trouvée sur la page.", team_name)
        data["last"]["match"] = None
        data["last"]["format"] = None
        data["last"]["date"] = None
        data["last"]["event"] = None
        data["last"]["score"] = None

    # 2. Récupération du prochain match (next_match) via la page centrale Liquipedia:Matches
    central_url = "https://liquipedia.net/counterstrike/Liquipedia:Matches"
    # Vérifier si on doit refetch la page centrale (pas de cache ou cache expiré)
    if (_LAST_CENTRAL_FETCH is None) or (now - _LAST_CENTRAL_FETCH >= SCAN_INTERVAL):
        _LOGGER.debug("Fetching central Liquipedia Matches page for upcoming matches")
        try:
            resp2 = requests.get(central_url, timeout=10)
            resp2.raise_for_status()
        except Exception as err:
            _LOGGER.error("Error fetching central matches page: %s", err)
            # Si échec de la récupération, on conserve d'éventuels résultats précédents
            # et on n'actualise pas _LAST_CENTRAL_FETCH (ainsi une prochaine tentative pourra avoir lieu)
        else:
            soup_all = BeautifulSoup(resp2.text, "lxml")
            new_results: dict[str, dict] = {}
            # Pour chaque équipe suivie, chercher le match à venir
            for page, short_name in TEAM_PAGES.items():
                anchor = soup_all.find(lambda tag: tag.name == "a" 
                                       and tag.get("href") == f"/counterstrike/{page}" 
                                       and tag.get_text(strip=True))
                if anchor:
                    # On a trouvé l'équipe dans la liste des matchs à venir
                    match_row = anchor.find_parent("tr")
                    opp_name = None
                    format_text = None
                    date_local_str = None
                    event_name = None
                    if match_row:
                        # Identifier l'adversaire (dans la colonne opposée)
                        parent_td = anchor.find_parent("td")
                        if parent_td and "team-left" in parent_td.get("class", []):
                            opp_cell = match_row.find("td", class_="team-right")
                        elif parent_td and "team-right" in parent_td.get("class", []):
                            opp_cell = match_row.find("td", class_="team-left")
                        else:
                            opp_cell = None
                        if opp_cell:
                            opp_span = opp_cell.find("span", class_="team-template-text")
                            opp_name = opp_span.get_text(strip=True) if opp_span else opp_cell.get_text(strip=True)
                        # Format (BoX) depuis la colonne "versus"
                        vs_cell = match_row.find("td", class_="versus")
                        if vs_cell:
                            abbr = vs_cell.find("abbr")
                            if abbr:
                                format_text = abbr.get_text(strip=True)
                            else:
                                # Extraire le texte entre parenthèses s'il n'y a pas de balise <abbr>
                                text = vs_cell.get_text(strip=True)
                                if "(" in text and ")" in text:
                                    format_text = text[text.find("(")+1:text.find(")")]
                        # Date/heure et tournoi depuis la ligne suivante (match-filler)
                        details_row = match_row.find_next_sibling("tr")
                        if details_row:
                            # Heure et fuseau
                            time_span = details_row.find("span", class_="timer-object")
                            if time_span:
                                time_text = time_span.get_text()  # ne pas strip pour conserver l'espace avant le TZ
                                if " - " in time_text:
                                    date_part, time_part = time_text.split(" - ", 1)
                                else:
                                    date_part, time_part = time_text, ""
                                tz_abbr = ""
                                time_only = ""
                                if time_part:
                                    parts = time_part.split()
                                    if len(parts) >= 2:
                                        tz_abbr = parts[-1]
                                        time_only = parts[0]
                                    else:
                                        time_only = parts[0]
                                        tz_abbr = "UTC"
                                else:
                                    time_only = "00:00"
                                    tz_abbr = "UTC"
                                # Parsing de la date (ex: "June 20, 2025")
                                try:
                                    dt_date = datetime.strptime(date_part, "%B %d, %Y")
                                except ValueError:
                                    try:
                                        dt_date = datetime.strptime(date_part, "%b %d, %Y")
                                    except ValueError:
                                        _LOGGER.warning("Could not parse date '%s' for upcoming match of %s", date_part, team_page)
                                        dt_date = datetime.utcnow()
                                try:
                                    hour, minute = map(int, time_only.split(":"))
                                except Exception:
                                    hour = minute = 0
                                dt_obj = datetime(dt_date.year, dt_date.month, dt_date.day, hour, minute)
                                # Conversion fuseau -> fuseau local HA
                                offset_hours = _TZ_OFFSETS.get(tz_abbr, 0)
                                tzinfo = timezone(timedelta(hours=offset_hours)) if tz_abbr != "UTC" else timezone.utc
                                dt_local = dt_obj.replace(tzinfo=tzinfo)
                                ha_tz = ZoneInfo(str(hass.config.time_zone))
                                dt_local = dt_local.astimezone(ha_tz)
                                date_local_str = dt_local.strftime("%H:%M %d/%m/%Y")
                            # Nom du tournoi
                            event_elem = details_row.find("div", class_="text-nowrap")
                            if event_elem:
                                event_name = event_elem.get_text(strip=True)
                    # Remplir les données "next" pour cette équipe
                    data["next"]["match"] = f"{short_name} vs {opp_name}" if opp_name else None
                    data["next"]["format"] = format_text or "Inconnu"
                    data["next"]["date"] = date_local_str
                    data["next"]["event"] = event_name
                else:
                    # Aucun match à venir trouvé pour cette équipe
                    data["next"]["match"] = "No upcoming match"
                    data["next"]["format"] = None
                    data["next"]["date"] = None
                    data["next"]["event"] = None
                # Stocker dans les résultats centraux mis à jour
                new_results[page] = data["next"].copy()
            # Mettre à jour le cache central
            _CENTRAL_RESULTS = new_results
            _LAST_CENTRAL_FETCH = datetime.utcnow()
    # Si la page centrale est en cache et pas expirée, utiliser les données en cache pour ce team_page
    if team_page in _CENTRAL_RESULTS:
        data["next"] = _CENTRAL_RESULTS[team_page].copy()
    else:
        # Par sécurité, si on n'a rien trouvé (par ex. erreur précédente), on marque "No upcoming match"
        data["next"]["match"] = "No upcoming match"
        data["next"]["format"] = None
        data["next"]["date"] = None
        data["next"]["event"] = None

    # Mémoriser en cache le résultat pour ce team_page
    _TEAM_DATA_CACHE[team_page] = data
    _LAST_FETCH[team_page] = now

    # Post-traitement : valeurs par défaut si certaines données manquent
    if "last" in data:
        if not data["last"].get("format"):
            data["last"]["format"] = "Inconnu"
        if not data["last"].get("score") and data["last"].get("match"):
            data["last"]["score"] = "Score inconnu"
    if "next" in data:
        if not data["next"].get("format"):
            data["next"]["format"] = "Inconnu"

    return data

class LiquipediaCsMatchSensor(SensorEntity):
    """Capteur générique pour un match Liquipedia CS d'une équipe."""

    def __init__(self, team_page: str, team_name: str, match_type: str):
        """Initialiser le capteur."""
        self._team_page = team_page  # ex: "Team_Vitality"
        self._team_name = team_name  # ex: "Vitality"
        self._match_type = match_type  # "next" ou "last"
        self._state = None
        self._attr_native_value = None
        # Construire l'ID unique et le nom d'affichage de l'entité
        key = team_name.lower().replace(" ", "_")
        self._attr_unique_id = f"liquipedia_cs_{key}_{match_type}"
        self._attr_has_entity_name = False
        self._attr_name = f"Liquipedia CS {team_name} {match_type} match"
        self._attributes = {}

    @property
    def extra_state_attributes(self):
        """Retourner les attributs d'état du capteur."""
        return self._attributes

    def update(self):
        """Récupérer et traiter la page Liquipedia pour mettre à jour l’état."""
        url = f"https://liquipedia.net/counterstrike/{self._team_page}"
        try:
            res = requests.get(url, headers={"User-Agent": "HomeAssistant"})
            res.raise_for_status()
        except Exception as e:
            _LOGGER.error("Erreur requête Liquipedia pour %s: %s", self._team_name, e)
            self._state = None
            return

        tree = html.fromstring(res.text)
        if self._match_type == "next":
            # Extraction du prochain match (section "Upcoming Matches")
            rows = tree.xpath("//span[@id='Upcoming_Matches']/ancestor::h2/following-sibling::table//tr")
            if rows:
                row = rows[0]  # on prend la première ligne
                # Extrait le nom de l'adversaire (dernier <a> dans le premier <td>)
                opp = row.xpath(".//td[1]//a/text()")
                opponent = opp[-1] if opp else None
                # Format (ex: "(Bo3)")
                text_content = "".join(row.xpath(".//td[1]//text()"))
                fmt_match = re.search(r"\((Bo[0-9])\)", text_content)
                match_format = fmt_match.group(1) if fmt_match else ""
                # Date et heure (colonne 2)
                dt_str = row.xpath(".//td[2]/text()")
                dt_str = dt_str[0] if dt_str else ""
                # Convertir en local et formater "DD/MM/YYYY HH:MM"
                try:
                    dt = datetime.strptime(dt_str, "%B %d, %Y - %H:%M %Z")
                    dt = dt.astimezone()  # vers timezone local
                    date_local = dt.strftime("%d/%m/%Y %H:%M")
                except Exception:
                    date_local = dt_str
                # Événement (colonne 3, lien)
                event = row.xpath(".//td[3]//a/text()")
                event_name = event[0] if event else ""
                # Remplir attributs
                self._state = f"{self._team_name} vs {opponent}"
                self._attributes = {
                    "match": self._state,
                    "format": match_format,
                    "date": date_local,
                    "event": event_name
                }
            else:
                # Pas de prochain match connu
                self._state = None
                self._attributes = {}
        else:
            # Extraction du dernier match (section "Résultats récents")
            # Rechercher la première ligne de la table des résultats
            rows = tree.xpath("//table//tr[td and not(contains(string(.), 'Date'))]")
            if rows:
                row = rows[0]
                cols = row.xpath("./td")
                if len(cols) >= 7:
                    # colonnes: Date | Time | Tier | Type | Tournoi | Score | vs
                    date_str = cols[0].text_content().strip()
                    time_str = cols[1].text_content().strip()
                    score = cols[5].text_content().strip()
                    opponent = cols[6].xpath(".//a/text()")
                    opponent = opponent[0] if opponent else ""
                    event = cols[4].xpath(".//a/text()")
                    event = event[0] if event else ""
                    # Fusion date+heure et conversion timezone similaire
                    dt_text = f"{date_str} {time_str}"
                    try:
                        dt = datetime.strptime(dt_text, "%Y-%m-%d %H:%M %Z")
                        dt = dt.astimezone()
                        date_local = dt.strftime("%d/%m/%Y %H:%M")
                    except Exception:
                        date_local = dt_text
                    # Deviner le format (généralement Bo3 hors phases de groupes)
                    if "Stage 2" in event or "Group" in event:
                        match_format = "Bo1"
                    else:
                        match_format = "Bo3"
                    match_name = f"{self._team_name} vs {opponent}"
                    self._state = match_name
                    self._attributes = {
                        "match": match_name,
                        "format": match_format,
                        "date": date_local,
                        "event": event,
                        "score": score
                    }
                else:
                    self._state = None
                    self._attributes = {}
            else:
                self._state = None
                self._attributes = {}

def setup_platform(hass, config, add_entities, discovery_info=None):
    """Configurer les capteurs selon la liste d'équipes du YAML."""
    teams = config.get("teams", [])
    entities = []
    for team in teams:
        page = team.get("page")
        name = team.get("name")
        if page and name:
            entities.append(LiquipediaCsMatchSensor(page, name, "next"))
            entities.append(LiquipediaCsMatchSensor(page, name, "last"))
    add_entities(entities, True)
