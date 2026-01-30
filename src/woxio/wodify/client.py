"""Wodify API client."""

from collections.abc import Iterator
from datetime import datetime

import httpx

from woxio.config import WodifyConfig

from .models import WodifyClient as WodifyClientModel
from .models import WodifyInvoice, WodifyInvoicesResponse


class WodifyClient:
    """Client for the Wodify API."""

    def __init__(self, config: WodifyConfig) -> None:
        """Initialize the Wodify client.

        Args:
            config: Wodify API configuration.
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
                    "X-Api-Key": self.config.api_key,
                    "Accept": "application/json",
                },
                timeout=30.0,
            )
        return self._client

    def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> "WodifyClient":
        """Context manager entry."""
        return self

    def __exit__(self, *args: object) -> None:
        """Context manager exit."""
        self.close()

    def get_invoices(
        self,
        *,
        sort: str | None = "desc_created_on_datetime",
        page: int | None = None,
        page_size: int | None = None,
    ) -> WodifyInvoicesResponse:
        """Get invoices from Wodify.

        Args:
            sort: Sort order, e.g. "created_date" or "desc_created_date".
            page: Page number (defaults to 1).
            page_size: Number of invoices per page (max 100).

        Returns:
            Response containing invoices and pagination info.
        """
        params: dict[str, str | int] = {}
        if sort:
            params["sort"] = sort
        if page:
            params["page"] = page
        if page_size:
            params["page_size"] = page_size

        response = self.client.get("/financials/invoices", params=params)
        response.raise_for_status()

        return WodifyInvoicesResponse.model_validate(response.json())

    def get_invoice(self, invoice_id: int) -> WodifyInvoice:
        """Get a single invoice by ID.

        Args:
            invoice_id: The Wodify invoice ID.

        Returns:
            The Wodify invoice.
        """
        response = self.client.get(f"/financials/invoices/{invoice_id}")
        response.raise_for_status()

        return WodifyInvoice.model_validate(response.json())

    def get_client(self, client_id: int) -> WodifyClientModel:
        """Get a client (customer/member) by ID.

        Args:
            client_id: The Wodify client ID.

        Returns:
            The Wodify client.
        """
        response = self.client.get(f"/clients/{client_id}")
        response.raise_for_status()

        return WodifyClientModel.model_validate(response.json())

    def get_recent_invoices(
        self,
        cutoff: datetime,
        page_size: int = 100,
    ) -> Iterator[WodifyInvoice]:
        """Get recent invoices created after the cutoff date.

        Paginates through invoices (sorted by created_on_datetime descending)
        until reaching invoices older than the cutoff time.

        Args:
            cutoff: Stop iterating when reaching invoices created before this datetime.
            page_size: Number of invoices per page (max 100).

        Yields:
            Invoices created on or after the cutoff date.
        """
        page = 1

        while True:
            response = self.get_invoices(
                sort="desc_created_on_datetime",
                page=page,
                page_size=page_size,
            )

            for invoice in response.invoices:
                # Check if we've reached invoices older than the cutoff
                if invoice.created.created_on_datetime < cutoff:
                    return

                yield invoice

            # Check if there are more pages
            if not response.pagination.has_more:
                break

            page += 1
