"""Button entities for ITFlow ticket management."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, CONF_ITFLOW_ENABLED

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ITFlow button entities."""
    if not entry.data.get(CONF_ITFLOW_ENABLED, False):
        return

    title = entry.runtime_data
    entry_data = hass.data.get(DOMAIN, {}).get(entry.entry_id)

    if not entry_data or not isinstance(entry_data, dict):
        return

    # Get the open tickets sensor to watch for ticket updates
    buttons = []

    # Add manual refresh button
    buttons.append(ITFlowRefreshTicketsButton(hass, entry.entry_id, title))

    # Add manual document update button
    buttons.append(ITFlowUpdateDocumentButton(hass, entry.entry_id, title))

    async_add_entities(buttons)


class ITFlowRefreshTicketsButton(ButtonEntity):
    """Button to manually refresh ITFlow tickets."""

    def __init__(self, hass: HomeAssistant, entry_id: str, title: str):
        """Initialize the refresh button."""
        self.hass = hass
        self._entry_id = entry_id
        self._title = title
        self._attr_name = "Refresh ITFlow Tickets"
        self._attr_unique_id = f"{entry_id}_refresh_itflow_tickets"

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self._title)},
            "name": self._title,
            "manufacturer": "On-Off",
            "model": "ITFlow Integration",
        }

    async def async_press(self) -> None:
        """Handle the button press - refresh tickets."""
        # Find the open tickets sensor and trigger update
        from homeassistant.helpers import entity_component

        for entity_id in self.hass.states.async_entity_ids("sensor"):
            if "itflow_open_tickets" in entity_id:
                # Trigger sensor update
                await entity_component.async_update_entity(self.hass, entity_id)
                _LOGGER.info("Manually refreshed ITFlow tickets")
                break


class ITFlowUpdateDocumentButton(ButtonEntity):
    """Button to manually update the diagnostic document."""

    def __init__(self, hass: HomeAssistant, entry_id: str, title: str):
        """Initialize the update document button."""
        self.hass = hass
        self._entry_id = entry_id
        self._title = title
        self._attr_name = "Update Diagnostic Document"
        self._attr_unique_id = f"{entry_id}_update_document"

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self._title)},
            "name": self._title,
            "manufacturer": "On-Off",
            "model": "ITFlow Integration",
        }

    async def async_press(self) -> None:
        """Handle the button press - update all configured diagnostic documents."""
        try:
            from homeassistant.config_entries import ConfigEntry
            from datetime import datetime, timezone

            # Get config entry to access title
            entry: ConfigEntry = None
            for config_entry in self.hass.config_entries.async_entries(DOMAIN):
                if config_entry.entry_id == self._entry_id:
                    entry = config_entry
                    break

            if not entry:
                _LOGGER.error("Config entry not found")
                return

            title = entry.data.get("name", "On-Off ITFlow")

            entry_data = self.hass.data.get(DOMAIN, {}).get(self._entry_id)
            if not entry_data or not isinstance(entry_data, dict):
                _LOGGER.error("ITFlow client not found")
                return

            client = entry_data.get("itflow_client")
            if not client:
                _LOGGER.error("ITFlow client not initialized")
                return

            from .const import (
                CONF_DOC_ID_GENERAL,
                CONF_DOC_ID_AUTOMATIONS,
                CONF_DOC_ID_INTEGRATIONS,
                CONF_DOC_ID_BACKUP,
                CONF_DOC_ID_PROXMOX,
            )

            now = datetime.now()
            _LOGGER.info("Button pressed - Updating all configured document IDs")

            # Document configuration: (config_key, (method_name, doc_name))
            doc_config = {
                CONF_DOC_ID_GENERAL: ("get_system_info", f"HA General Info - {title}"),
                CONF_DOC_ID_AUTOMATIONS: ("get_automation_status", f"HA Automations - {title}"),
                CONF_DOC_ID_INTEGRATIONS: ("get_integrations_info", f"HA Integrations - {title}"),
                CONF_DOC_ID_BACKUP: ("get_backup_status", f"HA Backup Status - {title}"),
                CONF_DOC_ID_PROXMOX: ("_get_proxmox_info", f"Proxmox Info - {title}"),
            }

            updates_successful = 0
            updates_failed = 0

            # Process each document type
            for conf_key, (method_name, doc_name) in doc_config.items():
                doc_id = entry.data.get(conf_key)

                # Only update if this specific document ID is configured
                if not doc_id:
                    _LOGGER.debug("Skipping %s - no document ID configured", conf_key)
                    continue

                try:
                    # Generate content using the appropriate method
                    if method_name == "_get_proxmox_info":
                        document_content = await client._get_proxmox_info(self.hass)
                        if not document_content:
                            _LOGGER.info("Skipping Proxmox document - not enabled or no data")
                            continue
                    else:
                        method = getattr(client, method_name)
                        document_content = await method(self.hass)

                    # Update existing document
                    _LOGGER.info("Updating ONLY document ID %s (%s)", doc_id, doc_name)
                    response = await client.update_document(
                        document_id=doc_id,
                        document_name=doc_name,
                        document_content=document_content,
                        document_description=f"Manual update - {now.strftime('%Y-%m-%d %H:%M:%S')}"
                    )

                    if response.get("success"):
                        _LOGGER.info("✅ Successfully updated document ID: %s", doc_id)
                        updates_successful += 1
                    else:
                        _LOGGER.error("❌ Failed to update document %s: %s", doc_id, response)
                        updates_failed += 1

                except Exception as doc_err:
                    _LOGGER.error("Failed to update document %s: %s", conf_key, doc_err, exc_info=True)
                    updates_failed += 1

            # Update last document update timestamp
            self.hass.data[DOMAIN][entry.entry_id]["last_document_update"] = datetime.now(timezone.utc)

            # Trigger update for the AutoH Report Last Updated sensor
            try:
                entity_id = f"sensor.{entry.title.lower().replace(' ', '_')}_autoh_report_last_updated"
                _LOGGER.debug("Triggering update for sensor: %s", entity_id)
                await self.hass.helpers.entity_component.async_update_entity(entity_id)
            except Exception as update_err:
                _LOGGER.debug("Could not trigger sensor update: %s", update_err)

            _LOGGER.info("Document update completed: %d successful, %d failed", updates_successful, updates_failed)

        except Exception as err:
            _LOGGER.error("Error updating diagnostic documents: %s", err, exc_info=True)


