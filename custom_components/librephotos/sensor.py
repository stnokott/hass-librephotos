"""Main sensor."""
from __future__ import annotations

import logging
import time
from collections import namedtuple
from datetime import datetime
from typing import List, Optional

import async_timeout
import homeassistant.helpers.config_validation as cv
import requests
import voluptuous as vol
from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.config_entries import ConfigType
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.entity_component import DEFAULT_SCAN_INTERVAL
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from custom_components.librephotos.const.const import (
    DOMAIN,
    KEY_ATTR_WORKERS,
    KEY_ATTRS,
    KEY_SENSOR_WORKERS,
    KEY_STATE,
    MAX_WORKERS_COUNT,
    QUERY_ACCESS_TOKEN,
    QUERY_WORKERS,
    STRPTIME_FORMAT,
)

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.url,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_PORT, default=3000): cv.positive_int,
    }
)


async def async_setup_platform(
    hass: HomeAssistant, config: ConfigType, async_add_entities, discovery_info=None
):
    """Set sensor entry up."""
    host = config[CONF_HOST]
    username = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]
    port = config[CONF_PORT]

    api = LibrePhotosApi(host, port, username, password)
    username = config[CONF_USERNAME]
    scan_interval = DEFAULT_SCAN_INTERVAL

    async def async_update_data():
        """Async method to update LibrePhotos API data."""
        try:
            async with async_timeout.timeout(10):
                workers = await hass.async_add_executor_job(api.get_workers)
                return {
                    KEY_SENSOR_WORKERS: {
                        KEY_STATE: len(workers),
                        KEY_ATTRS: {
                            KEY_ATTR_WORKERS: [worker._asdict() for worker in workers]
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
        update_interval=scan_interval,
    )

    await coordinator.async_config_entry_first_refresh()

    async_add_entities([LibrePhotosSensor(coordinator)])


class LibrePhotosSensor(CoordinatorEntity, SensorEntity):
    """Sensor that provides data about LibrePhotos instance."""

    def __init__(self, coordinator):
        """Constructor."""
        super().__init__(coordinator)
        self.attrs = {}
        self._state = 0

    @property
    def name(self):
        """Entity name."""
        return "LibrePhotos Workers"

    @property
    def entity_id(self):
        """Unique entity id."""
        return f"sensor.{DOMAIN}_workers"

    @property
    def icon(self) -> str | None:
        """Entity icon."""
        return "mdi:image-multiple"

    @property
    def state(self):
        """Current entity state, derived from coordinator data."""
        self.attrs = self.coordinator.data[KEY_SENSOR_WORKERS][KEY_ATTRS]
        return self.coordinator.data[KEY_SENSOR_WORKERS][KEY_STATE]

    @property
    def device_state_attributes(self):
        """Device state attributes."""
        return self.attrs


Worker = namedtuple(
    "Worker",
    [
        "id",
        "job_type",
        "queued_by",
        "queued_at",
        "started_at",
        "finished_at",
        "is_started",
        "is_finished",
        "is_failed",
        "progress_current",
        "progress_target",
    ],
)


class LibrePhotosApi(object):
    """API wrapper for LibrePhotos instance."""

    _access_token: Optional[str] = None
    _access_token_expiry: Optional[float] = None

    def __init__(self, host: str, port: int, username: str, password: str):
        self._username = username
        self._password = password
        self._base_url = f"{host}:{port}/"

    def _get_access_token(self) -> str:
        data = {"username": self._username, "password": self._password}
        result = requests.post(self._base_url + QUERY_ACCESS_TOKEN, data=data)
        try:
            result.raise_for_status()
        except requests.HTTPError as e:
            raise ValueError(f"Login unsuccessful: {e}")
        else:
            self._access_token_expiry = time.time() + 3500
            _LOGGER.debug("Token refreshed")
            return result.json()["access"]

    class Decorators(object):
        """Decorators."""

        @staticmethod
        def refresh_token(func):
            """Refresh token if necessary."""

            def inner(api: LibrePhotosApi, *args, **kwargs):
                """Perform access token refresh."""
                if api._access_token is None or time.time() > api._access_token_expiry:
                    api._access_token = api._get_access_token()
                return func(api, *args, **kwargs)

            return inner

    @Decorators.refresh_token
    def get_workers(self) -> List[Worker]:
        """Retrieve workers from LibrePhotos API."""
        params = {"page_size": MAX_WORKERS_COUNT, "page": 1}
        headers = {"Authorization": f"Bearer {self._access_token}"}
        result = requests.get(
            self._base_url + QUERY_WORKERS, params=params, headers=headers
        )
        result_json = result.json()
        workers = []
        for i in range(min(result_json["count"], MAX_WORKERS_COUNT)):
            worker = result_json["results"][i]
            is_started = worker["started_at"] != ""
            is_finished = worker["finished"]
            is_failed = bool(worker["failed"])
            workers.append(
                Worker(
                    id=worker["job_id"],
                    job_type=worker["job_type_str"],
                    queued_by=worker["started_by"]["username"],
                    queued_at=datetime.strptime(worker["queued_at"], STRPTIME_FORMAT),
                    started_at=datetime.strptime(worker["started_at"], STRPTIME_FORMAT)
                    if is_started
                    else None,
                    finished_at=datetime.strptime(
                        worker["finished_at"], STRPTIME_FORMAT
                    )
                    if is_finished
                    else None,
                    is_started=is_started,
                    is_finished=is_finished,
                    is_failed=is_failed,
                    progress_current=int(worker["result"]["progress"]["current"])
                    if is_started
                    else None,
                    progress_target=int(worker["result"]["progress"]["target"])
                    if is_started
                    else None,
                )
            )
        _LOGGER.debug(f"Retreived data for {len(workers)} workers")
        return workers
