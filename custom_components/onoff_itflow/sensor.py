"""Sensor platform for On-Off ITFlow integration."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Any
import platform
import subprocess

import psutil
import aiohttp

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfInformation,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.event import async_track_time_interval

from homeassistant.const import CONF_NAME

from .const import (
    DOMAIN,
    CONF_GATEWAY_IP,
    CONF_CF_TUNNEL_ENABLED,
    CONF_CF_TUNNEL_IP,
    CONF_MASTER_ACCOUNT_MODE,
    map_ticket_status,
)

_LOGGER = logging.getLogger(__name__)


def build_ticket_attributes_with_size_check(tickets, include_tickets_array=False):
    """Build ticket attributes with dynamic size reduction to fit within 16KB limit.

    Args:
        tickets: List of ticket dictionaries (should be sorted by most recent first)
        include_tickets_array: Whether to include the tickets array (for open tickets)

    Returns:
        Dictionary of attributes that fit within size limit
    """
    import json

    # Start with 25 tickets and reduce if needed
    max_tickets = 25

    # Keep trying until attributes fit in 16KB (with 3 ticket buffer for growth)
    while max_tickets > 0:
        attributes = {}
        # Get the FIRST max_tickets (most recent tickets, since list is sorted newest first)
        limited_tickets = tickets[:max_tickets]

        # Add tickets array if requested (for open tickets sensor)
        if include_tickets_array:
            tickets_array = []
            for ticket in limited_tickets:
                raw_status = ticket.get("ticket_status", "")
                friendly_status = map_ticket_status(raw_status)

                tickets_array.append({
                    "id": ticket.get("ticket_id", "unknown"),
                    "ticket_id": ticket.get("ticket_id", "unknown"),
                    "number": ticket.get("ticket_number", ticket.get("ticket_id", "unknown")),
                    "ticket_number": ticket.get("ticket_number", ticket.get("ticket_id", "unknown")),
                    "subject": ticket.get("ticket_subject", "")[:100],
                    "ticket_subject": ticket.get("ticket_subject", "")[:100],
                    "priority": ticket.get("ticket_priority", ""),
                    "ticket_priority": ticket.get("ticket_priority", ""),
                    "status": friendly_status,
                    "ticket_status": friendly_status,
                    "created": ticket.get("ticket_created_at", ""),
                    "details": ticket.get("ticket_details", "")[:100],
                    "category": ticket.get("ticket_category", ""),
                    "ticket_category": ticket.get("ticket_category", ""),
                    "assigned_to": ticket.get("ticket_assigned_to", ""),
                    "ticket_assigned_to": ticket.get("ticket_assigned_to", ""),
                })
            attributes["tickets"] = tickets_array

        # Add individual attributes for backwards compatibility
        for idx, ticket in enumerate(limited_tickets):
            ticket_id = ticket.get("ticket_id", "unknown")
            raw_status = ticket.get("ticket_status", "")
            friendly_status = map_ticket_status(raw_status)

            attributes[f"ticket_{idx + 1}_id"] = ticket_id
            attributes[f"ticket_{idx + 1}_subject"] = ticket.get("ticket_subject", "")[:100]
            attributes[f"ticket_{idx + 1}_priority"] = ticket.get("ticket_priority", "")
            attributes[f"ticket_{idx + 1}_status"] = friendly_status
            attributes[f"ticket_{idx + 1}_status_raw"] = raw_status
            attributes[f"ticket_{idx + 1}_created"] = ticket.get("ticket_created_at", "")
            attributes[f"ticket_{idx + 1}_details"] = ticket.get("ticket_details", "")[:100]
            attributes[f"ticket_{idx + 1}_category"] = ticket.get("ticket_category", "")
            attributes[f"ticket_{idx + 1}_assigned_to"] = ticket.get("ticket_assigned_to", "")

        attributes["total_tickets"] = len(tickets)
        attributes["displayed_tickets"] = len(limited_tickets)
        attributes["last_updated"] = datetime.now(timezone.utc).isoformat()

        # Check size (16KB = 16384 bytes, leave buffer for 3 more tickets)
        attr_size = len(json.dumps(attributes, default=str))
        if attr_size < 14000:  # Leave ~2KB buffer for 3 more tickets
            break

        # Reduce by 1 ticket and try again
        max_tickets -= 1

    return attributes


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    """Set up On-Off ITFlow sensors."""
    title = entry.runtime_data
    entities = [
        AutoHCloudSensor(hass, entry.entry_id, title),
        AutoHReportLastUpdatedSensor(hass, entry.entry_id, title),
    ]

    # Add ITFlow ticket sensors (always enabled now)
    entities.extend([
        ITFlowTicketSensor(hass, entry.entry_id, title),
        ITFlowNewTicketsSensor(hass, entry.entry_id, title),
        ITFlowOpenTicketsSensor(hass, entry.entry_id, title),
        ITFlowResolvedTicketsSensor(hass, entry.entry_id, title),
        ITFlowClosedTicketsSensor(hass, entry.entry_id, title),
        ITFlowMaintenanceTicketsSensor(hass, entry.entry_id, title),
        ITFlowContactsSensor(hass, entry.entry_id, title),
    ])

    # Add clients sensor if in master account mode
    if entry.data.get(CONF_MASTER_ACCOUNT_MODE, False):
        entities.append(ITFlowClientsSensor(hass, entry))

    # Add System Monitoring sensors (only if enabled)
    if entry.data.get("enable_system_sensors", True):
        entities.extend([
            SystemCPUUsageSensor(hass, entry.entry_id, title),
            SystemMemoryUsageSensor(hass, entry.entry_id, title),
            SystemMemoryFreeSensor(hass, entry.entry_id, title),
            SystemMemoryTotalSensor(hass, entry.entry_id, title),
            SystemDiskUsageSensor(hass, entry.entry_id, title),
            SystemDiskFreeSensor(hass, entry.entry_id, title),
            SystemDiskTotalSensor(hass, entry.entry_id, title),
            SystemLoadAvgSensor(hass, entry.entry_id, title),
            SystemProcessCountSensor(hass, entry.entry_id, title),
            SystemCPUTemperatureSensor(hass, entry.entry_id, title),
            SystemHALastRebootSensor(hass, entry.entry_id, title),
            SystemOSLastRebootSensor(hass, entry.entry_id, title),
            SystemVersionInstalledSensor(hass, entry.entry_id, title),
            SystemVersionLatestSensor(hass, entry.entry_id, title),
            SystemPublicIPSensor(hass, entry.entry_id, title),
            SystemLocalIPSensor(hass, entry.entry_id, title),
            SystemHAIDSensor(hass, entry.entry_id, title),
            LoggedInUsersSensor(hass, entry.entry_id, title),
            TotalEntitiesSensor(hass, entry.entry_id, title),
            TotalAutomationsSensor(hass, entry.entry_id, title),
            TotalIntegrationsSensor(hass, entry.entry_id, title),
        ])

    # Add Ping sensors (only if enabled)
    if entry.data.get("enable_ping_sensors", True):
        ping_targets = [
            ("8.8.8.8", "Google DNS"),
            ("1.1.1.1", "Cloudflare DNS"),
            ("ping.autoh.cloud", "OnOff Automations"),
        ]

        # Add gateway ping if configured
        if entry.data.get(CONF_GATEWAY_IP):
            ping_targets.append((entry.data[CONF_GATEWAY_IP], "Gateway"))

        # Add Cloudflare tunnel ping if enabled
        if entry.data.get(CONF_CF_TUNNEL_ENABLED) and entry.data.get(CONF_CF_TUNNEL_IP):
            ping_targets.append((entry.data[CONF_CF_TUNNEL_IP], "CF Tunnel"))

        for target, name in ping_targets:
            entities.append(PingSensor(hass, entry.entry_id, title, target, name))

    async_add_entities(entities)


class AutoHCloudSensor(SensorEntity, RestoreEntity):
    """Main OnOff Automations sensor."""

    def __init__(self, hass, entry_id, title):
        """Initialize the sensor."""
        self.hass = hass
        self._entry_id = entry_id
        self._title = title
        self._attr_name = "OnOff Automations Title"
        self._attr_unique_id = f"{entry_id}_onoff_itflow_title"
        self._attr_native_value = title

    @property
    def native_value(self):
        """Return the state."""
        return self._attr_native_value

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._title)},
            name=self._title,
            manufacturer="On-Off",
            model="ITFlow Integration",
        )


class AutoHReportLastUpdatedSensor(SensorEntity):
    """Sensor showing when AutoH report was last updated."""

    def __init__(self, hass, entry_id, title):
        """Initialize the sensor."""
        self.hass = hass
        self._entry_id = entry_id
        self._title = title
        self._attr_name = "AutoH Report Last Updated"
        self._attr_unique_id = f"{entry_id}_report_last_updated"
        self._attr_device_class = SensorDeviceClass.TIMESTAMP
        self._attr_native_value = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._title)},
            name=self._title,
            manufacturer="On-Off",
            model="ITFlow Integration",
        )

    async def async_update(self):
        """Update the sensor with the last update time from ITFlow documents."""
        try:
            # This will be updated by the document update functions
            entry_data = self.hass.data.get(DOMAIN, {}).get(self._entry_id)
            if entry_data and isinstance(entry_data, dict):
                last_update = entry_data.get("last_document_update")
                if last_update:
                    self._attr_native_value = last_update
                else:
                    self._attr_native_value = datetime.now(timezone.utc)
        except Exception as err:
            _LOGGER.error("Error updating report last updated sensor: %s", err)


# =============================================================================
# SYSTEM MONITORING SENSORS
# =============================================================================


class SystemCPUUsageSensor(SensorEntity):
    """Sensor for CPU usage percentage."""

    def __init__(self, hass, entry_id, title):
        """Initialize the sensor."""
        self.hass = hass
        self._entry_id = entry_id
        self._title = title
        self._attr_name = "CPU Usage"
        self._attr_unique_id = f"{entry_id}_system_cpu_usage"
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_device_class = SensorDeviceClass.POWER_FACTOR
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:cpu-64-bit"
        self._attr_native_value = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry_id}_system_monitoring")},
            name=f"{self._title} - System Monitoring",
            manufacturer="AutoH",
            model="System Monitor",
            via_device=(DOMAIN, self._title),
        )

    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        try:
            # Use interval=None to avoid blocking call
            per_cpu = psutil.cpu_percent(interval=None, percpu=True)
            return {
                "per_cpu_usage": per_cpu,
                "cpu_count": psutil.cpu_count(),
                "cpu_count_logical": psutil.cpu_count(logical=True),
            }
        except:
            return {}

    async def async_update(self):
        """Update the sensor."""
        try:
            # Use interval=1 for accurate reading
            cpu_percent = await self.hass.async_add_executor_job(
                lambda: psutil.cpu_percent(interval=1)
            )
            self._attr_native_value = round(cpu_percent, 1)
        except Exception as err:
            _LOGGER.error("Error updating CPU usage: %s", err)
            self._attr_native_value = None


class SystemMemoryUsageSensor(SensorEntity):
    """Sensor for memory usage percentage."""

    def __init__(self, hass, entry_id, title):
        """Initialize the sensor."""
        self.hass = hass
        self._entry_id = entry_id
        self._title = title
        self._attr_name = "Memory Usage"
        self._attr_unique_id = f"{entry_id}_system_memory_usage"
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_device_class = SensorDeviceClass.POWER_FACTOR
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:memory"
        self._attr_native_value = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry_id}_system_monitoring")},
            name=f"{self._title} - System Monitoring",
            manufacturer="AutoH",
            model="System Monitor",
            via_device=(DOMAIN, self._title),
        )

    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        try:
            mem = psutil.virtual_memory()
            return {
                "used_gb": round(mem.used / (1024**3), 2),
                "available_gb": round(mem.available / (1024**3), 2),
            }
        except:
            return {}

    async def async_update(self):
        """Update the sensor."""
        try:
            mem = await self.hass.async_add_executor_job(psutil.virtual_memory)
            self._attr_native_value = round(mem.percent, 1)
        except Exception as err:
            _LOGGER.error("Error updating memory usage: %s", err)
            self._attr_native_value = None


class SystemMemoryFreeSensor(SensorEntity):
    """Sensor for free memory."""

    def __init__(self, hass, entry_id, title):
        """Initialize the sensor."""
        self.hass = hass
        self._entry_id = entry_id
        self._title = title
        self._attr_name = "Memory Free"
        self._attr_unique_id = f"{entry_id}_system_memory_free"
        self._attr_native_unit_of_measurement = UnitOfInformation.GIGABYTES
        self._attr_device_class = SensorDeviceClass.DATA_SIZE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:memory"
        self._attr_native_value = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry_id}_system_monitoring")},
            name=f"{self._title} - System Monitoring",
            manufacturer="AutoH",
            model="System Monitor",
            via_device=(DOMAIN, self._title),
        )

    async def async_update(self):
        """Update the sensor."""
        try:
            mem = await self.hass.async_add_executor_job(psutil.virtual_memory)
            self._attr_native_value = round(mem.available / (1024**3), 2)
        except Exception as err:
            _LOGGER.error("Error updating free memory: %s", err)
            self._attr_native_value = None


class SystemMemoryTotalSensor(SensorEntity):
    """Sensor for total memory."""

    def __init__(self, hass, entry_id, title):
        """Initialize the sensor."""
        self.hass = hass
        self._entry_id = entry_id
        self._title = title
        self._attr_name = "Memory Total"
        self._attr_unique_id = f"{entry_id}_system_memory_total"
        self._attr_native_unit_of_measurement = UnitOfInformation.GIGABYTES
        self._attr_device_class = SensorDeviceClass.DATA_SIZE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:memory"
        self._attr_native_value = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry_id}_system_monitoring")},
            name=f"{self._title} - System Monitoring",
            manufacturer="AutoH",
            model="System Monitor",
            via_device=(DOMAIN, self._title),
        )

    async def async_update(self):
        """Update the sensor."""
        try:
            mem = await self.hass.async_add_executor_job(psutil.virtual_memory)
            self._attr_native_value = round(mem.total / (1024**3), 2)
        except Exception as err:
            _LOGGER.error("Error updating total memory: %s", err)
            self._attr_native_value = None


class SystemDiskUsageSensor(SensorEntity):
    """Sensor for disk usage percentage."""

    def __init__(self, hass, entry_id, title):
        """Initialize the sensor."""
        self.hass = hass
        self._entry_id = entry_id
        self._title = title
        self._attr_name = "Disk Usage"
        self._attr_unique_id = f"{entry_id}_system_disk_usage"
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_device_class = SensorDeviceClass.POWER_FACTOR
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:harddisk"
        self._attr_native_value = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry_id}_system_monitoring")},
            name=f"{self._title} - System Monitoring",
            manufacturer="AutoH",
            model="System Monitor",
            via_device=(DOMAIN, self._title),
        )

    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        try:
            disk = psutil.disk_usage("/")
            return {
                "used_gb": round(disk.used / (1024**3), 2),
                "free_gb": round(disk.free / (1024**3), 2),
            }
        except:
            return {}

    async def async_update(self):
        """Update the sensor."""
        try:
            disk = await self.hass.async_add_executor_job(lambda: psutil.disk_usage("/"))
            self._attr_native_value = round(disk.percent, 1)
        except Exception as err:
            _LOGGER.error("Error updating disk usage: %s", err)
            self._attr_native_value = None


class SystemDiskFreeSensor(SensorEntity):
    """Sensor for free disk space."""

    def __init__(self, hass, entry_id, title):
        """Initialize the sensor."""
        self.hass = hass
        self._entry_id = entry_id
        self._title = title
        self._attr_name = "Disk Free"
        self._attr_unique_id = f"{entry_id}_system_disk_free"
        self._attr_native_unit_of_measurement = UnitOfInformation.GIGABYTES
        self._attr_device_class = SensorDeviceClass.DATA_SIZE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:harddisk"
        self._attr_native_value = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry_id}_system_monitoring")},
            name=f"{self._title} - System Monitoring",
            manufacturer="AutoH",
            model="System Monitor",
            via_device=(DOMAIN, self._title),
        )

    async def async_update(self):
        """Update the sensor."""
        try:
            disk = await self.hass.async_add_executor_job(lambda: psutil.disk_usage("/"))
            self._attr_native_value = round(disk.free / (1024**3), 2)
        except Exception as err:
            _LOGGER.error("Error updating free disk space: %s", err)
            self._attr_native_value = None


class SystemDiskTotalSensor(SensorEntity):
    """Sensor for total disk space."""

    def __init__(self, hass, entry_id, title):
        """Initialize the sensor."""
        self.hass = hass
        self._entry_id = entry_id
        self._title = title
        self._attr_name = "Disk Total"
        self._attr_unique_id = f"{entry_id}_system_disk_total"
        self._attr_native_unit_of_measurement = UnitOfInformation.GIGABYTES
        self._attr_device_class = SensorDeviceClass.DATA_SIZE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:harddisk"
        self._attr_native_value = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry_id}_system_monitoring")},
            name=f"{self._title} - System Monitoring",
            manufacturer="AutoH",
            model="System Monitor",
            via_device=(DOMAIN, self._title),
        )

    async def async_update(self):
        """Update the sensor."""
        try:
            disk = await self.hass.async_add_executor_job(lambda: psutil.disk_usage("/"))
            self._attr_native_value = round(disk.total / (1024**3), 2)
        except Exception as err:
            _LOGGER.error("Error updating total disk space: %s", err)
            self._attr_native_value = None


class SystemLoadAvgSensor(SensorEntity):
    """Sensor for system load average."""

    def __init__(self, hass, entry_id, title):
        """Initialize the sensor."""
        self.hass = hass
        self._entry_id = entry_id
        self._title = title
        self._attr_name = "Load Average"
        self._attr_unique_id = f"{entry_id}_system_load_avg"
        self._attr_icon = "mdi:chart-line"
        self._attr_native_value = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry_id}_system_monitoring")},
            name=f"{self._title} - System Monitoring",
            manufacturer="AutoH",
            model="System Monitor",
            via_device=(DOMAIN, self._title),
        )

    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        try:
            load1, load5, load15 = psutil.getloadavg()
            return {
                "load_1min": round(load1, 2),
                "load_5min": round(load5, 2),
                "load_15min": round(load15, 2),
            }
        except:
            return {}

    async def async_update(self):
        """Update the sensor."""
        try:
            load1, _, _ = await self.hass.async_add_executor_job(psutil.getloadavg)
            self._attr_native_value = round(load1, 2)
        except Exception as err:
            _LOGGER.error("Error updating load average: %s", err)
            self._attr_native_value = None


class SystemProcessCountSensor(SensorEntity):
    """Sensor for process count."""

    def __init__(self, hass, entry_id, title):
        """Initialize the sensor."""
        self.hass = hass
        self._entry_id = entry_id
        self._title = title
        self._attr_name = "Process Count"
        self._attr_unique_id = f"{entry_id}_system_process_count"
        self._attr_icon = "mdi:application-cog"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_value = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry_id}_system_monitoring")},
            name=f"{self._title} - System Monitoring",
            manufacturer="AutoH",
            model="System Monitor",
            via_device=(DOMAIN, self._title),
        )

    async def async_update(self):
        """Update the sensor."""
        try:
            pids = await self.hass.async_add_executor_job(psutil.pids)
            self._attr_native_value = len(pids)
        except Exception as err:
            _LOGGER.error("Error updating process count: %s", err)
            self._attr_native_value = None


class SystemCPUTemperatureSensor(SensorEntity):
    """Sensor for CPU temperature."""

    def __init__(self, hass, entry_id, title):
        """Initialize the sensor."""
        self.hass = hass
        self._entry_id = entry_id
        self._title = title
        self._attr_name = "CPU Temperature"
        self._attr_unique_id = f"{entry_id}_system_cpu_temperature"
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:thermometer"
        self._attr_native_value = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry_id}_system_monitoring")},
            name=f"{self._title} - System Monitoring",
            manufacturer="AutoH",
            model="System Monitor",
            via_device=(DOMAIN, self._title),
        )

    async def async_update(self):
        """Update the sensor."""
        try:
            temps = await self.hass.async_add_executor_job(psutil.sensors_temperatures)
            if temps:
                # Try to find CPU temp
                for name, entries in temps.items():
                    if "coretemp" in name.lower() or "cpu" in name.lower() or "k10temp" in name.lower():
                        if entries:
                            self._attr_native_value = round(entries[0].current, 1)
                            return
                # If no CPU-specific temp found, use first available
                first_sensor = list(temps.values())[0]
                if first_sensor:
                    self._attr_native_value = round(first_sensor[0].current, 1)
                    return
            self._attr_native_value = None
        except Exception as err:
            _LOGGER.debug("Error updating CPU temperature (may not be available): %s", err)
            self._attr_native_value = None


class SystemUptimeSensor(SensorEntity):
    """Sensor for system uptime."""

    def __init__(self, hass, entry_id, title):
        """Initialize the sensor."""
        self.hass = hass
        self._entry_id = entry_id
        self._title = title
        self._attr_name = "System Uptime"
        self._attr_unique_id = f"{entry_id}_system_uptime"
        self._attr_device_class = SensorDeviceClass.TIMESTAMP
        self._attr_icon = "mdi:clock-outline"
        self._attr_native_value = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry_id}_system_monitoring")},
            name=f"{self._title} - System Monitoring",
            manufacturer="AutoH",
            model="System Monitor",
            via_device=(DOMAIN, self._title),
        )

    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        try:
            import time
            boot_time = psutil.boot_time()
            uptime_seconds = time.time() - boot_time
            days = int(uptime_seconds // 86400)
            hours = int((uptime_seconds % 86400) // 3600)
            minutes = int((uptime_seconds % 3600) // 60)
            return {
                "uptime_days": days,
                "uptime_hours": hours,
                "uptime_minutes": minutes,
                "uptime_human": f"{days}d {hours}h {minutes}m",
            }
        except:
            return {}

    async def async_update(self):
        """Update the sensor."""
        try:
            boot_time = await self.hass.async_add_executor_job(psutil.boot_time)
            self._attr_native_value = datetime.fromtimestamp(boot_time, tz=timezone.utc)
        except Exception as err:
            _LOGGER.error("Error updating system uptime: %s", err)
            self._attr_native_value = None


class SystemLastRebootSensor(SensorEntity):
    """Sensor for system last reboot time."""

    def __init__(self, hass, entry_id, title):
        """Initialize the sensor."""
        self.hass = hass
        self._entry_id = entry_id
        self._title = title
        self._attr_name = "System Last Reboot"
        self._attr_unique_id = f"{entry_id}_system_last_reboot"
        self._attr_device_class = SensorDeviceClass.TIMESTAMP
        self._attr_icon = "mdi:restart"
        self._attr_native_value = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry_id}_system_monitoring")},
            name=f"{self._title} - System Monitoring",
            manufacturer="AutoH",
            model="System Monitor",
            via_device=(DOMAIN, self._title),
        )

    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        try:
            import time
            boot_time = psutil.boot_time()
            boot_dt = datetime.fromtimestamp(boot_time, tz=timezone.utc)
            return {
                "boot_timestamp": boot_time,
                "boot_time_local": boot_dt.astimezone().strftime('%m/%d/%Y at %I:%M %p'),
                "boot_time_utc": boot_dt.strftime('%m/%d/%Y at %I:%M %p'),
            }
        except:
            return {}

    async def async_update(self):
        """Update the sensor."""
        try:
            boot_time = await self.hass.async_add_executor_job(psutil.boot_time)
            self._attr_native_value = datetime.fromtimestamp(boot_time, tz=timezone.utc)
        except Exception as err:
            _LOGGER.error("Error updating system last reboot: %s", err)
            self._attr_native_value = None


class SystemHALastRebootSensor(SensorEntity, RestoreEntity):
    """Sensor for Home Assistant last restart time."""

    def __init__(self, hass, entry_id, title):
        """Initialize the sensor."""
        self.hass = hass
        self._entry_id = entry_id
        self._title = title
        self._attr_name = "HA Last Reboot"
        self._attr_unique_id = f"{entry_id}_ha_last_reboot"
        self._attr_device_class = SensorDeviceClass.TIMESTAMP
        self._attr_icon = "mdi:home-assistant"
        self._attr_native_value = None
        self._ha_start_time = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry_id}_system_monitoring")},
            name=f"{self._title} - System Monitoring",
            manufacturer="AutoH",
            model="System Monitor",
            via_device=(DOMAIN, self._title),
        )

    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        if self._ha_start_time:
            return {
                "ha_start_timestamp": self._ha_start_time.timestamp(),
                "ha_start_local": self._ha_start_time.astimezone().strftime('%m/%d/%Y at %I:%M %p'),
                "ha_start_utc": self._ha_start_time.strftime('%m/%d/%Y at %I:%M %p'),
            }
        return {}

    async def async_added_to_hass(self):
        """Restore previous state when added to hass."""
        await super().async_added_to_hass()

        # Set HA start time to now when first added
        if not self._ha_start_time:
            self._ha_start_time = datetime.now(timezone.utc)
            self._attr_native_value = self._ha_start_time

        # Listen for HA start event to update timestamp
        async def ha_started_listener(event):
            """Update HA start time when HA restarts."""
            self._ha_start_time = datetime.now(timezone.utc)
            self._attr_native_value = self._ha_start_time
            self.async_write_ha_state()
            _LOGGER.info("HA restarted at: %s", self._ha_start_time)

        self.hass.bus.async_listen("homeassistant_start", ha_started_listener)

        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in (None, "Unknown", "unavailable"):
            try:
                self._ha_start_time = datetime.fromisoformat(last_state.state.replace('Z', '+00:00'))
                self._attr_native_value = self._ha_start_time
            except:
                pass

    async def async_update(self):
        """Update is handled by event listener."""
        pass


class SystemOSLastRebootSensor(SensorEntity):
    """Sensor for operating system last reboot time (same as System Last Reboot)."""

    def __init__(self, hass, entry_id, title):
        """Initialize the sensor."""
        self.hass = hass
        self._entry_id = entry_id
        self._title = title
        self._attr_name = "OS Last Reboot"
        self._attr_unique_id = f"{entry_id}_os_last_reboot"
        self._attr_device_class = SensorDeviceClass.TIMESTAMP
        self._attr_icon = "mdi:restart-alert"
        self._attr_native_value = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry_id}_system_monitoring")},
            name=f"{self._title} - System Monitoring",
            manufacturer="AutoH",
            model="System Monitor",
            via_device=(DOMAIN, self._title),
        )

    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        try:
            import time
            boot_time = psutil.boot_time()
            boot_dt = datetime.fromtimestamp(boot_time, tz=timezone.utc)
            uptime_seconds = time.time() - boot_time
            days = int(uptime_seconds // 86400)
            hours = int((uptime_seconds % 86400) // 3600)
            minutes = int((uptime_seconds % 3600) // 60)
            return {
                "boot_timestamp": boot_time,
                "boot_time_local": boot_dt.astimezone().strftime('%m/%d/%Y at %I:%M %p'),
                "boot_time_utc": boot_dt.strftime('%m/%d/%Y at %I:%M %p'),
                "uptime_days": days,
                "uptime_hours": hours,
                "uptime_minutes": minutes,
                "uptime_human": f"{days}d {hours}h {minutes}m",
            }
        except:
            return {}

    async def async_update(self):
        """Update the sensor."""
        try:
            boot_time = await self.hass.async_add_executor_job(psutil.boot_time)
            self._attr_native_value = datetime.fromtimestamp(boot_time, tz=timezone.utc)
        except Exception as err:
            _LOGGER.error("Error updating OS last reboot: %s", err)
            self._attr_native_value = None


class SystemVersionInstalledSensor(SensorEntity):
    """Sensor for installed Home Assistant version."""

    def __init__(self, hass, entry_id, title):
        """Initialize the sensor."""
        self.hass = hass
        self._entry_id = entry_id
        self._title = title
        self._attr_name = "HA Version Installed"
        self._attr_unique_id = f"{entry_id}_ha_version_installed"
        self._attr_icon = "mdi:home-assistant"
        self._attr_native_value = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry_id}_system_monitoring")},
            name=f"{self._title} - System Monitoring",
            manufacturer="AutoH",
            model="System Monitor",
            via_device=(DOMAIN, self._title),
        )

    async def async_update(self):
        """Update the sensor."""
        try:
            from homeassistant.const import __version__
            self._attr_native_value = __version__
        except Exception as err:
            _LOGGER.error("Error getting installed version: %s", err)
            self._attr_native_value = "Unknown"


class SystemVersionLatestSensor(SensorEntity):
    """Sensor for latest stable Home Assistant version with release information."""

    def __init__(self, hass, entry_id, title):
        """Initialize the sensor."""
        self.hass = hass
        self._entry_id = entry_id
        self._title = title
        self._attr_name = "HA Version Latest"
        self._attr_unique_id = f"{entry_id}_ha_version_latest"
        self._attr_icon = "mdi:home-assistant"
        self._attr_native_value = None
        self._release_date = None
        self._release_url = None
        self._release_summary = None
        self._ticket_created_for_version = None  # Track if ticket was created

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry_id}_system_monitoring")},
            name=f"{self._title} - System Monitoring",
            manufacturer="AutoH",
            model="System Monitor",
            via_device=(DOMAIN, self._title),
        )

    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        attrs = {}
        if self._release_date:
            attrs["release_date"] = self._release_date
            try:
                # Parse and format the date
                from datetime import datetime
                dt = datetime.fromisoformat(self._release_date.replace('Z', '+00:00'))
                attrs["release_date_formatted"] = dt.strftime('%m/%d/%Y at %I:%M %p')
            except:
                pass
        if self._release_url:
            attrs["release_url"] = self._release_url
        if self._release_summary:
            attrs["release_summary"] = self._release_summary
        if self._ticket_created_for_version:
            attrs["ticket_created_for_version"] = self._ticket_created_for_version
        return attrs

    async def async_update(self):
        """Update the sensor."""
        try:
            # First get version from PyPI
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://pypi.org/pypi/homeassistant/json", timeout=10
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        version = data.get("info", {}).get("version", "Unknown")
                        self._attr_native_value = version

                        # Try to get release date from PyPI release data
                        releases = data.get("releases", {})
                        if version in releases and releases[version]:
                            # Get the first release entry for this version
                            release_info = releases[version][0]
                            self._release_date = release_info.get("upload_time")

                        # Try to fetch release notes from GitHub
                        if version != "Unknown":
                            try:
                                async with session.get(
                                    f"https://api.github.com/repos/home-assistant/core/releases/tags/{version}",
                                    timeout=10
                                ) as gh_response:
                                    if gh_response.status == 200:
                                        gh_data = await gh_response.json()
                                        self._release_url = gh_data.get("html_url")
                                        # Get first 200 chars of release notes
                                        body = gh_data.get("body", "")
                                        if body:
                                            self._release_summary = body[:200] + "..." if len(body) > 200 else body
                                        if not self._release_date:
                                            self._release_date = gh_data.get("published_at")
                            except:
                                pass
                    else:
                        self._attr_native_value = "Unknown"
        except Exception as err:
            _LOGGER.debug("Error fetching latest version: %s", err)
            self._attr_native_value = "Unknown"

    def mark_ticket_created(self, version: str):
        """Mark that a ticket was created for this version."""
        self._ticket_created_for_version = version
        self.async_write_ha_state()


class SystemPublicIPSensor(RestoreEntity, SensorEntity):
    """Sensor for public IP address with change tracking."""

    def __init__(self, hass, entry_id, title):
        """Initialize the sensor."""
        self.hass = hass
        self._entry_id = entry_id
        self._title = title
        self._attr_name = "Public IP"
        self._attr_unique_id = f"{entry_id}_public_ip"
        self._attr_icon = "mdi:web"
        self._attr_native_value = None
        self._last_change = None
        self._previous_ip = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry_id}_system_monitoring")},
            name=f"{self._title} - System Monitoring",
            manufacturer="AutoH",
            model="System Monitor",
            via_device=(DOMAIN, self._title),
        )

    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        attrs = {}
        if self._last_change:
            attrs["last_change"] = self._last_change.isoformat()
            attrs["last_change_formatted"] = self._last_change.strftime('%m/%d/%Y at %I:%M %p')
        if self._previous_ip:
            attrs["previous_ip"] = self._previous_ip
        return attrs

    async def async_added_to_hass(self):
        """Restore previous state when added to hass."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in (None, "Unknown", "unavailable"):
            self._attr_native_value = last_state.state
            if last_state.attributes:
                last_change_str = last_state.attributes.get("last_change")
                if last_change_str:
                    try:
                        self._last_change = datetime.fromisoformat(last_change_str)
                    except:
                        pass
                self._previous_ip = last_state.attributes.get("previous_ip")

    async def async_update(self):
        """Update the sensor."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://api.ipify.org", timeout=5) as response:
                    if response.status == 200:
                        new_ip = await response.text()
                        # Check if IP changed
                        if self._attr_native_value and self._attr_native_value != "Unknown" and new_ip != self._attr_native_value:
                            _LOGGER.info("Public IP changed from %s to %s", self._attr_native_value, new_ip)
                            self._previous_ip = self._attr_native_value
                            self._last_change = datetime.now(timezone.utc)
                        elif not self._last_change and new_ip and new_ip != "Unknown":
                            # First time getting IP, set last_change to now
                            self._last_change = datetime.now(timezone.utc)
                        self._attr_native_value = new_ip
                    else:
                        self._attr_native_value = "Unknown"
        except Exception as err:
            _LOGGER.debug("Error fetching public IP: %s", err)
            self._attr_native_value = "Unknown"


class SystemLocalIPSensor(RestoreEntity, SensorEntity):
    """Sensor for local IP address with change tracking."""

    def __init__(self, hass, entry_id, title):
        """Initialize the sensor."""
        self.hass = hass
        self._entry_id = entry_id
        self._title = title
        self._attr_name = "Local IP"
        self._attr_unique_id = f"{entry_id}_local_ip"
        self._attr_icon = "mdi:ip-network"
        self._attr_native_value = None
        self._last_change = None
        self._previous_ip = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry_id}_system_monitoring")},
            name=f"{self._title} - System Monitoring",
            manufacturer="AutoH",
            model="System Monitor",
            via_device=(DOMAIN, self._title),
        )

    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        attrs = {}
        if self._last_change:
            attrs["last_change"] = self._last_change.isoformat()
            attrs["last_change_formatted"] = self._last_change.strftime('%m/%d/%Y at %I:%M %p')
        if self._previous_ip:
            attrs["previous_ip"] = self._previous_ip
        return attrs

    async def async_added_to_hass(self):
        """Restore previous state when added to hass."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in (None, "Unknown", "unavailable"):
            self._attr_native_value = last_state.state
            if last_state.attributes:
                last_change_str = last_state.attributes.get("last_change")
                if last_change_str:
                    try:
                        self._last_change = datetime.fromisoformat(last_change_str)
                    except:
                        pass
                self._previous_ip = last_state.attributes.get("previous_ip")

    async def async_update(self):
        """Update the sensor."""
        try:
            local_ip = str(self.hass.config.api.local_ip) if self.hass.config.api else "Unknown"
            # Check if IP changed
            if self._attr_native_value and self._attr_native_value != "Unknown" and local_ip != self._attr_native_value:
                _LOGGER.info("Local IP changed from %s to %s", self._attr_native_value, local_ip)
                self._previous_ip = self._attr_native_value
                self._last_change = datetime.now(timezone.utc)
            elif not self._last_change and local_ip and local_ip != "Unknown":
                # First time getting IP, set last_change to now
                self._last_change = datetime.now(timezone.utc)
            self._attr_native_value = local_ip
        except Exception as err:
            _LOGGER.error("Error getting local IP: %s", err)
            self._attr_native_value = "Unknown"


