"""Liquipedia CS Matches integration init file."""
import logging

DOMAIN = "liquipedia_cs_matches"
_LOGGER = logging.getLogger(__name__)

async def async_setup(hass, config):
    """Set up the Liquipedia CS Matches integration."""
    hass.data.setdefault(DOMAIN, {})
    _LOGGER.debug("Liquipedia CS Matches integration initialized")
    return True
