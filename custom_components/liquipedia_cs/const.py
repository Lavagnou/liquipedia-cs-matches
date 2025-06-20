"""Constants for the Liquipedia CS Matches integration."""
from datetime import timedelta

# Le domaine doit correspondre exactement au nom du dossier dans custom_components
DOMAIN = "liquipedia_cs"

# Configuration constants
CONF_TEAMS = "teams"
CONF_PAGE = "page"
CONF_NAME = "name"
DEFAULT_NAME = "Liquipedia CS Matches"

# Types de capteurs
SENSOR_TYPE_NEXT = "next"
SENSOR_TYPE_LAST = "last"

# Scanning intervals
SCAN_INTERVAL = timedelta(minutes=30)

# URLs de base
BASE_URL = "https://liquipedia.net/counterstrike"
MATCHES_URL = f"{BASE_URL}/Liquipedia:Matches"

# En-têtes HTTP
HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Home Assistant) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml",
    "Accept-Language": "fr,fr-FR;q=0.9,en;q=0.8,en-US;q=0.7"
}