class SystemHAIDSensor(SensorEntity):
    """Sensor for Home Assistant installation ID."""

    def __init__(self, hass, entry_id, title):
        """Initialize the sensor."""
        self.hass = hass
        self._entry_id = entry_id
        self._title = title
        self._attr_name = "HA ID"
        self._attr_unique_id = f"{entry_id}_ha_id"
        self._attr_icon = "mdi:identifier"
        self._attr_native_value = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry_id}_system_monitoring")},
            name=f"{self._title} - System Monitoring",
            manufacturer="AutoH",
            model="System Monitor",
            via_device=(DOMAIN, self._title),
        )

    async def async_update(self):
        """Update the sensor."""
        try:
            # Try to get the HA instance ID from core.uuid
            ha_id = await self.hass.async_add_executor_job(
                lambda: self.hass.data.get("core.uuid")
            )
            if ha_id:
                self._attr_native_value = ha_id
            else:
                # Fallback: try to get from config entry
                from homeassistant.helpers import instance_id
                ha_id = await instance_id.async_get(self.hass)
                self._attr_native_value = ha_id if ha_id else "Unknown"
        except Exception as err:
            _LOGGER.error("Error getting HA ID: %s", err)
            self._attr_native_value = "Unknown"


# =============================================================================
# PING SENSORS
# =============================================================================


