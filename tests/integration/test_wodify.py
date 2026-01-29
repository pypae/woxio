"""Integration tests for Wodify API client.

These tests run against the live Wodify API.
Requires WODIFY_API_KEY environment variable to be set.

Run with: uv run pytest tests/integration/test_wodify.py -v
"""

import os
from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest

from woxio.config import WodifyConfig
from woxio.wodify import WodifyClient, WodifyInvoicesResponse


@pytest.fixture
def wodify_config() -> WodifyConfig:
    """Get Wodify configuration from environment."""
    api_key = os.environ.get("WODIFY_API_KEY")
    if not api_key:
        pytest.skip("WODIFY_API_KEY not set")
    return WodifyConfig(api_key=api_key)


@pytest.fixture
def wodify_client(wodify_config: WodifyConfig) -> Generator[WodifyClient]:
    """Create a Wodify client."""
    client = WodifyClient(wodify_config)
    yield client
    client.close()


class TestWodifyClient:
    """Integration tests for WodifyClient."""

    def test_get_invoices(self, wodify_client: WodifyClient) -> None:
        """Test fetching invoices from Wodify."""
        response = wodify_client.get_invoices()

        # Should return a response object
        assert isinstance(response, WodifyInvoicesResponse)
        assert isinstance(response.invoices, list)
        assert response.pagination is not None

        # If there are invoices, check their structure
        if response.invoices:
            invoice = response.invoices[0]
            assert invoice.id is not None
            print(f"\nFound {len(response.invoices)} invoices")
            pagination = response.pagination
            print(f"Pagination: page={pagination.page}, page_size={pagination.page_size}, "
                  f"has_more={pagination.has_more}")
            print(f"First invoice ID: {invoice.id}")
            print(f"First invoice status: {invoice.invoice_header_status}")
            print(f"First invoice final_charge: {invoice.final_charge}")

    def test_get_invoices_with_page_size(self, wodify_client: WodifyClient) -> None:
        """Test fetching invoices with a page size."""
        response = wodify_client.get_invoices(page_size=5)

        assert isinstance(response, WodifyInvoicesResponse)
        assert len(response.invoices) <= 5

    def test_get_invoices_sorted_descending(self, wodify_client: WodifyClient) -> None:
        """Test fetching invoices sorted by id descending."""
        response = wodify_client.get_invoices(sort="paid_on", page_size=10)

        assert isinstance(response, WodifyInvoicesResponse)

        if len(response.invoices) > 1:
            ids = [inv.id for inv in response.invoices]
            print(f"\nInvoices sorted by paid_on: {ids}")

    def test_get_recent_invoices(self, wodify_client: WodifyClient) -> None:
        """Test fetching recent invoices with a cutoff date."""
        from woxio.wodify import WodifyInvoice

        # Set cutoff to 30 days ago
        cutoff = datetime.now(UTC) - timedelta(days=30)

        invoices = list(wodify_client.get_recent_invoices(cutoff))

        print(f"\nFound {len(invoices)} invoices created after {cutoff.isoformat()}")

        # All returned invoices should be created on or after the cutoff
        for invoice in invoices:
            assert isinstance(invoice, WodifyInvoice)
            assert invoice.created.created_on_datetime >= cutoff, (
                f"Invoice {invoice.id} created at {invoice.created.created_on_datetime} "
                f"is before cutoff {cutoff}"
            )

        # If we have invoices, they should be in descending order by created date
        if len(invoices) > 1:
            for i in range(len(invoices) - 1):
                assert (
                    invoices[i].created.created_on_datetime
                    >= invoices[i + 1].created.created_on_datetime
                ), "Invoices should be in descending order by created date"

    def test_get_recent_invoices_with_future_cutoff(
        self, wodify_client: WodifyClient
    ) -> None:
        """Test that future cutoff returns no invoices."""
        # Set cutoff to tomorrow - should return no invoices
        cutoff = datetime.now(UTC) + timedelta(days=1)

        invoices = list(wodify_client.get_recent_invoices(cutoff))

        assert len(invoices) == 0, "Future cutoff should return no invoices"


class TestWodifyInvoiceModel:
    """Test Wodify invoice data model."""

    def test_invoice_model_validate(self) -> None:
        """Test parsing invoice from dict (simulating API response)."""
        from decimal import Decimal

        from woxio.wodify import WodifyInvoice

        data = {
            "id": 92421096,
            "invoice_number": "00003505",
            "client_id": 6114148,
            "invoice_header_status_id": 4,
            "invoice_header_status": "Paid",
            "payment_due": "2026-09-29",
            "paid_on_date": "2026-01-29",
            "final_charge": 87.5,
            "notes": "Monthly membership",
            "invoice_footer": "Thank you!",
            "created": {
                "created_by_id": 6114148,
                "created_by": "Patrick Düggelin",
                "created_on_datetime": "2026-01-29T17:49:15Z",
            },
        }

        invoice = WodifyInvoice.model_validate(data)

        assert invoice.id == 92421096
        assert invoice.invoice_number == "00003505"
        assert invoice.client_id == 6114148
        assert invoice.invoice_header_status == "Paid"
        assert invoice.is_paid is True
        assert invoice.final_charge == Decimal("87.5")
        assert invoice.notes == "Monthly membership"
        assert invoice.created.created_by == "Patrick Düggelin"
