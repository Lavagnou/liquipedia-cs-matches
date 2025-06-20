"""Constants for the Liquipedia CS Matches integration."""
from datetime import timedelta

# Le domaine doit correspondre exactement au nom du dossier dans custom_components
DOMAIN = "liquipedia_cs"

# Configuration constants
CONF_TEAMS = "teams"
CONF_PAGE = "page"
DEFAULT_NAME = "Liquipedia CS Matches"

# Scanning intervals
SCAN_INTERVAL = timedelta(minutes=30)