class PingSensor(SensorEntity):
    """Sensor for ping monitoring (binary: reachable/unreachable)."""

    def __init__(self, hass, entry_id, title, target, name):
        """Initialize the sensor."""
        self.hass = hass
        self._entry_id = entry_id
        self._title = title
        self._target = target
        self._name = name
        self._attr_name = f"Ping {name}"
        self._attr_unique_id = f"{entry_id}_ping_{target.replace('.', '_').replace(':', '_')}"
        self._attr_icon = "mdi:lan-connect"
        self._attr_native_value = False
        self._ping_times = []

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry_id}_ping_monitoring")},
            name=f"{self._title} - Ping Results",
            manufacturer="AutoH",
            model="Network Monitor",
            via_device=(DOMAIN, self._title),
        )

    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        attrs = {
            "target": self._target,
            "target_name": self._name,
        }

        if self._ping_times:
            attrs["average_ms"] = round(sum(self._ping_times) / len(self._ping_times), 2)
            attrs["min_ms"] = min(self._ping_times)
            attrs["max_ms"] = max(self._ping_times)
            attrs["last_ms"] = self._ping_times[-1]
        else:
            attrs["average_ms"] = None

        return attrs

    async def async_update(self):
        """Update the sensor."""
        try:
            # Determine ping command based on OS
            param = "-n" if platform.system().lower() == "windows" else "-c"
            command = ["ping", param, "4", "-w" if platform.system().lower() == "windows" else "-W", "1000" if platform.system().lower() == "windows" else "1", self._target]

            result = await self.hass.async_add_executor_job(
                lambda: subprocess.run(
                    command, capture_output=True, text=True, timeout=5
                )
            )

            if result.returncode == 0:
                # Parse ping times from output
                output = result.stdout
                times = []
                for line in output.split('\n'):
                    if "time=" in line:
                        try:
                            time_str = line.split("time=")[1].split()[0]
                            time_val = float(time_str.replace("ms", ""))
                            times.append(time_val)
                        except:
                            pass

                if times:
                    self._ping_times = times
                    self._attr_native_value = True
                else:
                    self._attr_native_value = True  # Ping succeeded but couldn't parse time
            else:
                self._attr_native_value = False
                self._ping_times = []

        except Exception as err:
            _LOGGER.debug("Error pinging %s: %s", self._target, err)
            self._attr_native_value = False
            self._ping_times = []


