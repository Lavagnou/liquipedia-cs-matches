"""Bouton Home Assistant pour mettre à jour toutes les équipes."""
from homeassistant.components.button import ButtonEntity
from .const import DOMAIN

class LiquipediaCsUpdateAllButton(ButtonEntity):
    """Bouton pour forcer la mise à jour de tous les capteurs."""

    def __init__(self, hass):
        self._hass = hass
        self._attr_name = "Liquipedia CS Update All Matches"

    async def async_press(self):
        """Mise à jour manuelle de tous les capteurs de rencontres."""
        # Récupérer toutes les entités de ce domaine et appeler update()
        for entity in list(self._hass.data.get(DOMAIN, {}).get("entities", [])):
            self._hass.async_create_task(self._hass.async_add_executor_job(entity.update))
