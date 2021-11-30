"""
Converts Octet String values to plain string
"""
from __future__ import annotations
import time

import logging
from collections import namedtuple
from datetime import timedelta, datetime
from typing import Optional, List, Any

import requests
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import (
    CONF_HOST,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_PORT,
    CONF_FRIENDLY_NAME,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import Throttle

from custom_components.librephotos.const.const import (
    FRIENDLY_NAME_PREFIX,
    UNIQUE_ID_PREFIX,
    MAX_WORKERS_COUNT,
    STRPTIME_FORMAT,
    QUERY_ACCESS_TOKEN,
    QUERY_WORKERS,
    ATTR_WORKERS,
)

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.url,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_PORT, default=3000): cv.positive_int,
        vol.Optional(CONF_SCAN_INTERVAL, default=60): cv.positive_int,
        vol.Optional(CONF_FRIENDLY_NAME, default=FRIENDLY_NAME_PREFIX): cv.string,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info=None,
):
    """Setup platform"""
    _LOGGER.debug("Setting up sensor")

    host = config.get(CONF_HOST)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    port = config.get(CONF_PORT)
    scan_interval = config.get(CONF_SCAN_INTERVAL)
    friendly_name = config.get(CONF_FRIENDLY_NAME)

    libre_photos_sensor = LibrePhotosSensor(
        host, username, password, port, scan_interval, friendly_name
    )

    add_entities([libre_photos_sensor])


class LibrePhotosSensor(SensorEntity):
    """Sensor that provides data about LibrePhotos instance"""

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        port: int,
        scan_interval: int,
        friendly_name: str,
    ):
        self._friendly_name = friendly_name

        self._available = False
        self._state = None
        self._attributes = None

        self.update = Throttle(timedelta(seconds=scan_interval))(self._update)

        self._api = LibrePhotosApi(host, port, username, password)

    def _update(self) -> None:
        try:
            workers = self._api.get_workers()
            self._state = len(workers)
            self._attributes = {
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
            }
        except ValueError as e:
            self._available = False
            self._state = None
            self._attributes = None
            _LOGGER.error(e)
        else:
            self._available = True

    @property
    def name(self):
        return self._friendly_name + " Workers"

    @property
    def unique_id(self):
        return UNIQUE_ID_PREFIX + " Workers"

    @property
    def available(self) -> bool:
        return self._available

    @property
    def state(self):
        return self._state

    @property
    def state_attributes(self) -> dict[str, Any] | None:
        return self._attributes


Worker = namedtuple(
    "Worker",
    [
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
    """API wrapper for LibrePhotos instance"""

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
            return result.json()["access"]

    class Decorators(object):
        """Decorators"""

        @staticmethod
        def refresh_token(func):
            def inner(api: LibrePhotosApi, *args, **kwargs):
                """Refresh access token"""
                if api._access_token is None or time.time() > api._access_token_expiry:
                    api._access_token = api._get_access_token()
                return func(api, *args, **kwargs)

            return inner

    @Decorators.refresh_token
    def get_workers(self) -> List[Worker]:
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
            return workers