# =============================================================================
# ITFLOW SENSORS
# =============================================================================


class ITFlowTicketSensor(SensorEntity, RestoreEntity):
    """Sensor for creating ITFlow tickets from the dashboard."""

    def __init__(self, hass, entry_id, title):
        """Initialize the ITFlow ticket sensor."""
        self.hass = hass
        self._entry_id = entry_id
        self._title = title
        self._attr_name = "ITFlow Create Ticket"
        self._attr_unique_id = f"{entry_id}_itflow_create_ticket"
        self._attr_native_value = "Ready"
        self._ticket_subject = ""
        self._ticket_details = ""
        self._ticket_priority = "Low"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._attr_native_value

    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        return {
            "ticket_subject": self._ticket_subject,
            "ticket_details": self._ticket_details,
            "ticket_priority": self._ticket_priority,
        }

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._title)},
            name=self._title,
            manufacturer="On-Off",
            model="ITFlow Integration",
        )

    async def async_set_ticket_data(
        self, subject: str, details: str, priority: str = "Low"
    ):
        """Set ticket data and create the ticket."""
        self._ticket_subject = subject
        self._ticket_details = details
        self._ticket_priority = priority
        self._attr_native_value = "Creating ticket..."
        self.async_write_ha_state()

        # Create the ticket
        try:
            await self.hass.services.async_call(
                DOMAIN,
                "create_ticket",
                {
                    "ticket_subject": subject,
                    "ticket_details": details,
                    "ticket_priority": priority,
                },
                blocking=True,
            )
            self._attr_native_value = "Ticket created"
        except Exception as err:
            self._attr_native_value = f"Error: {err}"

        self.async_write_ha_state()

        # Reset to ready after 5 seconds
        async def reset_state():
            await asyncio.sleep(5)
            self._attr_native_value = "Ready"
            self.async_write_ha_state()

        self.hass.async_create_task(reset_state())


