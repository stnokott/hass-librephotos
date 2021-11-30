"""Main sensor"""

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from custom_components.librephotos import DOMAIN


async def async_setup_platform(
    hass: HomeAssistant, config, async_add_entities, discovery_info=None
):
    coordinator = hass.data[DOMAIN]["coordinator"]
    async_add_entities(
        [LibrePhotosSensor(coordinator)],
        True,
    )


class LibrePhotosSensor(CoordinatorEntity):
    """Sensor that provides data about LibrePhotos instance"""

    def __init__(self, coordinator: DataUpdateCoordinator[dict]):
        super().__init__(coordinator)
        self.attrs = {}
        self._state = 0

    @property
    def name(self):
        return "LibrePhotos Workers"

    @property
    def entity_id(self):
        return f"sensor.{DOMAIN}"

    @property
    def state(self):
        self.attrs["some_attr"] = self.coordinator.data
        return len(self.coordinator.data.values())

    @property
    def device_state_attributes(self):
        return self.attrs
