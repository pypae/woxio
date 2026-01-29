"""Bexio API client."""

from typing import Any

import httpx

from woxio.config import BexioConfig

from .models import BexioContact, BexioInvoice


class BexioClient:
    """Client for the Bexio API."""

    def __init__(self, config: BexioConfig) -> None:
        """Initialize the Bexio client.

        Args:
            config: Bexio API configuration.
        """
        self.config = config
        self._client: httpx.Client | None = None

    @property
    def client(self) -> httpx.Client:
        """Get or create the HTTP client."""
        if self._client is None:
            self._client = httpx.Client(
                base_url=self.config.base_url,
                headers={
                    "Authorization": f"Bearer {self.config.api_token}",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )
        return self._client

    def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> "BexioClient":
        """Context manager entry."""
        return self

    def __exit__(self, *args: object) -> None:
        """Context manager exit."""
        self.close()

    # Invoice endpoints

    def get_invoices(
        self,
        *,
        api_reference: str | None = None,
        limit: int = 500,
        offset: int = 0,
    ) -> list[BexioInvoice]:
        """Get invoices from Bexio.

        Args:
            api_reference: Filter by api_reference field (for finding linked invoices).
            limit: Maximum number of invoices to return.
            offset: Offset for pagination.

        Returns:
            List of Bexio invoices.
        """
        params: dict[str, str | int] = {
            "limit": limit,
            "offset": offset,
        }

        # Use search endpoint if filtering by api_reference
        if api_reference:
            # Bexio uses POST for search with filters
            search_params = [
                {
                    "field": "api_reference",
                    "value": api_reference,
                    "criteria": "=",
                }
            ]
            response = self.client.post(
                "/2.0/kb_invoice/search",
                json=search_params,
                params=params,
            )
        else:
            response = self.client.get("/2.0/kb_invoice", params=params)

        response.raise_for_status()
        data = response.json()

        return [BexioInvoice.model_validate(inv) for inv in data]

    def get_invoice(self, invoice_id: int) -> BexioInvoice:
        """Get a single invoice by ID.

        Args:
            invoice_id: The Bexio invoice ID.

        Returns:
            The Bexio invoice.
        """
        response = self.client.get(f"/2.0/kb_invoice/{invoice_id}")
        response.raise_for_status()
        return BexioInvoice.model_validate(response.json())

    def create_invoice(self, invoice: BexioInvoice) -> BexioInvoice:
        """Create a new invoice in Bexio.

        Args:
            invoice: The invoice to create.

        Returns:
            The created invoice with ID populated.
        """
        response = self.client.post(
            "/2.0/kb_invoice",
            json=invoice.model_dump(exclude_none=True, exclude={"id"}),
        )
        response.raise_for_status()
        return BexioInvoice.model_validate(response.json())

    def issue_invoice(self, invoice_id: int) -> BexioInvoice:
        """Issue a draft invoice (change status from draft to open).

        Args:
            invoice_id: The invoice ID to issue.

        Returns:
            The updated invoice.
        """
        response = self.client.post(f"/2.0/kb_invoice/{invoice_id}/issue")
        response.raise_for_status()
        return BexioInvoice.model_validate(response.json())

    def invoice_exists_for_reference(self, api_reference: str) -> bool:
        """Check if an invoice already exists with the given api_reference.

        Args:
            api_reference: The external reference (e.g., Wodify invoice ID).

        Returns:
            True if an invoice exists with this reference.
        """
        invoices = self.get_invoices(api_reference=api_reference)
        return len(invoices) > 0

    # Contact endpoints

    def get_contacts(
        self,
        *,
        limit: int = 500,
        offset: int = 0,
    ) -> list[BexioContact]:
        """Get contacts from Bexio.

        Args:
            limit: Maximum number of contacts to return.
            offset: Offset for pagination.

        Returns:
            List of Bexio contacts.
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        response = self.client.get("/2.0/contact", params=params)
        response.raise_for_status()
        return [BexioContact.model_validate(c) for c in response.json()]

    def search_contacts_by_email(self, email: str) -> list[BexioContact]:
        """Search for contacts by email address.

        Args:
            email: The email address to search for.

        Returns:
            List of matching contacts.
        """
        search_params = [
            {
                "field": "mail",
                "value": email,
                "criteria": "=",
            }
        ]
        response = self.client.post("/2.0/contact/search", json=search_params)
        response.raise_for_status()
        return [BexioContact.model_validate(c) for c in response.json()]
