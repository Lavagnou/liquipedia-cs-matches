"""Tests for the Liquipedia CS Matches sensor platform."""
from unittest.mock import MagicMock, patch
import pytest

from homeassistant.setup import async_setup_component
from custom_components.liquipedia_cs_matches.sensor import (
    LiquipediaCsMatchSensor,
    fetch_team_data,
)
from custom_components.liquipedia_cs_matches.const import DOMAIN

# Tests will be implemented later
