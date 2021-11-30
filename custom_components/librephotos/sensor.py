"""Main sensor"""
import logging
from datetime import timedelta

import async_timeout
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.entity_component import DEFAULT_SCAN_INTERVAL
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from custom_components.librephotos import DOMAIN, ATTR_WORKERS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    """Setup sensor entry"""
    api = hass.data[DOMAIN][entry.entry_id]
    username = entry.data[CONF_USERNAME]
    scan_interval = entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

    async def async_update_data():
        """Async method to update LibrePhotos API data"""
        try:
            async with async_timeout.timeout(10):
                workers = await hass.async_add_executor_job(api.get_workers)
                return {
                    "workers": {
                        "state": len(workers),
                        "attributes": {
                            ATTR_WORKERS: [
                                {
                                    "queued_by": worker.queued_by,
                                    "queued_at": worker.queued_at,
                                    "started_at": worker.started_at,
                                    "finished_at": worker.finished_at,
                                    "is_started": worker.is_started,
                                    "is_finished": worker.is_finished,
                                    "is_failed": worker.is_failed,
                                    "progress_current": worker.progress_current,
                                    "progress_target": worker.progress_target,
                                }
                                for worker in workers
                            ]
                        },
                    }
                }
        except ValueError as e:
            raise ConfigEntryAuthFailed from e

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"LibrePhotos for user {username}",
        update_method=async_update_data,
        update_interval=timedelta(seconds=scan_interval),
    )

    await coordinator.async_config_entry_first_refresh()

    async_add_entities(LibrePhotosSensor(coordinator))


class LibrePhotosSensor(CoordinatorEntity, SensorEntity):
    """Sensor that provides data about LibrePhotos instance"""

    def __init__(self, coordinator):
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
