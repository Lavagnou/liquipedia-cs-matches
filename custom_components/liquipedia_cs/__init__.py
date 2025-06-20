"""The Liquipedia CS Matches integration."""
import logging
import asyncio
import async_timeout
from datetime import datetime, timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Liquipedia CS component."""
    # Initialiser le dictionnaire de domaine
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["entities"] = []
    hass.data[DOMAIN]["match_data"] = {}
    hass.data[DOMAIN]["last_update"] = datetime.now() - timedelta(minutes=30)
    
    # Les capteurs seront configurés par la configuration YAML directement
    _LOGGER.info("Liquipedia CS Matches integration initialized")
    return True
