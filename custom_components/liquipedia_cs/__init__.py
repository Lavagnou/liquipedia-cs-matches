"""The Liquipedia CS Matches integration."""
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Liquipedia CS component."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["entities"] = []
    
    # Les capteurs seront configurés par la configuration YAML directement
    _LOGGER.info("Liquipedia CS Matches integration initialized")
    return True
