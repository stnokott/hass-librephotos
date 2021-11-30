"""
Converts Octet String values to plain string
"""
from __future__ import annotations
import time

import logging
from collections import namedtuple
from datetime import timedelta, datetime
from typing import Optional, List

import async_timeout
import requests
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_HOST,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_PORT,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
)

from custom_components.librephotos.const.const import (
    MAX_WORKERS_COUNT,
    STRPTIME_FORMAT,
    QUERY_ACCESS_TOKEN,
    QUERY_WORKERS,
    ATTR_WORKERS,
    CONFIG_REFRESH_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.url,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_PORT, default=3000): cv.positive_int,
        vol.Optional(CONFIG_REFRESH_INTERVAL, default=60): cv.positive_int,
    }
)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Setup platform"""
    _LOGGER.debug("Setting up sensor")

    conf = config[DOMAIN]
    host = conf[CONF_HOST]
    username = conf[CONF_USERNAME]
    password = conf[CONF_PASSWORD]
    port = conf[CONF_PORT]
    refresh_interval = conf[CONFIG_REFRESH_INTERVAL]

    api = LibrePhotosApi(host, port, username, password)

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
        name=DOMAIN,
        update_method=async_update_data,
        update_interval=timedelta(seconds=refresh_interval),
    )

    await coordinator.async_refresh()

    hass.data[DOMAIN] = {"conf": conf, "coordinator": coordinator}
    hass.async_create_task(async_load_platform(hass, "sensor", DOMAIN, {}, conf))
    return True


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
            _LOGGER.debug("Token refreshed")
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
        _LOGGER.debug(f"Retreived data for {len(workers)} workers")
        return workers
