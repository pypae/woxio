"""Integration tests for Bexio API client.

These tests run against the live Bexio API.
Requires BEXIO_API_TOKEN environment variable to be set.

Run with: uv run pytest tests/integration/test_bexio.py -v
"""

import os
import uuid
from collections.abc import Generator
from datetime import date
from decimal import Decimal

import pytest

from woxio.bexio import BexioClient, BexioInvoice, BexioInvoiceItem
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

    def test_invoice_exists_for_reference_found(self, bexio_client: BexioClient) -> None:
        """Test checking for an existing invoice by Wodify ID."""
        # This invoice was previously synced from Wodify
        wodify_invoice_id = "test-7ea181d9-1235-4a6e-8edd-f7147b65cbb6"
        exists = bexio_client.invoice_exists_for_reference(wodify_invoice_id)
        assert exists is True

    def test_get_active_sales_taxes(self, bexio_client: BexioClient) -> None:
        """Test fetching active sales taxes."""
        taxes = bexio_client.get_active_sales_taxes()

        assert isinstance(taxes, list)
        print(f"\nFound {len(taxes)} active sales taxes")

        if taxes:
            tax = taxes[0]
            print(f"First tax ID: {tax['id']}, name: {tax.get('name', 'N/A')}")

    def test_get_accounts(self, bexio_client: BexioClient) -> None:
        """Test fetching accounting accounts."""
        accounts = bexio_client.get_accounts()

        assert isinstance(accounts, list)
        print(f"\nFound {len(accounts)} accounting accounts")

        if accounts:
            account = accounts[0]
            print(f"First account ID: {account['id']}, name: {account.get('name', 'N/A')}")

    def test_search_accounts_by_account_no(self, bexio_client: BexioClient) -> None:
        """Test searching accounting accounts by account number."""
        invoice_account_no = os.environ.get("BEXIO_INVOICE_ACCOUNT_NO")
        if not invoice_account_no:
            pytest.skip("BEXIO_INVOICE_ACCOUNT_NO not set")

        accounts = bexio_client.search_accounts_by_account_no(invoice_account_no)

        assert isinstance(accounts, list)
        print(f"\nFound {len(accounts)} accounts matching account_no {invoice_account_no}")

        if accounts:
            account = accounts[0]
            print(
                f"Account ID: {account['id']}, "
                f"account_no: {account.get('account_no', 'N/A')}, "
                f"name: {account.get('name', 'N/A')}"
            )

    def test_get_bank_accounts(self, bexio_client: BexioClient) -> None:
        """Test fetching bank accounts."""
        accounts = bexio_client.get_bank_accounts()

        assert isinstance(accounts, list)
        print(f"\nFound {len(accounts)} bank accounts")

        if accounts:
            account = accounts[0]
            print(f"First account ID: {account['id']}, IBAN: {account.get('iban', 'N/A')}")

    def test_create_and_delete_invoice(self, bexio_client: BexioClient) -> None:
        """Test creating an invoice and cleaning it up."""

        # Get a contact to use for the invoice
        contacts = bexio_client.get_contacts(limit=1)
        assert len(contacts) > 0, "Need at least one contact in Bexio for this test"
        contact_id = contacts[0].id

        # Get a valid tax ID for invoices
        taxes = bexio_client.get_active_sales_taxes()
        assert len(taxes) > 0, "Need at least one active sales tax in Bexio for this test"
        tax_id = taxes[0]["id"]
        # Get bank account ID from IBAN in environment
        invoice_iban = os.environ.get("BEXIO_INVOICE_IBAN")
        assert invoice_iban, "BEXIO_INVOICE_IBAN must be set in environment"
        bank_account_id = bexio_client.get_bank_account_id_by_iban(invoice_iban)
        assert bank_account_id is not None, f"No bank account found with IBAN {invoice_iban}"

        # Get a valid accounting account ID by account number from environment
        invoice_account_no = os.environ.get("BEXIO_INVOICE_ACCOUNT_NO")
        assert invoice_account_no, "BEXIO_INVOICE_ACCOUNT_NO must be set in environment"
        accounts = bexio_client.search_accounts_by_account_no(invoice_account_no)
        assert len(accounts) > 0, (
            f"No accounting account found with account_no {invoice_account_no}"
        )
        account_id = accounts[0]["id"]

        # Create a unique reference to avoid conflicts
        test_reference = f"test-{uuid.uuid4()}"

        invoice = BexioInvoice(
            contact_id=contact_id,
            user_id=1,  # Required: Bexio user ID
            bank_account_id=bank_account_id,
            title="Integration Test Invoice",
            api_reference=test_reference,
            is_valid_from=date.today(),
            positions=[
                BexioInvoiceItem(
                    amount=Decimal("1"),
                    unit_price=Decimal("10.00"),
                    text="Test item - please do not delete",
                    account_id=account_id,
                    tax_id=tax_id,
                ),
            ],
        )

        created_invoice = None
        try:
            # Create the invoice
            created_invoice = bexio_client.create_invoice(invoice)

            assert created_invoice.id is not None
            assert created_invoice.api_reference == test_reference
            assert created_invoice.title == "Integration Test Invoice"

            print(f"\nCreated invoice ID: {created_invoice.id}")

            # Verify we can find it by reference
            exists = bexio_client.invoice_exists_for_reference(test_reference)
            assert exists is True

        finally:
            # Always clean up - delete the invoice
            if created_invoice and created_invoice.id:
                deleted = bexio_client.delete_invoice(created_invoice.id)
                assert deleted is True
                print(f"Deleted invoice ID: {created_invoice.id}")


class TestBexioInvoiceModel:
    """Test Bexio invoice data model."""

    def test_invoice_model_dump(self) -> None:
        """Test converting invoice model to dict format."""
        invoice = BexioInvoice(
            contact_id=1,
            user_id=1,
            title="Test Invoice",
            api_reference="wodify-123",
            is_valid_from=date(2025, 1, 1),
            is_valid_to=date(2025, 1, 31),
            positions=[
                BexioInvoiceItem(
                    amount=Decimal("1"),
                    unit_price=Decimal("100.00"),
                    text="Monthly membership",
                    account_id=1,
                    tax_id=4,
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
        data = {
            "id": 123,
            "contact_id": 1,
            "user_id": 1,
            "title": "Test Invoice",
            "api_reference": "wodify-456",
            "positions": [],
            "mwst_type": 0,
            "mwst_is_net": True,
        }

        invoice = BexioInvoice.model_validate(data)

        assert invoice.id == 123
        assert invoice.contact_id == 1
        assert invoice.user_id == 1
        assert invoice.title == "Test Invoice"
        assert invoice.api_reference == "wodify-456"
