"""Button component for Liquipedia CS Matches."""
import logging

from homeassistant.components.button import ButtonEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Liquipedia CS button platform."""
    # Add the refresh button
    async_add_entities([LiquipediaCSRefreshButton(hass)], True)
    _LOGGER.info("Liquipedia CS refresh button configured")

class LiquipediaCSRefreshButton(ButtonEntity):
    """Button to refresh Liquipedia CS matches data."""
    
    def __init__(self, hass):
        """Initialize the button."""
        self.hass = hass
        self._attr_name = "Refresh Liquipedia CS Matches"
        self._attr_unique_id = "liquipedia_cs_refresh_button"
        self._attr_icon = "mdi:refresh"
    
    async def async_press(self):
        """Handle button press."""
        _LOGGER.info("Liquipedia CS refresh button pressed - updating all sensors")
        
        # Call the update service
        await self.hass.services.async_call(
            DOMAIN, "update_matches", {}
        )