class ITFlowNewTicketsSensor(SensorEntity, RestoreEntity):
    """Sensor that displays all new ITFlow tickets (status 1)."""

    def __init__(self, hass, entry_id, title):
        """Initialize the new tickets sensor."""
        self.hass = hass
        self._entry_id = entry_id
        self._title = title
        self._attr_name = "ITFlow New Tickets"
        self._attr_unique_id = f"{entry_id}_itflow_new_tickets"
        self._attr_native_value = 0
        self._tickets = []

    @property
    def native_value(self):
        """Return the number of new tickets."""
        return self._attr_native_value

    @property
    def extra_state_attributes(self):
        """Return ticket details as attributes with dynamic size reduction."""
        return build_ticket_attributes_with_size_check(self._tickets, include_tickets_array=False)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._title)},
            name=self._title,
            manufacturer="On-Off",
            model="ITFlow Integration",
        )

    async def async_update(self):
        """Fetch new tickets from ITFlow (status 1 only)."""
        try:
            entry_data = self.hass.data.get(DOMAIN, {}).get(self._entry_id)
            if not entry_data or not isinstance(entry_data, dict):
                return

            client = entry_data.get("itflow_client")
            if not client:
                return

            # Only fetch tickets with status 1 (New)
            all_new_tickets = []

            for status in ["1", "New"]:
                try:
                    response = await client.get_tickets(status=status)
                    if response.get("success"):
                        tickets = response.get("data", [])
                        # Only add tickets with status_raw = 1
                        for ticket in tickets:
                            ticket_id = ticket.get("ticket_id")
                            raw_status = str(ticket.get("ticket_status", ""))
                            if raw_status == "1" and ticket_id and not any(t.get("ticket_id") == ticket_id for t in all_new_tickets):
                                all_new_tickets.append(ticket)
                except Exception as e:
                    _LOGGER.debug("Error fetching tickets with status %s: %s", status, e)
                    continue

            # Sort by ticket_created_at descending (newest first)
            all_new_tickets.sort(
                key=lambda x: x.get("ticket_created_at", ""),
                reverse=True
            )

            self._tickets = all_new_tickets
            self._attr_native_value = len(self._tickets)

        except Exception as err:
            _LOGGER.error("Error fetching new tickets: %s", err)
            self._tickets = []
            self._attr_native_value = 0


