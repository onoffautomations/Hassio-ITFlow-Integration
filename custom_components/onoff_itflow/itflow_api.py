"""ITFlow API client for Home Assistant integration."""

from __future__ import annotations

import aiohttp
import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)


class ITFlowClient:
    """ITFlow API Client."""

    def __init__(self, server: str, api_key: str, client_id: str):
        """Initialize the ITFlow client.

        Args:
            server: ITFlow server URL (not used, hardcoded to ticket.onoffapi.com)
            api_key: ITFlow API key
            client_id: ITFlow client ID
        """
        # Hardcoded server URL - always use ticket.onoffapi.com
        self.server = "https://ticket.onoffapi.com/api/v1"

        _LOGGER.info("ITFlow client initialized with server: %s", self.server)

        self.api_key = api_key
        self.client_id = client_id
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        """Close the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def _request(
        self, endpoint: str, method: str = "GET", data: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Make a request to the ITFlow API.

        Args:
            endpoint: API endpoint (e.g., /tickets/create.php)
            method: HTTP method
            data: Request data

        Returns:
            API response as dictionary
        """
        import json as json_module

        session = await self._get_session()
        # Build URL - endpoint should NOT include /api/v1 as it's already in self.server
        url = f"{self.server}{endpoint}"

        if data is None:
            data = {}

        try:
            if method == "GET":
                # For GET, add api_key to params
                if "api_key" not in data:
                    data["api_key"] = self.api_key
                # For GET, send data as URL params
                async with session.get(url, params=data) as response:
                    response_text = await response.text()
                    if response.status >= 400:
                        _LOGGER.debug("ITFlow API error response: %s", response_text[:200])
                        return {"success": False, "message": f"HTTP {response.status}: {response_text}"}
                    try:
                        result = await response.json()
                        return result
                    except Exception as json_err:
                        _LOGGER.debug("Failed to parse JSON: %s, Raw response: %s", json_err, response_text[:200])
                        return {"success": False, "message": response_text}
            else:  # POST
                # ITFlow API expects JSON body with api_key included
                # Ensure api_key is in the data
                if "api_key" not in data:
                    data["api_key"] = self.api_key

                import json as json_module
                json_body = json_module.dumps(data)
                headers = {"Content-Type": "application/json"}

                async with session.post(url, data=json_body, headers=headers) as response:
                    response_text = await response.text()
                    if response.status >= 400:
                        _LOGGER.debug("ITFlow API error response: %s", response_text[:200])
                        return {"success": False, "message": f"HTTP {response.status}: {response_text}"}
                    try:
                        result = await response.json()
                        return result
                    except Exception as json_err:
                        _LOGGER.debug("Failed to parse JSON: %s, Raw response: %s", json_err, response_text[:200])
                        return {"success": False, "message": response_text}
        except aiohttp.ClientError as err:
            _LOGGER.error("ITFlow API request failed: %s (URL: %s)", err, url)
            return {"success": False, "message": str(err)}
        except Exception as err:
            _LOGGER.error("Unexpected error in ITFlow API request: %s (URL: %s)", err, url)
            return {"success": False, "message": str(err)}

    async def create_asset(
        self,
        asset_name: str,
        asset_type: str = "Server",
        asset_ip: str | None = None,
        asset_notes: str | None = None,
        asset_make: str | None = None,
        asset_model: str | None = None,
        asset_serial: str | None = None,
        asset_os: str | None = None,
        asset_mac: str | None = None,
        asset_status: str | None = None,
        asset_purchase_date: str | None = None,
        asset_warranty_expire: str | None = None,
        install_date: str | None = None
    ) -> dict[str, Any]:
        """Create an asset in ITFlow.

        Args:
            asset_name: Name of the asset
            asset_type: Type of asset (Server, Workstation, etc.)
            asset_ip: IP address of the asset
            asset_notes: Additional notes
            asset_make: Manufacturer/make
            asset_model: Model
            asset_serial: Serial number
            asset_os: Operating system
            asset_mac: MAC address
            asset_status: Status (Deployed, etc.)
            asset_purchase_date: Purchase date (YYYY-MM-DD)
            asset_warranty_expire: Warranty expiration (YYYY-MM-DD)
            install_date: Installation date (YYYY-MM-DD)

        Returns:
            API response
        """
        data = {
            "client_id": self.client_id,
            "asset_name": asset_name,
            "asset_type": asset_type,
        }

        if asset_ip:
            data["asset_ip"] = asset_ip
        if asset_notes:
            data["asset_notes"] = asset_notes
        if asset_make:
            data["asset_make"] = asset_make
        if asset_model:
            data["asset_model"] = asset_model
        if asset_serial:
            data["asset_serial"] = asset_serial
        if asset_os:
            data["asset_os"] = asset_os
        if asset_mac:
            data["asset_mac"] = asset_mac
        if asset_status:
            data["asset_status"] = asset_status
        if asset_purchase_date:
            data["asset_purchase_date"] = asset_purchase_date
        if asset_warranty_expire:
            data["asset_warranty_expire"] = asset_warranty_expire
        if install_date:
            data["install_date"] = install_date

        return await self._request("/assets/create.php", "POST", data)

    async def update_asset(
        self,
        asset_id: int,
        asset_ip: str | None = None,
        asset_notes: str | None = None
    ) -> dict[str, Any]:
        """Update an existing asset in ITFlow.

        Args:
            asset_id: ID of the asset to update
            asset_ip: New IP address
            asset_notes: Updated notes

        Returns:
            API response
        """
        data = {
            "client_id": self.client_id,
            "asset_id": asset_id,
        }

        if asset_ip:
            data["asset_ip"] = asset_ip
        if asset_notes:
            data["asset_notes"] = asset_notes

        return await self._request("/assets/update.php", "POST", data)

    async def get_assets(self) -> dict[str, Any]:
        """Get all assets for the client.

        Returns:
            API response with assets list
        """
        data = {"client_id": self.client_id}
        return await self._request("/assets/read.php", "GET", data)

    async def create_contact(
        self,
        contact_name: str,
        contact_email: str | None = None,
        contact_phone: str | None = None,
        contact_notes: str | None = None,
        contact_title: str | None = None,
        contact_department: str | None = None,
        contact_extension: str | None = None,
        contact_mobile: str | None = None,
        contact_auth_method: str = "local",
        contact_primary: int = 0,
        contact_important: int = 0,
        contact_billing: int = 0,
        contact_technical: int = 0,
        contact_location_id: int = 0
    ) -> dict[str, Any]:
        """Create a contact in ITFlow.

        Args:
            contact_name: Name of the contact
            contact_email: Email address
            contact_phone: Phone number
            contact_notes: Additional notes
            contact_title: Job title
            contact_department: Department
            contact_extension: Phone extension
            contact_mobile: Mobile phone
            contact_auth_method: Authentication method (default: "local")
            contact_primary: Primary contact flag (0 or 1)
            contact_important: Important contact flag (0 or 1)
            contact_billing: Billing contact flag (0 or 1)
            contact_technical: Technical contact flag (0 or 1)
            contact_location_id: Location ID (0 for no location)

        Returns:
            API response
        """
        # Match Python example EXACTLY - use contact_* prefix for all fields
        # Use default email if not provided
        if not contact_email:
            contact_email = "api@homeassistant.local"

        # Build data matching Python example format EXACTLY
        data = {
            "api_key": self.api_key,
            "contact_name": contact_name,
            "contact_title": contact_title if contact_title else "",
            "contact_department": contact_department if contact_department else "",
            "contact_email": contact_email,
            "contact_phone": contact_phone if contact_phone else "",
            "contact_extension": contact_extension if contact_extension else "",
            "contact_mobile": contact_mobile if contact_mobile else "",
            "contact_notes": contact_notes if contact_notes else "",
            "contact_auth_method": contact_auth_method,
            "contact_primary": str(contact_primary),
            "contact_important": str(contact_important),
            "contact_billing": str(contact_billing),
            "contact_technical": str(contact_technical),
            "contact_location_id": str(contact_location_id),
            "client_id": str(self.client_id),
        }

        # Log the exact request for debugging
        import json
        _LOGGER.info("=== Creating Contact ===")
        _LOGGER.info("Contact name: %s", contact_name)
        _LOGGER.info("Client ID: %s", self.client_id)
        _LOGGER.info("Full request payload:")
        _LOGGER.info(json.dumps(data, indent=2))

        result = await self._request("/contacts/create.php", "POST", data)

        _LOGGER.info("ITFlow Response:")
        _LOGGER.info(json.dumps(result, indent=2))

        return result

    async def create_ticket(
        self,
        subject: str,
        details: str,
        priority: str = "Low",
        contact_id: int | None = None,
        asset_id: int | None = None,
        category: str | None = None,
        category_id: int | None = None,
        status: str | None = None,
        assigned_to: int | None = None
    ) -> dict[str, Any]:
        """Create a ticket in ITFlow.

        Args:
            subject: Ticket subject
            details: Ticket details/description
            priority: Ticket priority (Low, Medium, High)
            contact_id: Associated contact ID
            asset_id: Associated asset ID
            category: Ticket category name (deprecated, use category_id)
            category_id: Ticket category ID (preferred over category)
            status: Ticket status (New, Open, On Hold, Resolved, Closed, Maintenance/7)
            assigned_to: User ID to assign ticket to

        Returns:
            API response
        """
        data = {
            "client_id": self.client_id,
            "ticket_subject": subject,
            "ticket_details": details,
            "ticket_priority": priority,
        }

        if contact_id:
            data["ticket_contact_id"] = contact_id
        if asset_id:
            data["asset_id"] = asset_id
        # Prefer category_id over category name
        if category_id:
            data["ticket_category_id"] = category_id
        elif category:
            data["ticket_category"] = category
        if status:
            data["ticket_status"] = status
        if assigned_to:
            data["ticket_assigned_to"] = assigned_to

        return await self._request("/tickets/create.php", "POST", data)

    async def get_tickets(self, status: str = "Open") -> dict[str, Any]:
        """Get tickets for the client.

        Args:
            status: Ticket status filter (Open, Closed, etc.)

        Returns:
            API response with tickets list
        """
        data = {
            "client_id": self.client_id,
            "ticket_status": status,
        }
        return await self._request("/tickets/read.php", "GET", data)

    async def update_ticket(
        self,
        ticket_id: int,
        status: str | None = None,
        priority: str | None = None
    ) -> dict[str, Any]:
        """Update a ticket in ITFlow.

        Args:
            ticket_id: ID of the ticket to update
            status: New status
            priority: New priority

        Returns:
            API response
        """
        # Try /tickets/update.php first, fall back to /tickets/close.php for status changes
        if status and str(status).lower() == "closed":
            data = {
                "client_id": self.client_id,
                "ticket_id": ticket_id,
            }
            result = await self._request("/tickets/close.php", "POST", data)
            if result.get("success") or "404" not in str(result.get("message", "")):
                return result

        # Try standard update endpoint
        data = {
            "client_id": self.client_id,
            "ticket_id": ticket_id,
        }

        if status:
            data["ticket_status"] = status
        if priority:
            data["ticket_priority"] = priority

        return await self._request("/tickets/update.php", "POST", data)

    async def add_ticket_reply(
        self,
        ticket_id: int,
        reply: str
    ) -> dict[str, Any]:
        """Add a reply/note to a ticket.

        Args:
            ticket_id: ID of the ticket
            reply: Reply text

        Returns:
            API response with success status
        """
        # ITFlow API doesn't have a direct reply endpoint
        # We need to use a workaround - return success for now
        # User should add notes directly in ITFlow
        _LOGGER.warning(
            "ITFlow API doesn't support adding replies via API. "
            "Reply text: %s for ticket ID: %s. "
            "Please add this note manually in ITFlow.",
            reply[:100], ticket_id
        )
        return {
            "success": False,
            "message": "ITFlow API doesn't support adding replies. Please add notes directly in ITFlow web interface."
        }

    async def create_domain(
        self,
        domain_name: str,
        domain_expire: str | None = None,
        domain_notes: str | None = None,
        domain_registrar: str | None = None,
        domain_webhost: str | None = None,
        domain_ip: str | None = None,
        domain_name_servers: str | None = None
    ) -> dict[str, Any]:
        """Create a domain in ITFlow.

        Args:
            domain_name: Domain name
            domain_expire: Expiration date (YYYY-MM-DD format)
            domain_notes: Additional notes
            domain_registrar: Domain registrar
            domain_webhost: Web hosting provider
            domain_ip: IP address
            domain_name_servers: Name servers (comma-separated)

        Returns:
            API response
        """
        data = {
            "client_id": self.client_id,
            "domain_name": domain_name,
        }

        if domain_expire:
            data["domain_expire"] = domain_expire
        if domain_notes:
            data["domain_notes"] = domain_notes
        if domain_registrar:
            data["domain_registrar"] = domain_registrar
        if domain_webhost:
            data["domain_webhost"] = domain_webhost
        if domain_ip:
            data["domain_ip"] = domain_ip
        if domain_name_servers:
            data["domain_name_servers"] = domain_name_servers

        return await self._request("/domains/create.php", "POST", data)

    async def update_domain(
        self,
        domain_id: int,
        domain_name: str | None = None,
        domain_expire: str | None = None,
        domain_notes: str | None = None,
        domain_registrar: str | None = None,
        domain_webhost: str | None = None,
        domain_ip: str | None = None,
        domain_name_servers: str | None = None
    ) -> dict[str, Any]:
        """Update an existing domain in ITFlow.

        Args:
            domain_id: ID of the domain to update
            domain_name: Domain name
            domain_expire: Expiration date (YYYY-MM-DD format)
            domain_notes: Additional notes
            domain_registrar: Domain registrar
            domain_webhost: Web hosting provider
            domain_ip: IP address
            domain_name_servers: Name servers (comma-separated)

        Returns:
            API response
        """
        data = {
            "client_id": self.client_id,
            "domain_id": domain_id,
        }

        if domain_name:
            data["domain_name"] = domain_name
        if domain_expire:
            data["domain_expire"] = domain_expire
        if domain_notes:
            data["domain_notes"] = domain_notes
        if domain_registrar:
            data["domain_registrar"] = domain_registrar
        if domain_webhost:
            data["domain_webhost"] = domain_webhost
        if domain_ip:
            data["domain_ip"] = domain_ip
        if domain_name_servers:
            data["domain_name_servers"] = domain_name_servers

        return await self._request("/domains/update.php", "POST", data)

    async def create_log(
        self,
        log_type: str,
        log_action: str,
        log_description: str,
        asset_id: int | None = None
    ) -> dict[str, Any]:
        """Create a log entry in ITFlow.

        Args:
            log_type: Type of log entry
            log_action: Action performed
            log_description: Description of the log entry
            asset_id: Associated asset ID

        Returns:
            API response
        """
        data = {
            "client_id": self.client_id,
            "log_type": log_type,
            "log_action": log_action,
            "log_description": log_description,
        }

        if asset_id:
            data["asset_id"] = asset_id

        return await self._request("/logs/create.php", "POST", data)

    async def create_location(
        self,
        location_name: str,
        location_description: str | None = None,
        location_country: str | None = None,
        location_address: str | None = None,
        location_city: str | None = None,
        location_state: str | None = None,
        location_zip: str | None = None,
        phone: str | None = None,
        location_hours: str | None = None,
        location_notes: str | None = None,
        location_primary: str | None = None
    ) -> dict[str, Any]:
        """Create a location in ITFlow.

        Args:
            location_name: Name of the location
            location_description: Description
            location_country: Country
            location_address: Street address
            location_city: City
            location_state: State/province
            location_zip: ZIP/postal code
            phone: Phone number
            location_hours: Business hours
            location_notes: Additional notes
            location_primary: Whether this is the primary location (0 or 1)

        Returns:
            API response
        """
        data = {
            "client_id": self.client_id,
            "location_name": location_name,
        }

        if location_description:
            data["location_description"] = location_description
        if location_country:
            data["location_country"] = location_country
        if location_address:
            data["location_address"] = location_address
        if location_city:
            data["location_city"] = location_city
        if location_state:
            data["location_state"] = location_state
        if location_zip:
            data["location_zip"] = location_zip
        if phone:
            data["location_phone"] = phone
        if location_hours:
            data["location_hours"] = location_hours
        if location_notes:
            data["location_notes"] = location_notes
        if location_primary:
            data["location_primary"] = location_primary

        return await self._request("/locations/create.php", "POST", data)

    async def create_document(
        self,
        document_name: str,
        document_content: str,
        document_description: str | None = None,
        folder_id: int | None = None
    ) -> dict[str, Any]:
        """Create a document in ITFlow.

        Args:
            document_name: Name of the document
            document_content: HTML content of the document
            document_description: Description
            folder_id: Optional folder ID to organize the document

        Returns:
            API response
        """
        data = {
            "client_id": self.client_id,
            "document_name": document_name,
            "document_content": document_content,
        }

        if document_description:
            data["document_description"] = document_description

        if folder_id:
            data["folder"] = folder_id

        return await self._request("/documents/create.php", "POST", data)

    async def create_document_folder(
        self,
        folder_name: str,
        parent_folder_id: int = 0
    ) -> dict[str, Any]:
        """Create a document folder in ITFlow.

        Args:
            folder_name: Name of the folder
            parent_folder_id: Parent folder ID (0 for root level)

        Returns:
            API response
        """
        data = {
            "client_id": self.client_id,
            "name": folder_name,
            "parent": parent_folder_id
        }

        return await self._request("/document_folders/create.php", "POST", data)

    async def get_document_folders(self) -> dict[str, Any]:
        """Get all document folders for the client.

        Returns:
            API response with folders
        """
        params = {"client_id": self.client_id}
        return await self._request("/document_folders/read.php", "GET", params)

    async def update_document(
        self,
        document_id: int,
        document_name: str | None = None,
        document_content: str | None = None,
        document_description: str | None = None
    ) -> dict[str, Any]:
        """Update an existing document in ITFlow.

        Args:
            document_id: ID of the document to update
            document_name: New name
            document_content: New HTML content
            document_description: New description

        Returns:
            API response
        """
        # CRITICAL: Ensure document_id is ALWAYS included and is an integer
        # This prevents updating all documents under the client
        if not document_id:
            _LOGGER.error("CRITICAL: update_document called without document_id! This would update ALL documents!")
            return {"success": False, "message": "document_id is required"}

        # CRITICAL: Build data dictionary with document_id FIRST to ensure it's sent
        # ITFlow API REQUIRES document_id to update a specific document
        # Without it, ALL client documents would be updated

        # FORCE document_id to be an integer and validate it
        try:
            doc_id_int = int(document_id)
            if doc_id_int <= 0:
                raise ValueError(f"Invalid document_id: {doc_id_int}")
        except (ValueError, TypeError) as e:
            _LOGGER.error("CRITICAL: Invalid document_id provided: %s (error: %s)", document_id, e)
            return {"success": False, "message": f"Invalid document_id: {document_id}"}

        # Build data with document_id and client_id
        # Note: api_key will be added as URL parameter by _request method
        data = {
            "document_id": str(doc_id_int),  # Send as string
            "client_id": str(self.client_id),  # Send as string
        }

        # Add required fields - ALWAYS send these even if provided
        if document_name:
            data["document_name"] = str(document_name)
        if document_description:
            data["document_description"] = str(document_description)
        if document_content:
            data["document_content"] = str(document_content)

        _LOGGER.debug("Document update - ID: %s, Name: %s", document_id, document_name)

        result = await self._request("/documents/update.php", "POST", data)

        if not result.get("success"):
            _LOGGER.debug("Document update failed for document_id %s: %s", document_id, result)

        return result

    async def get_contacts(self) -> dict[str, Any]:
        """Get all contacts for the client.

        Returns:
            API response with contacts list
        """
        data = {"client_id": self.client_id}
        return await self._request("/contacts/read.php", "GET", data)

    async def delete_contact(self, contact_id: int) -> dict[str, Any]:
        """Delete a contact from ITFlow.

        Args:
            contact_id: ID of the contact to delete

        Returns:
            API response
        """
        data = {
            "contact_id": contact_id,
            "client_id": self.client_id,
        }
        return await self._request("/contacts/delete.php", "POST", data)

    async def update_contact(
        self,
        contact_id: int,
        contact_name: str | None = None,
        contact_email: str | None = None,
        contact_phone: str | None = None,
        contact_mobile: str | None = None,
        contact_title: str | None = None,
        contact_department: str | None = None,
        contact_notes: str | None = None,
        contact_important: str | None = None,
        contact_billing: str | None = None,
        contact_technical: str | None = None
    ) -> dict[str, Any]:
        """Update an existing contact in ITFlow.

        Args:
            contact_id: ID of the contact to update
            contact_name: New name
            contact_email: New email
            contact_phone: New phone
            contact_mobile: New mobile
            contact_title: New title
            contact_department: New department
            contact_notes: New notes
            contact_important: Important contact flag (0 or 1)
            contact_billing: Billing contact flag (0 or 1)
            contact_technical: Technical contact flag (0 or 1)

        Returns:
            API response
        """
        data = {
            "contact_id": contact_id,
            "client_id": self.client_id,
        }

        if contact_name:
            data["contact_name"] = contact_name
        if contact_email:
            data["contact_email"] = contact_email
        if contact_phone:
            data["contact_phone"] = contact_phone
        if contact_mobile:
            data["contact_mobile"] = contact_mobile
        if contact_title:
            data["contact_title"] = contact_title
        if contact_department:
            data["contact_department"] = contact_department
        if contact_notes:
            data["contact_notes"] = contact_notes
        if contact_important:
            data["contact_important"] = contact_important
        if contact_billing:
            data["contact_billing"] = contact_billing
        if contact_technical:
            data["contact_technical"] = contact_technical

        return await self._request("/contacts/update.php", "POST", data)

    async def resolve_ticket(self, ticket_id: int) -> dict[str, Any]:
        """Resolve/close a ticket in ITFlow.

        Args:
            ticket_id: ID of the ticket to resolve

        Returns:
            API response
        """
        data = {
            "client_id": self.client_id,
            "ticket_id": ticket_id,
            "ticket_status": "Resolved"
        }
        return await self._request("/tickets/update.php", "POST", data)

    async def close_ticket(self, ticket_id: int) -> dict[str, Any]:
        """Close a ticket in ITFlow.

        Args:
            ticket_id: ID of the ticket to close

        Returns:
            API response
        """
        data = {
            "client_id": self.client_id,
            "ticket_id": ticket_id,
        }
        return await self._request("/tickets/close.php", "POST", data)

    async def reopen_ticket(self, ticket_id: int) -> dict[str, Any]:
        """Reopen a closed ticket in ITFlow.

        Args:
            ticket_id: ID of the ticket to reopen

        Returns:
            API response
        """
        data = {
            "client_id": self.client_id,
            "ticket_id": ticket_id,
            "ticket_status": "New"
        }
        return await self._request("/tickets/update.php", "POST", data)

    async def create_network(
        self,
        network_name: str,
        network: str,
        network_mask: str,
        network_gateway: str | None = None,
        network_dhcp_range: str | None = None,
        network_vlan: int | None = None,
        network_notes: str | None = None
    ) -> dict[str, Any]:
        """Create a network in ITFlow.

        Args:
            network_name: Network name
            network: Network address
            network_mask: Subnet mask or CIDR
            network_gateway: Gateway IP
            network_dhcp_range: DHCP range
            network_vlan: VLAN number
            network_notes: Additional notes

        Returns:
            API response
        """
        data = {
            "client_id": self.client_id,
            "network_name": network_name,
            "network": network,
            "network_mask": network_mask,
        }

        if network_gateway:
            data["network_gateway"] = network_gateway
        if network_dhcp_range:
            data["network_dhcp_range"] = network_dhcp_range
        if network_vlan is not None:
            data["network_vlan"] = network_vlan
        if network_notes:
            data["network_notes"] = network_notes

        return await self._request("/networks/create.php", "POST", data)

    async def create_software(
        self,
        software_name: str,
        software_type: str | None = None,
        software_license_type: str | None = None,
        software_key: str | None = None,
        software_seats: int | None = None,
        software_notes: str | None = None
    ) -> dict[str, Any]:
        """Create a software license in ITFlow.

        Args:
            software_name: Software name
            software_type: Software type
            software_license_type: License type
            software_key: License key
            software_seats: Number of seats
            software_notes: Additional notes

        Returns:
            API response
        """
        data = {
            "client_id": self.client_id,
            "software_name": software_name,
        }

        if software_type:
            data["software_type"] = software_type
        if software_license_type:
            data["software_license_type"] = software_license_type
        if software_key:
            data["software_key"] = software_key
        if software_seats is not None:
            data["software_seats"] = software_seats
        if software_notes:
            data["software_notes"] = software_notes

        return await self._request("/software/create.php", "POST", data)

    async def create_certificate(
        self,
        certificate_name: str,
        certificate_domain: str,
        certificate_issued_by: str | None = None,
        certificate_expire: str | None = None,
        certificate_notes: str | None = None
    ) -> dict[str, Any]:
        """Create a certificate in ITFlow.

        Args:
            certificate_name: Certificate name
            certificate_domain: Domain name
            certificate_issued_by: Certificate authority
            certificate_expire: Expiration date (YYYY-MM-DD)
            certificate_notes: Additional notes

        Returns:
            API response
        """
        data = {
            "client_id": self.client_id,
            "certificate_name": certificate_name,
            "certificate_domain": certificate_domain,
        }

        if certificate_issued_by:
            data["certificate_issued_by"] = certificate_issued_by
        if certificate_expire:
            data["certificate_expire"] = certificate_expire
        if certificate_notes:
            data["certificate_notes"] = certificate_notes

        return await self._request("/certificates/create.php", "POST", data)

    async def create_credential(
        self,
        credential_name: str,
        credential_username: str | None = None,
        credential_password: str | None = None,
        credential_notes: str | None = None
    ) -> dict[str, Any]:
        """Create a credential in ITFlow.

        Args:
            credential_name: Credential name
            credential_username: Username
            credential_password: Password (will be encrypted)
            credential_notes: Additional notes

        Returns:
            API response
        """
        data = {
            "client_id": self.client_id,
            "credential_name": credential_name,
        }

        if credential_username:
            data["credential_username"] = credential_username
        if credential_password:
            data["credential_password"] = credential_password
        if credential_notes:
            data["credential_notes"] = credential_notes

        return await self._request("/credentials/create.php", "POST", data)

    def _get_version_html(self, hass) -> str:
        """Get version comparison HTML with red indicator if update available.

        Args:
            hass: Home Assistant instance

        Returns:
            HTML string with version info
        """
        # Get installed version
        try:
            from homeassistant.const import __version__
            installed_version = __version__
        except:
            installed_version = "Unknown"

        latest_version = None

        # Try to find update entity or version entity
        for state in hass.states.async_all():
            if state.entity_id in ["update.home_assistant_core_update", "update.home_assistant_operating_system_update"]:
                latest_version = state.attributes.get("latest_version")
                if latest_version:
                    break
            elif state.entity_id.startswith("sensor.") and "version" in state.entity_id.lower():
                if state.attributes.get("latest_version"):
                    latest_version = state.attributes.get("latest_version")
                    break

        if latest_version and latest_version != installed_version:
            return f'<span style="color: red;">Installed: {installed_version} | Latest: {latest_version} (UPDATE AVAILABLE!)</span>'
        elif latest_version:
            return f'Installed: {installed_version} | Latest: {latest_version}'
        else:
            return f'{installed_version}'

    def _get_ha_info(self, hass, ha_start_time, ha_uptime_str) -> str:
        """Get single-line HA info.

        Args:
            hass: Home Assistant instance
            ha_start_time: HA start timestamp
            ha_uptime_str: HA uptime string

        Returns:
            Single-line formatted string
        """
        return f'Started: {ha_start_time} | Uptime: {ha_uptime_str}'

    async def _get_proxmox_info(self, hass) -> str:
        """Get Proxmox node and VM information if configured.

        Args:
            hass: Home Assistant instance

        Returns:
            HTML string with Proxmox info or empty string
        """
        try:
            from .const import (
                DOMAIN,
                CONF_PROXMOX_ENABLED,
                CONF_PROXMOX_HOST,
                CONF_PROXMOX_USER,
                CONF_PROXMOX_PASSWORD,
                CONF_PROXMOX_VERIFY_SSL,
                CONF_PROXMOX_PORT,
                CONF_PROXMOX_REALM,
                DEFAULT_PROXMOX_PORT,
                DEFAULT_PROXMOX_REALM,
            )
            from .proxmox_api import ProxmoxClient

            # Find the config entry for this integration
            config_entry = None
            for entry in hass.config_entries.async_entries(DOMAIN):
                if entry.data.get(CONF_PROXMOX_ENABLED, False):
                    config_entry = entry
                    break

            if not config_entry:
                _LOGGER.debug("Proxmox not enabled, skipping")
                return ""

            # Connect to Proxmox using our custom client
            proxmox = ProxmoxClient(
                host=config_entry.data.get(CONF_PROXMOX_HOST),
                port=config_entry.data.get(CONF_PROXMOX_PORT, DEFAULT_PROXMOX_PORT),
                user=config_entry.data.get(CONF_PROXMOX_USER),
                password=config_entry.data.get(CONF_PROXMOX_PASSWORD),
                realm=config_entry.data.get(CONF_PROXMOX_REALM, DEFAULT_PROXMOX_REALM),
                verify_ssl=config_entry.data.get(CONF_PROXMOX_VERIFY_SSL, True),
            )

            # Authenticate
            if not await proxmox.authenticate():
                _LOGGER.error("Failed to authenticate to Proxmox")
                return "<h2>🖥️ Proxmox Information</h2><p>❌ Authentication failed</p>"

            html = """
<h2>🖥️ Proxmox Information</h2>
<table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse; width: 100%;">
    <tr style="background-color: #f0f0f0;">
        <th>Node</th>
        <th>Type</th>
        <th>ID</th>
        <th>Name</th>
        <th>Status</th>
        <th>CPU %</th>
        <th>Memory %</th>
        <th>Disk %</th>
    </tr>
"""

            # Get all nodes
            nodes = await proxmox.get_nodes()
            for node in nodes:
                node_name = node['node']

                # Get VMs
                vms = await proxmox.get_vms(node_name)
                for vm in vms:
                    vm_id = vm['vmid']
                    vm_name = vm.get('name', 'Unknown')
                    vm_status = await proxmox.get_vm_status(node_name, vm_id)

                    if not vm_status:
                        continue

                    status = vm_status.get('status', 'unknown')
                    cpu_percent = round(vm_status.get('cpu', 0) * 100, 2) if status == 'running' else 0

                    mem_used = vm_status.get('mem', 0)
                    mem_total = vm_status.get('maxmem', 1)
                    mem_percent = round((mem_used / mem_total) * 100, 2) if mem_total > 0 else 0

                    disk_used = vm_status.get('disk', 0)
                    disk_total = vm_status.get('maxdisk', 1)
                    disk_percent = round((disk_used / disk_total) * 100, 2) if disk_total > 0 else 0

                    status_icon = "✅" if status == "running" else "❌"

                    html += f"""
    <tr>
        <td>{node_name}</td>
        <td>VM</td>
        <td>{vm_id}</td>
        <td>{vm_name}</td>
        <td>{status_icon} {status}</td>
        <td>{cpu_percent}%</td>
        <td>{mem_percent}%</td>
        <td>{disk_percent}%</td>
    </tr>
"""

                # Get Containers (LXC)
                containers = await proxmox.get_containers(node_name)
                for ct in containers:
                    ct_id = ct['vmid']
                    ct_name = ct.get('name', 'Unknown')
                    ct_status = await proxmox.get_container_status(node_name, ct_id)

                    if not ct_status:
                        continue

                    status = ct_status.get('status', 'unknown')
                    cpu_percent = round(ct_status.get('cpu', 0) * 100, 2) if status == 'running' else 0

                    mem_used = ct_status.get('mem', 0)
                    mem_total = ct_status.get('maxmem', 1)
                    mem_percent = round((mem_used / mem_total) * 100, 2) if mem_total > 0 else 0

                    disk_used = ct_status.get('disk', 0)
                    disk_total = ct_status.get('maxdisk', 1)
                    disk_percent = round((disk_used / disk_total) * 100, 2) if disk_total > 0 else 0

                    status_icon = "✅" if status == "running" else "❌"

                    html += f"""
    <tr>
        <td>{node_name}</td>
        <td>LXC</td>
        <td>{ct_id}</td>
        <td>{ct_name}</td>
        <td>{status_icon} {status}</td>
        <td>{cpu_percent}%</td>
        <td>{mem_percent}%</td>
        <td>{disk_percent}%</td>
    </tr>
"""

            html += """
</table>
"""
            # Close the proxmox connection
            await proxmox.close()

            return html

        except Exception as err:
            _LOGGER.error("Error getting Proxmox info: %s", err, exc_info=True)
            return ""

    def _get_scheduler_info(self, hass) -> str:
        """Get scheduler domain information if available.

        Args:
            hass: Home Assistant instance

        Returns:
            HTML string with scheduler info or empty string
        """
        try:
            # Find all scheduler entities
            scheduler_entities = [s for s in hass.states.async_all() if s.entity_id.startswith('schedule.') or s.entity_id.startswith('scheduler.')]

            if not scheduler_entities:
                return ""

            html = """
<h2>📅 Scheduler Information</h2>
<table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse; width: 100%;">
    <tr style="background-color: #f0f0f0;">
        <th>Entity ID</th>
        <th>Name</th>
        <th>State</th>
        <th>Next Run</th>
        <th>Details</th>
    </tr>
"""

            for entity in sorted(scheduler_entities, key=lambda x: x.entity_id):
                entity_id = entity.entity_id
                name = entity.attributes.get('friendly_name', entity_id)
                state = entity.state

                # Try to get next run time
                next_run = entity.attributes.get('next_run', entity.attributes.get('next_trigger', 'N/A'))

                # Get other relevant attributes
                details = []
                if 'action' in entity.attributes:
                    details.append(f"Action: {entity.attributes['action']}")
                if 'time' in entity.attributes:
                    details.append(f"Time: {entity.attributes['time']}")
                if 'weekdays' in entity.attributes:
                    weekdays = entity.attributes['weekdays']
                    if isinstance(weekdays, list):
                        weekdays = ', '.join(weekdays)
                    details.append(f"Days: {weekdays}")
                if 'entity_id' in entity.attributes:
                    target_entity = entity.attributes['entity_id']
                    if isinstance(target_entity, list):
                        target_entity = ', '.join(target_entity)
                    details.append(f"Target: {target_entity}")

                details_str = '<br>'.join(details) if details else 'N/A'

                state_icon = "✅" if state == "on" else "❌"

                html += f"""
    <tr>
        <td>{entity_id}</td>
        <td>{name}</td>
        <td>{state_icon} {state}</td>
        <td>{next_run}</td>
        <td>{details_str}</td>
    </tr>
"""

            html += """
</table>
"""
            return html

        except Exception as err:
            _LOGGER.debug("Error getting scheduler info: %s", err)
            return ""

    def _format_datetime(self, dt_str: str) -> str:
        """Format datetime string to readable format.

        Args:
            dt_str: ISO format datetime string like "2025-10-20T09:35:00.264+00:00"

        Returns:
            Formatted string like "10/20/2025 at 9:35 AM"
        """
        try:
            from datetime import datetime
            # Try to parse ISO format
            if isinstance(dt_str, str):
                # Remove milliseconds and timezone for parsing
                dt_str_clean = dt_str.split('.')[0] if '.' in dt_str else dt_str
                dt_str_clean = dt_str_clean.replace('Z', '').split('+')[0].split('-')
                # Reconstruct basic datetime
                if 'T' in dt_str:
                    dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
                    return dt.strftime('%m/%d/%Y at %I:%M %p')
            return dt_str
        except:
            return dt_str

    async def get_backup_status(self, hass) -> str:
        """Generate HTML formatted backup status information.

        Args:
            hass: Home Assistant instance

        Returns:
            HTML formatted backup status
        """
        try:
            from datetime import datetime

            html = """
<h1>Home Assistant Backup Status</h1>
<p><em>Last Updated: """ + datetime.now().strftime('%m/%d/%Y at %I:%M %p') + """</em></p>

<h2>💾 Google Drive Backup Status</h2>
<table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse; width: 100%;">
    <tr style="background-color: #f0f0f0;">
        <th>Metric</th>
        <th>Value</th>
    </tr>
"""

            # Look for Google Drive Backup sensors
            google_backup_found = False
            for state in hass.states.async_all():
                if 'backup' in state.entity_id.lower() and ('google' in state.entity_id.lower() or 'drive' in state.entity_id.lower()):
                    google_backup_found = True
                    sensor_name = state.attributes.get('friendly_name', state.entity_id)

                    # Get various backup attributes
                    last_backup_raw = state.attributes.get('last_backup', state.state)
                    next_backup_raw = state.attributes.get('next_snapshot_time', state.attributes.get('next_backup', 'Unknown'))
                    backup_count = state.attributes.get('backups_in_google_drive', state.attributes.get('backup_count', 'Unknown'))
                    backup_size = state.attributes.get('size_in_google_drive', state.attributes.get('backup_size', 'Unknown'))

                    # Format dates for readability
                    last_backup = self._format_datetime(last_backup_raw)
                    next_backup = self._format_datetime(next_backup_raw)

                    html += f"""
    <tr>
        <td><strong>Last Backup</strong></td>
        <td>{last_backup}</td>
    </tr>
    <tr>
        <td><strong>Next Backup</strong></td>
        <td>{next_backup}</td>
    </tr>
    <tr>
        <td><strong>Backups in Drive</strong></td>
        <td>{backup_count}</td>
    </tr>
    <tr>
        <td><strong>Total Size</strong></td>
        <td>{backup_size}</td>
    </tr>
"""

                    # Add all other attributes
                    for attr_key, attr_value in state.attributes.items():
                        if attr_key not in ['last_backup', 'next_snapshot_time', 'next_backup', 'backups_in_google_drive', 'backup_count', 'size_in_google_drive', 'backup_size', 'friendly_name', 'icon', 'device_class']:
                            html += f"""
    <tr>
        <td>{attr_key.replace('_', ' ').title()}</td>
        <td>{attr_value}</td>
    </tr>
"""

            if not google_backup_found:
                html += """
    <tr>
        <td colspan="2">No Google Drive Backup sensors found. Install the Google Drive Backup add-on for automated backups.</td>
    </tr>
"""

            html += """
</table>

<h2>💾 All Backup Sensors</h2>
<table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse; width: 100%;">
"""

            # Get all backup-related sensors
            backup_sensors = [s for s in hass.states.async_all() if 'backup' in s.entity_id.lower()]

            if backup_sensors:
                html += """
    <tr style="background-color: #f0f0f0;">
        <th>Sensor</th>
        <th>State</th>
        <th>Last Updated</th>
        <th>Details</th>
    </tr>
"""
                for sensor in backup_sensors:
                    sensor_name = sensor.attributes.get('friendly_name', sensor.entity_id)
                    state = sensor.state
                    last_updated = sensor.last_updated.strftime('%m/%d/%Y at %I:%M %p') if sensor.last_updated else 'Unknown'

                    # Get key details
                    details = []
                    if 'last_backup' in sensor.attributes:
                        last_backup_formatted = self._format_datetime(sensor.attributes['last_backup'])
                        details.append(f"Last: {last_backup_formatted}")
                    if 'next_backup' in sensor.attributes or 'next_snapshot_time' in sensor.attributes:
                        next_time_raw = sensor.attributes.get('next_backup', sensor.attributes.get('next_snapshot_time'))
                        next_time_formatted = self._format_datetime(next_time_raw)
                        details.append(f"Next: {next_time_formatted}")
                    if 'backup_count' in sensor.attributes or 'backups_in_google_drive' in sensor.attributes:
                        count = sensor.attributes.get('backup_count', sensor.attributes.get('backups_in_google_drive'))
                        details.append(f"Count: {count}")

                    details_str = ' | '.join(details) if details else 'N/A'

                    html += f"""
    <tr>
        <td>{sensor_name}</td>
        <td>{state}</td>
        <td>{last_updated}</td>
        <td>{details_str}</td>
    </tr>
"""
            else:
                html += """
    <tr>
        <td colspan="4">No backup sensors found. Consider installing the Google Drive Backup add-on or Home Assistant Cloud backup.</td>
    </tr>
"""

            html += """
</table>
"""
            return html
        except Exception as e:
            _LOGGER.error("Failed to generate backup status: %s", e)
            return f"<p>Error generating backup status: {e}</p>"

    async def get_system_info(self, hass) -> str:
        """Generate HTML formatted system information.

        Args:
            hass: Home Assistant instance

        Returns:
            HTML formatted system information
        """
        try:
            import psutil
            from datetime import datetime
            import asyncio
            from dateutil import parser as date_parser

            _LOGGER.debug("Starting get_system_info generation")

            # Get system information (use non-blocking method for CPU)
            cpu_percent = psutil.cpu_percent(interval=0)  # Non-blocking
            # Wait a moment and get again for accurate reading
            await asyncio.sleep(0.1)
            cpu_percent = psutil.cpu_percent(interval=0)

            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            # Get network info
            local_ip = str(hass.config.api.local_ip) if hass.config.api else "Unknown"

            # Get HA version
            try:
                ha_version = hass.data.get('homeassistant', {}).get('version', 'Unknown')
                if ha_version == 'Unknown':
                    # Try alternative method
                    from homeassistant.const import __version__
                    ha_version = __version__
            except:
                ha_version = "Unknown"

            # Get HA instance ID
            ha_instance_id = hass.data.get("core.uuid", "Unknown")

            # Get HA start time (from uptime sensor if available)
            ha_uptime_str = "Unknown"
            ha_start_time = "Unknown"
            try:
                # Try to get HA start time from hass.data
                if hasattr(hass, 'data') and 'homeassistant' in hass.data:
                    ha_start = hass.data.get('homeassistant', {}).get('start_time')
                    if ha_start:
                        ha_start_time = ha_start.strftime('%Y-%m-%d %H:%M:%S')
                        # Get current time with same timezone as ha_start
                        from datetime import timezone
                        if ha_start.tzinfo:
                            now = datetime.now(ha_start.tzinfo)
                        else:
                            now = datetime.now()
                        time_diff = now - ha_start
                        ha_days = int(time_diff.total_seconds() // 86400)
                        ha_hours = int((time_diff.total_seconds() % 86400) // 3600)
                        ha_minutes = int((time_diff.total_seconds() % 3600) // 60)
                        ha_uptime_str = f"{ha_days}d {ha_hours}h {ha_minutes}m"
            except:
                pass

            # Get system uptime and last boot
            try:
                import time
                boot_time = psutil.boot_time()
                boot_time_dt = datetime.fromtimestamp(boot_time)
                uptime_seconds = time.time() - boot_time
                uptime_days = int(uptime_seconds // 86400)
                uptime_hours = int((uptime_seconds % 86400) // 3600)
                uptime_minutes = int((uptime_seconds % 3600) // 60)
                uptime_str = f"{uptime_days}d {uptime_hours}h {uptime_minutes}m"
                last_boot = boot_time_dt.strftime('%Y-%m-%d %H:%M:%S')
            except:
                uptime_str = "Unknown"
                last_boot = "Unknown"

            # Get public IP
            try:
                import socket
                public_ip = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: __import__('requests').get('https://api.ipify.org', timeout=5).text
                )
            except:
                public_ip = "Unable to fetch"

            # Check ping to 8.8.8.8
            try:
                import subprocess
                ping_result = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: subprocess.run(['ping', '-c', '1', '-W', '2', '8.8.8.8'],
                                         capture_output=True, text=True)
                )
                ping_status = "✅ Online" if ping_result.returncode == 0 else "❌ Failed"
            except:
                ping_status = "❓ Unknown"

            # Build HTML
            html = f"""
<h1>Home Assistant System Information</h1>
<p><em>Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</em></p>

<h2>🏠 Home Assistant Details</h2>
<table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse; width: 100%;">
    <tr>
        <td><strong>Version</strong></td>
        <td>{self._get_version_html(hass)}</td>
    </tr>
    <tr>
        <td><strong>Home Assistant</strong></td>
        <td>{self._get_ha_info(hass, ha_start_time, ha_uptime_str)}</td>
    </tr>
    <tr>
        <td><strong>System</strong></td>
        <td>First Boot: {last_boot} | Uptime: {uptime_str}</td>
    </tr>
    <tr>
        <td><strong>Instance ID</strong></td>
        <td>{ha_instance_id}</td>
    </tr>
    <tr>
        <td><strong>Local IP</strong></td>
        <td>{local_ip}</td>
    </tr>
    <tr>
        <td><strong>Public IP</strong></td>
        <td>{public_ip}</td>
    </tr>
    <tr>
        <td><strong>Ping to 8.8.8.8</strong></td>
        <td>{ping_status}</td>
    </tr>
</table>

<h2>💻 System Resources</h2>
<table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse; width: 100%;">
    <tr>
        <td><strong>CPU Usage</strong></td>
        <td>{cpu_percent}%</td>
    </tr>
    <tr>
        <td><strong>Memory Used</strong></td>
        <td>{memory.used / (1024**3):.2f} GB / {memory.total / (1024**3):.2f} GB ({memory.percent}%)</td>
    </tr>
    <tr>
        <td><strong>Memory Available</strong></td>
        <td>{memory.available / (1024**3):.2f} GB</td>
    </tr>
    <tr>
        <td><strong>Disk Used</strong></td>
        <td>{disk.used / (1024**3):.2f} GB / {disk.total / (1024**3):.2f} GB ({disk.percent}%)</td>
    </tr>
    <tr>
        <td><strong>Disk Free</strong></td>
        <td>{disk.free / (1024**3):.2f} GB</td>
    </tr>
</table>

<h2>📊 Entity Statistics</h2>
<table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse; width: 100%;">
    <tr>
        <td><strong>Total Entities</strong></td>
        <td>{len(hass.states.async_all())}</td>
    </tr>
    <tr>
        <td><strong>Sensors</strong></td>
        <td>{len([s for s in hass.states.async_all() if s.entity_id.startswith('sensor.')])}</td>
    </tr>
    <tr>
        <td><strong>Switches</strong></td>
        <td>{len([s for s in hass.states.async_all() if s.entity_id.startswith('switch.')])}</td>
    </tr>
    <tr>
        <td><strong>Lights</strong></td>
        <td>{len([s for s in hass.states.async_all() if s.entity_id.startswith('light.')])}</td>
    </tr>
    <tr>
        <td><strong>Automations</strong></td>
        <td>{len([s for s in hass.states.async_all() if s.entity_id.startswith('automation.')])}</td>
    </tr>
</table>

<h2>🤖 Automation Status</h2>
<table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse; width: 100%;">
    <tr style="background-color: #f0f0f0;">
        <th>Automation</th>
        <th>State</th>
        <th>Last Triggered</th>
    </tr>
"""

            # Get automation states
            automations = [s for s in hass.states.async_all() if s.entity_id.startswith('automation.')]

            # Sort by last_triggered, handling both datetime objects and strings
            def get_sort_key(x):
                from datetime import timezone
                last_trig = x.attributes.get('last_triggered')
                if not last_trig:
                    return datetime.min.replace(tzinfo=timezone.utc)
                if isinstance(last_trig, datetime):
                    # Ensure timezone aware
                    if last_trig.tzinfo is None:
                        return last_trig.replace(tzinfo=timezone.utc)
                    return last_trig
                try:
                    dt = date_parser.parse(str(last_trig))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    return dt
                except:
                    return datetime.min.replace(tzinfo=timezone.utc)

            for auto in sorted(automations, key=get_sort_key, reverse=True)[:20]:
                state_icon = "✅" if auto.state == "on" else "❌"
                last_triggered = auto.attributes.get('last_triggered', 'Never')
                if last_triggered and last_triggered != 'Never':
                    try:
                        last_trig_dt = date_parser.parse(last_triggered)
                        last_triggered = last_trig_dt.strftime('%Y-%m-%d %H:%M:%S')
                    except:
                        pass

                html += f"""
    <tr>
        <td>{auto.attributes.get('friendly_name', auto.entity_id)}</td>
        <td>{state_icon} {auto.state}</td>
        <td>{last_triggered}</td>
    </tr>
"""

            html += """
</table>

<h2>👥 Users</h2>
<table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse; width: 100%;">
    <tr style="background-color: #f0f0f0;">
        <th>User Name</th>
        <th>System Admin</th>
        <th>Active</th>
    </tr>
"""

            # Get simple user list
            try:
                auth_manager = hass.auth
                users = await auth_manager.async_get_users()

                for user in users:
                    if not user.system_generated:
                        is_admin = "Yes" if user.is_admin else "No"
                        is_active = "Yes" if user.is_active else "No"

                        html += f"""
    <tr>
        <td>{user.name}</td>
        <td>{is_admin}</td>
        <td>{is_active}</td>
    </tr>
"""
            except Exception as user_err:
                html += f"""
    <tr>
        <td colspan="3">Error loading user data: {user_err}</td>
    </tr>
"""

            html += """
</table>
"""

            # Add Proxmox info if configured
            try:
                from homeassistant.config_entries import ConfigEntry
                proxmox_html = await self._get_proxmox_info(hass)
                if proxmox_html:
                    html += proxmox_html
            except Exception as proxmox_err:
                _LOGGER.debug("No Proxmox info available: %s", proxmox_err)

            # Add Scheduler info if available
            scheduler_html = self._get_scheduler_info(hass)
            if scheduler_html:
                html += scheduler_html

            html += """
<h2>📋 Recent Home Assistant Logs</h2>
"""
            # Get recent HA logs
            try:
                import os
                log_file = hass.config.path("home-assistant.log")
                if os.path.exists(log_file):
                    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                        # Read last 100 lines
                        lines = f.readlines()
                        recent_logs = lines[-100:] if len(lines) > 100 else lines

                        html += """
<div style="background-color: #f5f5f5; padding: 10px; border: 1px solid #ddd; font-family: monospace; font-size: 12px; overflow-x: auto;">
<pre>"""
                        for line in recent_logs:
                            # Color code log levels
                            if "ERROR" in line:
                                html += f'<span style="color: red;">{line}</span>'
                            elif "WARNING" in line:
                                html += f'<span style="color: orange;">{line}</span>'
                            elif "INFO" in line:
                                html += f'<span style="color: blue;">{line}</span>'
                            else:
                                html += line
                        html += """</pre>
</div>
"""
                else:
                    html += "<p>Log file not found</p>"
            except Exception as log_err:
                html += f"<p>Error reading logs: {log_err}</p>"

            _LOGGER.debug("Completed get_system_info generation successfully")
            return html
        except Exception as e:
            import traceback
            _LOGGER.error("Failed to generate system info: %s", e, exc_info=True)
            _LOGGER.error("Traceback: %s", traceback.format_exc())
            return f"<p>Error generating system info: {e}</p>"

    async def get_automation_status(self, hass) -> str:
        """Generate HTML formatted automation status information."""
        try:
            from datetime import datetime

            html = """
<h1>Home Assistant Automation Status</h1>
<p><strong>Last Updated:</strong> """ + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + """</p>

<h2>Automation Status</h2>
<table border="1" cellpadding="5" cellspacing="0">
    <tr style="background-color: #f0f0f0;">
        <th>Automation Name</th>
        <th>Status</th>
        <th>Last Triggered</th>
        <th>Last Run</th>
    </tr>
"""

            # Get all automations
            automations = []
            for state in hass.states.async_all():
                if state.entity_id.startswith("automation."):
                    automations.append(state)

            # Sort by name
            automations.sort(key=lambda x: x.name or x.entity_id)

            for automation in automations:
                name = automation.name or automation.entity_id
                status = automation.state
                last_triggered = automation.attributes.get("last_triggered", "Never")

                # Get last run status (from last_triggered attribute if recent, or current mode)
                last_run_status = automation.attributes.get("current", "Unknown")
                if last_run_status == "Unknown":
                    # Check if automation ran successfully based on mode
                    mode = automation.attributes.get("mode", "single")
                    if mode == "queued" or mode == "parallel":
                        last_run_status = "Running"
                    else:
                        last_run_status = "Success" if last_triggered != "Never" else "Not Run"

                # Convert to string to avoid .lower() errors
                last_run_status_str = str(last_run_status) if last_run_status is not None else "Unknown"

                # Color code the run status
                if "success" in last_run_status_str.lower() or last_run_status_str == "Success":
                    run_color = "#90ee90"  # green
                elif "fail" in last_run_status_str.lower() or "error" in last_run_status_str.lower():
                    run_color = "#ffcccb"  # red
                else:
                    run_color = "#ffffcc"  # yellow

                # Format last triggered
                if last_triggered and last_triggered != "Never":
                    try:
                        from dateutil import parser as date_parser
                        dt = date_parser.parse(str(last_triggered))
                        last_triggered = dt.strftime('%Y-%m-%d %H:%M:%S')
                    except:
                        pass

                status_color = "#90ee90" if status == "on" else "#ffcccb"

                html += f"""
    <tr>
        <td>{name}</td>
        <td style="background-color: {status_color};">{status.upper()}</td>
        <td>{last_triggered}</td>
        <td style="background-color: {run_color};">{last_run_status}</td>
    </tr>
"""

            html += """
</table>
"""
            return html
        except Exception as e:
            _LOGGER.error("Failed to generate automation status: %s", e)
            return f"<p>Error generating automation status: {e}</p>"

    async def get_integrations_info(self, hass) -> str:
        """Generate HTML formatted integrations information."""
        try:
            from datetime import datetime
            from homeassistant.loader import async_get_integration

            html = """
<h1>Home Assistant Integrations</h1>
<p><strong>Last Updated:</strong> """ + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + """</p>

<h2>Entity Statistics</h2>
"""

            # Count entities by domain
            domain_counts = {}
            total_entities = 0
            for state in hass.states.async_all():
                domain = state.entity_id.split(".")[0]
                domain_counts[domain] = domain_counts.get(domain, 0) + 1
                total_entities += 1

            html += f"""<p><strong>Total Entities: {total_entities}</strong></p>
<table border="1" cellpadding="5" cellspacing="0">
    <tr style="background-color: #f0f0f0;">
        <th>Domain</th>
        <th>Count</th>
    </tr>
"""

            # Sort by domain name
            for domain in sorted(domain_counts.keys()):
                count = domain_counts[domain]
                html += f"""
    <tr>
        <td>{domain.replace('_', ' ').title()}</td>
        <td>{count}</td>
    </tr>
"""

            html += """
</table>

<h2>🔌 Installed Integrations</h2>
<table border="1" cellpadding="5" cellspacing="0">
    <tr style="background-color: #f0f0f0;">
        <th>Integration</th>
        <th>Domain</th>
        <th>Version</th>
        <th>Type</th>
        <th>Status</th>
        <th>Author</th>
        <th>GitHub Link</th>
    </tr>
"""

            # Get all config entries (installed integrations)
            integrations_added = set()
            for entry in hass.config_entries.async_entries():
                if entry.domain in integrations_added:
                    continue
                integrations_added.add(entry.domain)

                try:
                    integration = await async_get_integration(hass, entry.domain)
                    name = integration.name
                    version = integration.version or "Unknown"

                    # Determine if custom integration
                    is_custom = integration.pkg_path.startswith(hass.config.path("custom_components"))
                    integration_type = "🔧 Custom" if is_custom else "✅ Built-in"

                    # Check integration state
                    from homeassistant.config_entries import ConfigEntryState
                    status = "✅ Loaded"
                    status_color = "#90ee90"  # Light green
                    if entry.state == ConfigEntryState.SETUP_ERROR:
                        status = "❌ Setup Error"
                        status_color = "#ffcccb"  # Light red
                    elif entry.state == ConfigEntryState.SETUP_RETRY:
                        status = "⚠️ Setup Retry"
                        status_color = "#ffffcc"  # Light yellow
                    elif entry.state == ConfigEntryState.NOT_LOADED:
                        status = "❌ Not Loaded"
                        status_color = "#ffcccb"  # Light red
                    elif entry.state == ConfigEntryState.FAILED_UNLOAD:
                        status = "❌ Failed Unload"
                        status_color = "#ffcccb"  # Light red

                    # Get author from manifest
                    author = "Unknown"
                    if hasattr(integration, 'manifest'):
                        author = integration.manifest.get('codeowners', ['Unknown'])[0] if integration.manifest.get('codeowners') else "Unknown"
                        # Clean up author format (remove @ if present)
                        if isinstance(author, str) and author.startswith('@'):
                            author = author[1:]

                    # Try to construct GitHub link
                    github_link = "N/A"
                    if hasattr(integration, 'documentation'):
                        doc_url = integration.documentation
                        if 'github.com' in doc_url:
                            github_link = f'<a href="{doc_url}" target="_blank">GitHub</a>'

                    html += f"""
    <tr>
        <td>{name}</td>
        <td>{entry.domain}</td>
        <td>{version}</td>
        <td>{integration_type}</td>
        <td style="background-color: {status_color};">{status}</td>
        <td>{author}</td>
        <td>{github_link}</td>
    </tr>
"""
                except Exception:
                    # If we can't get integration info, just show the domain
                    html += f"""
    <tr>
        <td>{entry.domain}</td>
        <td>{entry.domain}</td>
        <td>Unknown</td>
        <td>Unknown</td>
        <td>Unknown</td>
        <td>Unknown</td>
        <td>N/A</td>
    </tr>
"""

            html += """
</table>

<h2>📦 Installed Add-ons</h2>
<table border="1" cellpadding="5" cellspacing="0">
    <tr style="background-color: #f0f0f0;">
        <th>Add-on</th>
        <th>Version</th>
        <th>State</th>
        <th>Auto Update</th>
        <th>Boot</th>
    </tr>
"""

            # Get add-on information from Supervisor (if available)
            addon_count = 0
            try:
                # Check if supervisor is available
                supervisor_sensors = [s for s in hass.states.async_all() if s.entity_id.startswith('sensor.') and 'addon' in s.entity_id.lower()]

                # Also check binary sensors for addon states
                addon_states = [s for s in hass.states.async_all() if s.entity_id.startswith('binary_sensor.') and 'addon' in s.entity_id.lower()]

                # Combine and process addon information
                addon_info = {}

                # Look for update sensors
                for sensor in supervisor_sensors:
                    if 'update' in sensor.entity_id:
                        addon_name = sensor.attributes.get('friendly_name', 'Unknown')
                        addon_info[sensor.entity_id] = {
                            'name': addon_name,
                            'version': sensor.attributes.get('installed_version', 'Unknown'),
                            'state': sensor.state,
                            'auto_update': sensor.attributes.get('auto_update', 'Unknown'),
                            'boot': sensor.attributes.get('boot', 'Unknown')
                        }

                # If we have addon info, display it
                if addon_info:
                    for addon_id, info in addon_info.items():
                        state_icon = "✅" if info['state'] == 'on' or info['state'] == 'started' else "❌"
                        addon_count += 1
                        html += f"""
    <tr>
        <td>{info['name']}</td>
        <td>{info['version']}</td>
        <td>{state_icon} {info['state']}</td>
        <td>{info['auto_update']}</td>
        <td>{info['boot']}</td>
    </tr>
"""
                else:
                    # Try alternative method - look for hassio integration
                    hassio_entities = [s for s in hass.states.async_all() if 'hassio' in s.entity_id or 'supervisor' in s.entity_id]

                    if hassio_entities:
                        html += """
    <tr>
        <td colspan="5">Add-on information available through Supervisor integration. Check sensor.hassio_* entities for details.</td>
    </tr>
"""
                    else:
                        html += """
    <tr>
        <td colspan="5">No add-ons detected or Supervisor not available (Core installation)</td>
    </tr>
"""
            except Exception as addon_err:
                _LOGGER.debug("Error getting addon info: %s", addon_err)
                html += """
    <tr>
        <td colspan="5">Unable to retrieve add-on information</td>
    </tr>
"""

            html += """
</table>
"""

            if addon_count > 0:
                _LOGGER.info("Found %d add-ons", addon_count)

            return html
        except Exception as e:
            _LOGGER.error("Failed to generate integrations info: %s", e)
            return f"<p>Error generating integrations info: {e}</p>"

    async def get_clients(self) -> dict[str, Any]:
        """Get all clients from ITFlow (for master accounts).

        Returns:
            API response with clients list
        """
        # For master accounts, don't pass client_id filter
        return await self._request("/clients/read.php", "GET", {})
