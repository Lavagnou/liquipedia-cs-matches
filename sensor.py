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