class ITFlowOpenTicketsSensor(SensorEntity, RestoreEntity):
    """Sensor that displays all open ITFlow tickets."""

    def __init__(self, hass, entry_id, title):
        """Initialize the open tickets sensor."""
        self.hass = hass
        self._entry_id = entry_id
        self._title = title
        self._attr_name = "ITFlow Open Tickets"
        self._attr_unique_id = f"{entry_id}_itflow_open_tickets"
        self._attr_native_value = 0
        self._tickets = []

    @property
    def native_value(self):
        """Return the number of open tickets."""
        return self._attr_native_value

    @property
    def extra_state_attributes(self):
        """Return ticket details as attributes with dynamic size reduction."""
        return build_ticket_attributes_with_size_check(self._tickets, include_tickets_array=False)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._title)},
            name=self._title,
            manufacturer="On-Off",
            model="ITFlow Integration",
        )

    async def async_update(self):
        """Fetch open tickets from ITFlow (includes New tickets, excludes Resolved/Closed)."""
        try:
            entry_data = self.hass.data.get(DOMAIN, {}).get(self._entry_id)
            if not entry_data or not isinstance(entry_data, dict):
                return

            client = entry_data.get("itflow_client")
            if not client:
                return

            # Get all tickets and filter for open (status 1=New, 2=Open, 3=On Hold)
            # Exclude 4=Resolved and 5=Closed
            all_tickets = []

            for status in ["1", "2", "3", "New", "Open", "On Hold"]:
                try:
                    response = await client.get_tickets(status=status)

                    if response.get("success"):
                        tickets = response.get("data", [])
                        for ticket in tickets:
                            ticket_id = ticket.get("ticket_id")
                            raw_status = str(ticket.get("ticket_status", ""))
                            # Only include if status is not 4 (Resolved) or 5 (Closed)
                            if raw_status not in ["4", "5"] and ticket_id and not any(t.get("ticket_id") == ticket_id for t in all_tickets):
                                all_tickets.append(ticket)
                except Exception as e:
                    _LOGGER.debug("Error fetching tickets with status %s: %s", status, e)
                    continue

            # Sort by ticket_created_at descending (newest first)
            all_tickets.sort(
                key=lambda x: x.get("ticket_created_at", ""),
                reverse=True
            )

            self._tickets = all_tickets
            self._attr_native_value = len(self._tickets)

        except Exception as err:
            _LOGGER.error("Error fetching open tickets: %s", err)
            self._tickets = []
            self._attr_native_value = 0


class ITFlowClosedTicketsSensor(SensorEntity, RestoreEntity):
    """Sensor that displays all closed ITFlow tickets (status 5 only)."""

    def __init__(self, hass, entry_id, title):
        """Initialize the closed tickets sensor."""
        self.hass = hass
        self._entry_id = entry_id
        self._title = title
        self._attr_name = "ITFlow Closed Tickets"
        self._attr_unique_id = f"{entry_id}_itflow_closed_tickets"
        self._attr_native_value = 0
        self._tickets = []

    @property
    def native_value(self):
        """Return the number of closed tickets."""
        return self._attr_native_value

    @property
    def extra_state_attributes(self):
        """Return ticket details as attributes with dynamic size reduction."""
        return build_ticket_attributes_with_size_check(self._tickets, include_tickets_array=False)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._title)},
            name=self._title,
            manufacturer="On-Off",
            model="ITFlow Integration",
        )

    async def async_update(self):
        """Fetch closed tickets from ITFlow (status 5 only)."""
        try:
            entry_data = self.hass.data.get(DOMAIN, {}).get(self._entry_id)
            if not entry_data or not isinstance(entry_data, dict):
                return

            client = entry_data.get("itflow_client")
            if not client:
                return

            # Only fetch tickets with status 5 (Closed)
            all_closed_tickets = []

            for status in ["5", "Closed"]:
                try:
                    response = await client.get_tickets(status=status)
                    if response.get("success"):
                        tickets = response.get("data", [])
                        # Only add tickets with status_raw = 5
                        for ticket in tickets:
                            ticket_id = ticket.get("ticket_id")
                            raw_status = str(ticket.get("ticket_status", ""))
                            if raw_status == "5" and ticket_id and not any(t.get("ticket_id") == ticket_id for t in all_closed_tickets):
                                all_closed_tickets.append(ticket)
                except Exception as e:
                    _LOGGER.debug("Error fetching tickets with status %s: %s", status, e)
                    continue

            # Sort by ticket_created_at descending (newest first)
            all_closed_tickets.sort(
                key=lambda x: x.get("ticket_created_at", ""),
                reverse=True
            )

            self._tickets = all_closed_tickets
            self._attr_native_value = len(self._tickets)

        except Exception as err:
            _LOGGER.error("Error fetching closed tickets: %s", err)
            self._tickets = []
            self._attr_native_value = 0


