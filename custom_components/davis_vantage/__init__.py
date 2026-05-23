"""The Davis Vantage integration."""

from __future__ import annotations
from dataclasses import dataclass
import logging

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.const import Platform
from .client import DavisVantageClient
from .const import (
    DOMAIN,
    NAME,
    MANUFACTURER,
    CONFIG_INSTANCE_NAME,
    CONFIG_STATION_MODEL,
    CONFIG_INTERVAL,
    CONFIG_PROTOCOL,
    CONFIG_LINK,
    CONFIG_PERSISTENT_CONNECTION,
    SERVICE_SET_DAVIS_TIME,
    SERVICE_GET_DAVIS_TIME,
    SERVICE_GET_RAW_DATA,
    SERVICE_GET_INFO,
    SERVICE_SET_YEARLY_RAIN,
    SERVICE_SET_ARCHIVE_PERIOD,
    SERVICE_SET_RAIN_COLLECTOR,
)
from .coordinator import DavisVantageDataUpdateCoordinator
from .services import DavisServicesSetup

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]

_LOGGER: logging.Logger = logging.getLogger(__package__)

SERVICES = [
    SERVICE_SET_DAVIS_TIME,
    SERVICE_GET_DAVIS_TIME,
    SERVICE_GET_RAW_DATA,
    SERVICE_GET_INFO,
    SERVICE_SET_YEARLY_RAIN,
    SERVICE_SET_ARCHIVE_PERIOD,
    SERVICE_SET_RAIN_COLLECTOR,
]


@dataclass
class RuntimeData:
    """Class to hold your data."""
    coordinator: DavisVantageDataUpdateCoordinator

type DavisConfigEntry = ConfigEntry[RuntimeData]

async def async_setup_entry(
    hass: HomeAssistant, config_entry: DavisConfigEntry
) -> bool:
    """Set up Davis Vantage from a config entry."""
    if hass.data.get(DOMAIN) is None:
        hass.data.setdefault(DOMAIN, {})

    _LOGGER.debug("entry.data: %s", config_entry.data)

    protocol = config_entry.data.get(CONFIG_PROTOCOL, "")
    link = config_entry.data.get(CONFIG_LINK, "")
    persistent_connection = config_entry.data.get(CONFIG_PERSISTENT_CONNECTION, False)
    instance_name = config_entry.data.get(
        CONFIG_INSTANCE_NAME, config_entry.title or NAME
    )

    hass.data[DOMAIN]["interval"] = config_entry.data.get(CONFIG_INTERVAL, 30)

    client = DavisVantageClient(hass, protocol, link, persistent_connection)

    device_info = DeviceInfo(
        identifiers={(DOMAIN, config_entry.entry_id)},
        manufacturer=MANUFACTURER,
        name=instance_name,
        model=config_entry.data.get(CONFIG_STATION_MODEL, "Unknown"),
        sw_version=None,
        hw_version=None,
    )

    coordinator = (
        DavisVantageDataUpdateCoordinator(
            hass=hass, client=client, device_info=device_info, config_entry=config_entry
        )
    )

    config_entry.runtime_data = RuntimeData(coordinator)

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    # Don't block startup on a potentially slow serial handshake.
    hass.async_create_task(coordinator.async_refresh())

    config_entry.async_on_unload(
        config_entry.add_update_listener(async_reload_entry)
    )

    if not hass.services.has_service(DOMAIN, SERVICE_SET_DAVIS_TIME):
        DavisServicesSetup(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: DavisConfigEntry) -> bool:
    """Unload a config entry."""
    coordinator = config_entry.runtime_data.coordinator
    coordinator.client._executor.shutdown(wait=False)
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )

    loaded_entries = [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.state == ConfigEntryState.LOADED
    ]
    if unload_ok and not loaded_entries:
        for service in SERVICES:
            hass.services.async_remove(DOMAIN, service)

    return unload_ok

async def async_reload_entry(hass: HomeAssistant, config_entry: DavisConfigEntry) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(config_entry.entry_id)