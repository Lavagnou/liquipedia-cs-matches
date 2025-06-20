"""Bouton Home Assistant pour mettre à jour toutes les équipes."""
import logging

from homeassistant.components.button import ButtonEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

def setup_platform(hass, config, add_entities, discovery_info=None):
    """Configurer le bouton Liquipedia CS."""
    add_entities([LiquipediaCsUpdateButton(hass)], True)
    _LOGGER.info("Liquipedia CS update button configured")

class LiquipediaCsUpdateButton(ButtonEntity):
    """Bouton pour mettre à jour tous les capteurs Liquipedia CS."""
    def __init__(self, hass):
        """Initialiser le bouton."""
        self.hass = hass
        self._attr_name = "Liquipedia CS Update All"
        self._attr_unique_id = "liquipedia_cs_update_button"
        self._attr_icon = "mdi:refresh"
    
    def press(self):
        """Gérer l'appui sur le bouton."""
        _LOGGER.info("Liquipedia CS update button pressed")
        
        # Récupérer toutes les entités
        if DOMAIN in self.hass.data and "entities" in self.hass.data[DOMAIN]:
            entities = self.hass.data[DOMAIN]["entities"]
            
            # Mettre à jour chaque entité
            for entity in entities:
                try:
                    entity.update()
                    _LOGGER.debug(f"Updated {entity.name}")
                except Exception as err:
                    _LOGGER.error(f"Error updating {entity.name}: {err}")
        else:
            _LOGGER.warning("No entities found to update")