class ITFlowResolvedTicketsSensor(SensorEntity, RestoreEntity):
    """Sensor that displays all resolved ITFlow tickets (status 4 only)."""

    def __init__(self, hass, entry_id, title):
        """Initialize the resolved tickets sensor."""
        self.hass = hass
        self._entry_id = entry_id
        self._title = title
        self._attr_name = "ITFlow Resolved Tickets"
        self._attr_unique_id = f"{entry_id}_itflow_resolved_tickets"
        self._attr_native_value = 0
        self._tickets = []

    @property
    def native_value(self):
        """Return the number of resolved tickets."""
        return self._attr_native_value

    @property
    def extra_state_attributes(self):
        """Return ticket details as attributes (limited to 25 most recent to avoid size issues)."""
        attributes = {}
        # Limit to 25 most recent tickets to avoid exceeding 16KB attribute limit
        limited_tickets = self._tickets[:25]

        for idx, ticket in enumerate(limited_tickets):
            ticket_id = ticket.get("ticket_id", "unknown")
            raw_status = ticket.get("ticket_status", "")
            friendly_status = map_ticket_status(raw_status)

            attributes[f"ticket_{idx + 1}_id"] = ticket_id
            attributes[f"ticket_{idx + 1}_subject"] = ticket.get("ticket_subject", "")[:100]  # Limit subject length
            attributes[f"ticket_{idx + 1}_priority"] = ticket.get("ticket_priority", "")
            attributes[f"ticket_{idx + 1}_status"] = friendly_status
            attributes[f"ticket_{idx + 1}_status_raw"] = raw_status
            attributes[f"ticket_{idx + 1}_created"] = ticket.get("ticket_created_at", "")
            attributes[f"ticket_{idx + 1}_resolved"] = ticket.get("ticket_resolved_at", "")
            attributes[f"ticket_{idx + 1}_details"] = ticket.get("ticket_details", "")[:100]  # Reduced from 200 to 100
            attributes[f"ticket_{idx + 1}_category"] = ticket.get("ticket_category", "")
            attributes[f"ticket_{idx + 1}_assigned_to"] = ticket.get("ticket_assigned_to", "")

        attributes["total_tickets"] = len(self._tickets)
        attributes["displayed_tickets"] = len(limited_tickets)
        attributes["last_updated"] = datetime.now(timezone.utc).isoformat()
        return attributes

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._title)},
            name=self._title,
            manufacturer="On-Off",
            model="ITFlow Integration",
        )

    async def async_update(self):
        """Fetch resolved tickets from ITFlow (status 4 only)."""
        try:
            entry_data = self.hass.data.get(DOMAIN, {}).get(self._entry_id)
            if not entry_data or not isinstance(entry_data, dict):
                return

            client = entry_data.get("itflow_client")
            if not client:
                return

            # Only fetch tickets with status 4 (Resolved)
            all_resolved_tickets = []

            for status in ["4", "Resolved"]:
                try:
                    response = await client.get_tickets(status=status)
                    if response.get("success"):
                        tickets = response.get("data", [])
                        # Only add tickets with status_raw = 4
                        for ticket in tickets:
                            ticket_id = ticket.get("ticket_id")
                            raw_status = str(ticket.get("ticket_status", ""))
                            if raw_status == "4" and ticket_id and not any(t.get("ticket_id") == ticket_id for t in all_resolved_tickets):
                                all_resolved_tickets.append(ticket)
                except Exception as e:
                    _LOGGER.debug("Error fetching tickets with status %s: %s", status, e)
                    continue

            # Sort by ticket_created_at descending (newest first)
            all_resolved_tickets.sort(
                key=lambda x: x.get("ticket_created_at", ""),
                reverse=True
            )

            self._tickets = all_resolved_tickets
            self._attr_native_value = len(self._tickets)

        except Exception as err:
            _LOGGER.error("Error fetching resolved tickets: %s", err)
            self._tickets = []
            self._attr_native_value = 0


class ITFlowMaintenanceTicketsSensor(SensorEntity, RestoreEntity):
    """Sensor that displays all maintenance ITFlow tickets (status 7 only)."""

    def __init__(self, hass, entry_id, title):
        """Initialize the maintenance tickets sensor."""
        self.hass = hass
        self._entry_id = entry_id
        self._title = title
        self._attr_name = "ITFlow Maintenance Tickets"
        self._attr_unique_id = f"{entry_id}_itflow_maintenance_tickets"
        self._attr_native_value = 0
        self._tickets = []

    @property
    def native_value(self):
        """Return the number of maintenance tickets."""
        return self._attr_native_value

    @property
    def extra_state_attributes(self):
        """Return ticket details as attributes with dynamic size reduction."""
        return build_ticket_attributes_with_size_check(self._tickets, include_tickets_array=False)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._title)},
            name=self._title,
            manufacturer="On-Off",
            model="ITFlow Integration",
        )

    async def async_update(self):
        """Fetch maintenance tickets from ITFlow (status 7 only)."""
        try:
            entry_data = self.hass.data.get(DOMAIN, {}).get(self._entry_id)
            if not entry_data or not isinstance(entry_data, dict):
                return

            client = entry_data.get("itflow_client")
            if not client:
                return

            # Only fetch tickets with status 7 (Maintenance)
            all_maintenance_tickets = []

            for status in ["7", "Maintenance"]:
                try:
                    response = await client.get_tickets(status=status)
                    if response.get("success"):
                        tickets = response.get("data", [])
                        # Only add tickets with status_raw = 7
                        for ticket in tickets:
                            ticket_id = ticket.get("ticket_id")
                            raw_status = str(ticket.get("ticket_status", ""))
                            if raw_status == "7" and ticket_id and not any(t.get("ticket_id") == ticket_id for t in all_maintenance_tickets):
                                all_maintenance_tickets.append(ticket)
                except Exception as e:
                    _LOGGER.debug("Error fetching tickets with status %s: %s", status, e)
                    continue

            # Sort by ticket_created_at descending (newest first)
            all_maintenance_tickets.sort(
                key=lambda x: x.get("ticket_created_at", ""),
                reverse=True
            )

            self._tickets = all_maintenance_tickets
            self._attr_native_value = len(self._tickets)

        except Exception as err:
            _LOGGER.error("Error fetching maintenance tickets: %s", err)
            self._tickets = []
            self._attr_native_value = 0


class ITFlowContactsSensor(SensorEntity, RestoreEntity):
    """Sensor for ITFlow contacts list."""

    def __init__(self, hass: HomeAssistant, entry_id: str, title: str):
        """Initialize the sensor."""
        self.hass = hass
        self._entry_id = entry_id
        self._title = title
        self._contacts = []
        self._attr_name = f"{title} Contacts"
        self._attr_unique_id = f"{entry_id}_itflow_contacts"
        self._attr_native_value = 0
        self._attr_icon = "mdi:account-multiple"

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attributes = {}
        if self._contacts:
            contacts_list = []
            for contact in self._contacts:
                contact_info = {
                    "id": contact.get("contact_id"),
                    "name": contact.get("contact_name") or "N/A",
                    "email": contact.get("contact_email") or "N/A",
                    "phone": contact.get("contact_phone") or "N/A",
                    "title": contact.get("contact_title") or "N/A",
                    "department": contact.get("contact_department") or "N/A",
                    "notes": contact.get("contact_notes") or "N/A",
                    "mobile": contact.get("contact_mobile") or "N/A",
                    "extension": contact.get("contact_extension") or "N/A",
                }
                contacts_list.append(contact_info)
            attributes["contacts"] = contacts_list

        attributes["total_contacts"] = len(self._contacts)
        attributes["last_updated"] = datetime.now(timezone.utc).isoformat()
        return attributes

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._title)},
            name=self._title,
            manufacturer="On-Off",
            model="ITFlow Integration",
        )

    async def async_update(self):
        """Fetch contacts from ITFlow."""
        try:
            entry_data = self.hass.data.get(DOMAIN, {}).get(self._entry_id)
            if not entry_data or not isinstance(entry_data, dict):
                return

            client = entry_data.get("itflow_client")
            if not client:
                return

            response = await client.get_contacts()
            if response.get("success"):
                # Filter out contacts with name "*****"
                all_contacts = response.get("data", [])
                self._contacts = [
                    contact for contact in all_contacts
                    if contact.get("contact_name") != "*****"
                ]
                self._attr_native_value = len(self._contacts)
            else:
                _LOGGER.error("Failed to fetch contacts: %s", response.get("message"))
                self._contacts = []
                self._attr_native_value = 0

        except Exception as err:
            _LOGGER.error("Error fetching contacts: %s", err)
            self._contacts = []
            self._attr_native_value = 0