class ITFlowTicketActionButton(ButtonEntity):
    """Base class for ticket action buttons."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        title: str,
        ticket_id: int,
        ticket_subject: str,
        action: str,
    ):
        """Initialize the ticket action button."""
        self.hass = hass
        self._entry_id = entry_id
        self._title = title
        self._ticket_id = ticket_id
        self._ticket_subject = ticket_subject
        self._action = action
        self._attr_name = f"{action} Ticket {ticket_id}"
        self._attr_unique_id = f"{entry_id}_ticket_{ticket_id}_{action.lower()}"

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self._title)},
            "name": self._title,
            "manufacturer": "On-Off",
            "model": "ITFlow Integration",
        }

    @property
    def extra_state_attributes(self):
        """Return extra attributes."""
        return {
            "ticket_id": self._ticket_id,
            "ticket_subject": self._ticket_subject,
        }


class ITFlowCloseTicketButton(ITFlowTicketActionButton):
    """Button to close a ticket."""

    def __init__(
        self, hass: HomeAssistant, entry_id: str, title: str, ticket_id: int, ticket_subject: str
    ):
        """Initialize the close ticket button."""
        super().__init__(hass, entry_id, title, ticket_id, ticket_subject, "Close")

    async def async_press(self) -> None:
        """Handle the button press - close ticket."""
        try:
            entry_data = self.hass.data.get(DOMAIN, {}).get(self._entry_id)
            if not entry_data or not isinstance(entry_data, dict):
                _LOGGER.error("ITFlow client not found")
                return

            client = entry_data.get("itflow_client")
            if not client:
                _LOGGER.error("ITFlow client not initialized")
                return

            # Close the ticket
            response = await client.update_ticket(self._ticket_id, status="Closed")

            if response.get("success"):
                _LOGGER.info("Successfully closed ticket %s", self._ticket_id)
                # Refresh tickets
                from homeassistant.helpers import entity_component
                for entity_id in self.hass.states.async_entity_ids("sensor"):
                    if "itflow_open_tickets" in entity_id:
                        await entity_component.async_update_entity(self.hass, entity_id)
                        break
            else:
                _LOGGER.error("Failed to close ticket %s: %s", self._ticket_id, response.get("message"))
        except Exception as err:
            _LOGGER.error("Error closing ticket %s: %s", self._ticket_id, err)


class ITFlowReplyTicketButton(ITFlowTicketActionButton):
    """Button to reply to a ticket."""

    def __init__(
        self, hass: HomeAssistant, entry_id: str, title: str, ticket_id: int, ticket_subject: str
    ):
        """Initialize the reply ticket button."""
        super().__init__(hass, entry_id, title, ticket_id, ticket_subject, "Reply")
        self._last_reply = ""

    async def async_press(self) -> None:
        """Handle the button press - add reply to ticket."""
        try:
            # This is a simplified version - in a real implementation, you'd want
            # to use a service call with the reply text as a parameter
            _LOGGER.info("Reply button pressed for ticket %s", self._ticket_id)
            _LOGGER.info("Use the onoff_itflow.reply_to_ticket service to add a reply")
        except Exception as err:
            _LOGGER.error("Error replying to ticket %s: %s", self._ticket_id, err)
