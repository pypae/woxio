"""Integration tests for Bexio API client.

These tests run against the live Bexio API.
Requires BEXIO_API_TOKEN environment variable to be set.

Run with: uv run pytest tests/integration/test_bexio.py -v
"""

import os
from collections.abc import Generator

import pytest

from woxio.bexio import BexioClient
from woxio.config import BexioConfig


@pytest.fixture
def bexio_config() -> BexioConfig:
    """Get Bexio configuration from environment."""
    api_token = os.environ.get("BEXIO_API_TOKEN")
    if not api_token:
        pytest.skip("BEXIO_API_TOKEN not set")
    return BexioConfig(api_token=api_token)


@pytest.fixture
def bexio_client(bexio_config: BexioConfig) -> Generator[BexioClient]:
    """Create a Bexio client."""
    client = BexioClient(bexio_config)
    yield client
    client.close()


class TestBexioClient:
    """Integration tests for BexioClient."""

    def test_get_invoices(self, bexio_client: BexioClient) -> None:
        """Test fetching invoices from Bexio."""
        invoices = bexio_client.get_invoices(limit=10)

        # Should return a list (may be empty)
        assert isinstance(invoices, list)

        print(f"\nFound {len(invoices)} invoices")

        # If there are invoices, check their structure
        if invoices:
            invoice = invoices[0]
            assert invoice.id is not None
            print(f"First invoice ID: {invoice.id}")
            print(f"First invoice title: {invoice.title}")
            print(f"First invoice api_reference: {invoice.api_reference}")

    def test_get_contacts(self, bexio_client: BexioClient) -> None:
        """Test fetching contacts from Bexio."""
        contacts = bexio_client.get_contacts(limit=10)

        # Should return a list (may be empty)
        assert isinstance(contacts, list)

        print(f"\nFound {len(contacts)} contacts")

        # If there are contacts, check their structure
        if contacts:
            contact = contacts[0]
            assert contact.id is not None
            print(f"First contact ID: {contact.id}")
            print(f"First contact name: {contact.name}")
            print(f"First contact mail: {contact.mail}")

    def test_invoice_exists_for_reference_not_found(self, bexio_client: BexioClient) -> None:
        """Test checking for non-existent invoice reference."""
        # Use a reference that shouldn't exist
        exists = bexio_client.invoice_exists_for_reference("non-existent-wodify-id-12345")
        assert exists is False


class TestBexioInvoiceModel:
    """Test Bexio invoice data model."""

    def test_invoice_model_dump(self) -> None:
        """Test converting invoice model to dict format."""
        from datetime import date
        from decimal import Decimal

        from woxio.bexio import BexioInvoice, BexioInvoiceItem

        invoice = BexioInvoice(
            contact_id=1,
            title="Test Invoice",
            api_reference="wodify-123",
            is_valid_from=date(2025, 1, 1),
            is_valid_to=date(2025, 1, 31),
            positions=[
                BexioInvoiceItem(
                    amount=Decimal("1"),
                    unit_price=Decimal("100.00"),
                    text="Monthly membership",
                    account_id=3200,
                    tax_id=1,
                ),
            ],
        )

        api_data = invoice.model_dump(exclude_none=True, exclude={"id"})

        assert api_data["contact_id"] == 1
        assert api_data["title"] == "Test Invoice"
        assert api_data["api_reference"] == "wodify-123"
        assert api_data["is_valid_from"] == date(2025, 1, 1)
        assert api_data["is_valid_to"] == date(2025, 1, 31)
        assert len(api_data["positions"]) == 1
        assert api_data["positions"][0]["text"] == "Monthly membership"
        assert api_data["positions"][0]["unit_price"] == Decimal("100.00")

        print(f"\nModel dump: {api_data}")

    def test_invoice_model_validate(self) -> None:
        """Test parsing invoice from dict."""
        from woxio.bexio import BexioInvoice

        data = {
            "id": 123,
            "contact_id": 1,
            "title": "Test Invoice",
            "api_reference": "wodify-456",
            "positions": [],
            "mwst_type": 0,
            "mwst_is_net": True,
            "kb_item_status_id": 7,
        }

        invoice = BexioInvoice.model_validate(data)

        assert invoice.id == 123
        assert invoice.contact_id == 1
        assert invoice.title == "Test Invoice"
        assert invoice.api_reference == "wodify-456"