class ITFlowClientsSensor(SensorEntity, RestoreEntity):
    """Sensor for all clients (master account mode)."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        """Initialize the sensor."""
        self.hass = hass
        self._entry = entry
        self._clients = []
        self._attr_name = f"{entry.data.get(CONF_NAME, 'ITFlow')} Clients"
        self._attr_unique_id = f"{entry.entry_id}_clients"
        self._attr_icon = "mdi:account-multiple"
        self._attr_native_value = 0
        self._attr_state_class = None

    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        # Create attributes dict with each client
        attributes = {}
        for client in self._clients:
            client_id = client.get("client_id")
            client_name = client.get("client_name", f"Client {client_id}")
            if client_id:
                attributes[f"client_{client_id}"] = client_name
                # Also add individual client details
                attributes[f"client_{client_id}_details"] = {
                    "id": client_id,
                    "name": client_name,
                    "location": client.get("location_name", ""),
                    "website": client.get("client_website", ""),
                    "phone": client.get("client_phone", ""),
                }

        attributes["total_clients"] = len(self._clients)
        attributes["clients_list"] = [
            {
                "id": c.get("client_id"),
                "name": c.get("client_name", f"Client {c.get('client_id')}")
            }
            for c in self._clients
        ]

        return attributes

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": self._entry.data.get(CONF_NAME, "On-Off ITFlow"),
            "manufacturer": "On-Off",
            "model": "ITFlow Integration",
        }

    async def async_added_to_hass(self) -> None:
        """Restore previous state when added to hass."""
        await super().async_added_to_hass()

        # Restore previous state
        if (state := await self.async_get_last_state()) is not None:
            self._attr_native_value = state.state
            if state.attributes:
                # Reconstruct clients list from attributes
                clients_list = state.attributes.get("clients_list", [])
                self._clients = clients_list

        # Start update cycle
        await self._update_clients()

    async def async_update(self) -> None:
        """Update the sensor."""
        await self._update_clients()

    async def _update_clients(self) -> None:
        """Fetch clients from ITFlow."""
        try:
            client = self.hass.data[DOMAIN][self._entry.entry_id].get("itflow_client")
            if not client:
                _LOGGER.error("ITFlow client not initialized")
                return

            response = await client.get_clients()

            if response.get("success"):
                self._clients = response.get("data", [])
                self._attr_native_value = len(self._clients)
                _LOGGER.debug("Fetched %d clients", len(self._clients))
            else:
                _LOGGER.error("Failed to fetch clients: %s", response.get("message"))
                self._clients = []
                self._attr_native_value = 0

        except Exception as err:
            _LOGGER.error("Error fetching clients: %s", err)
            self._clients = []
            self._attr_native_value = 0


class LoggedInUsersSensor(SensorEntity):
    """Sensor to track logged in users."""

    def __init__(self, hass: HomeAssistant, entry_id: str, title: str):
        """Initialize the sensor."""
        self.hass = hass
        self._entry_id = entry_id
        self._title = title
        self._attr_name = f"{title} Logged In Users"
        self._attr_unique_id = f"{entry_id}_logged_in_users"
        self._attr_native_value = 0
        self._users = {}
        self._attr_extra_state_attributes = {}
        self._attr_icon = "mdi:account-multiple"
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._title)},
            name=self._title,
            manufacturer="On-Off",
            model="ITFlow Integration",
        )

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        # Update immediately
        await self.async_update()
        # Schedule updates every 30 seconds
        async_track_time_interval(
            self.hass, self._async_update_data, timedelta(seconds=30)
        )

    async def _async_update_data(self, now=None) -> None:
        """Update the sensor data."""
        await self.async_update()

    async def async_update(self) -> None:
        """Update the sensor."""
        try:
            logged_in_users = {}
            active_count = 0

            # Get all users
            for user in await self.hass.auth.async_get_users():
                if user.system_generated:
                    continue

                user_name = user.name
                is_logged_in = False

                # Check if user has any active refresh tokens
                try:
                    # Access refresh tokens via the access token manager
                    refresh_token_manager = self.hass.auth._store._async_get_refresh_token_manager()
                    refresh_tokens = await self.hass.async_add_executor_job(
                        lambda: list(refresh_token_manager._refresh_tokens.values())
                    )

                    for token in refresh_tokens:
                        if token.user_id == user.id:
                            # Consider token active if it was used in the last 24 hours
                            if token.last_used_at:
                                time_since_use = datetime.now(timezone.utc) - token.last_used_at
                                if time_since_use < timedelta(hours=24):
                                    is_logged_in = True
                                    break
                except AttributeError:
                    # If refresh tokens are not accessible, skip this check
                    pass

                logged_in_users[user_name] = is_logged_in
                if is_logged_in:
                    active_count += 1

            self._users = logged_in_users
            self._attr_native_value = active_count
            self._attr_extra_state_attributes = {
                "users": logged_in_users,
                "total_users": len(logged_in_users),
                "active_users": active_count
            }

        except Exception as err:
            _LOGGER.error("Error updating logged in users sensor: %s", err, exc_info=True)
            self._attr_native_value = 0
            self._attr_extra_state_attributes = {}


class TotalEntitiesSensor(SensorEntity):
    """Sensor to track total entities."""

    def __init__(self, hass: HomeAssistant, entry_id: str, title: str):
        """Initialize the sensor."""
        self.hass = hass
        self._entry_id = entry_id
        self._title = title
        self._attr_name = f"{title} Total Entities"
        self._attr_unique_id = f"{entry_id}_total_entities"
        self._attr_native_value = 0
        self._attr_extra_state_attributes = {}
        self._attr_icon = "mdi:counter"
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry_id}_system_monitoring")},
            name=f"{self._title} - System Monitoring",
            manufacturer="AutoH",
            model="System Monitor",
            via_device=(DOMAIN, self._title),
        )

    async def async_update(self) -> None:
        """Update the sensor."""
        try:
            # Count all entities
            total_entities = len(self.hass.states.async_all())

            # Count by domain for attributes
            domain_counts = {}
            for state in self.hass.states.async_all():
                domain = state.entity_id.split('.')[0]
                domain_counts[domain] = domain_counts.get(domain, 0) + 1

            # Get top 10 domains
            top_domains = dict(sorted(domain_counts.items(), key=lambda x: x[1], reverse=True)[:10])

            self._attr_native_value = total_entities
            self._attr_extra_state_attributes = {
                "top_domains": top_domains,
                "total_domains": len(domain_counts),
            }

        except Exception as err:
            _LOGGER.error("Error updating total entities sensor: %s", err, exc_info=True)
            self._attr_native_value = 0
            self._attr_extra_state_attributes = {}


class TotalAutomationsSensor(SensorEntity):
    """Sensor to track total automations."""

    def __init__(self, hass: HomeAssistant, entry_id: str, title: str):
        """Initialize the sensor."""
        self.hass = hass
        self._entry_id = entry_id
        self._title = title
        self._attr_name = f"{title} Total Automations"
        self._attr_unique_id = f"{entry_id}_total_automations"
        self._attr_native_value = 0
        self._attr_extra_state_attributes = {}
        self._attr_icon = "mdi:robot"
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry_id}_system_monitoring")},
            name=f"{self._title} - System Monitoring",
            manufacturer="AutoH",
            model="System Monitor",
            via_device=(DOMAIN, self._title),
        )

    async def async_update(self) -> None:
        """Update the sensor."""
        try:
            # Count automations and their states
            automations = [s for s in self.hass.states.async_all() if s.entity_id.startswith('automation.')]
            automations_on = len([a for a in automations if a.state == 'on'])
            automations_off = len([a for a in automations if a.state == 'off'])

            self._attr_native_value = len(automations)
            self._attr_extra_state_attributes = {
                "active": automations_on,
                "disabled": automations_off,
                "total": len(automations),
            }

        except Exception as err:
            _LOGGER.error("Error updating total automations sensor: %s", err, exc_info=True)
            self._attr_native_value = 0
            self._attr_extra_state_attributes = {}


class TotalIntegrationsSensor(SensorEntity):
    """Sensor to track total integrations/domains."""

    def __init__(self, hass: HomeAssistant, entry_id: str, title: str):
        """Initialize the sensor."""
        self.hass = hass
        self._entry_id = entry_id
        self._title = title
        self._attr_name = f"{title} Total Integrations"
        self._attr_unique_id = f"{entry_id}_total_integrations"
        self._attr_native_value = 0
        self._attr_extra_state_attributes = {}
        self._attr_icon = "mdi:puzzle"
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry_id}_system_monitoring")},
            name=f"{self._title} - System Monitoring",
            manufacturer="AutoH",
            model="System Monitor",
            via_device=(DOMAIN, self._title),
        )

    async def async_update(self) -> None:
        """Update the sensor."""
        try:
            # Count unique domains (integrations)
            domains = set()
            for state in self.hass.states.async_all():
                domain = state.entity_id.split('.')[0]
                domains.add(domain)

            domains_list = sorted(list(domains))

            self._attr_native_value = len(domains)
            self._attr_extra_state_attributes = {
                "domains": domains_list,
                "integration_list": domains_list,  # Alias for clarity
                "total_domains": len(domains),
            }

        except Exception as err:
            _LOGGER.error("Error updating total integrations sensor: %s", err, exc_info=True)
            self._attr_native_value = 0
            self._attr_extra_state_attributes = {}
