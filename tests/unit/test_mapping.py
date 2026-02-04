"""Unit tests for the Wodify to Bexio mapping."""

from datetime import date, datetime
from decimal import Decimal

import pytest

from woxio.bexio.models import BexioContact, BexioInvoice
from woxio.mapping import WodifyToBexioMapper
from woxio.wodify.models import (
    WodifyClient,
    WodifyCreated,
    WodifyInvoice,
    WodifyInvoiceDetail,
)

# Test constants
TEST_OWNER_ID = 1
TEST_REVENUE_ACCOUNT_ID = 3200
TEST_DEFAULT_COUNTRY_ID = 1
TEST_TAX_ID = 16
TEST_BANK_ACCOUNT_ID = 42


@pytest.fixture
def mapper() -> WodifyToBexioMapper:
    """Create a mapper with test configuration."""
    return WodifyToBexioMapper(
        owner_id=TEST_OWNER_ID,
        revenue_account_id=TEST_REVENUE_ACCOUNT_ID,
        default_country_id=TEST_DEFAULT_COUNTRY_ID,
    )


@pytest.fixture
def wodify_client() -> WodifyClient:
    """Create a sample Wodify client."""
    return WodifyClient(
        id=12345,
        first_name="John",
        last_name="Doe",
        email="john.doe@example.com",
        phone_number="+41 79 123 45 67",
        street_address_1="Bahnhofstrasse 1",
        city="Zürich",
        zipcode="8001",
        country="Switzerland",
        gender="Male",
    )


@pytest.fixture
def wodify_client_minimal() -> WodifyClient:
    """Create a Wodify client with minimal data."""
    return WodifyClient(
        id=99999,
        first_name="",
        last_name="",
        email="minimal@example.com",
    )


@pytest.fixture
def wodify_invoice() -> WodifyInvoice:
    """Create a sample Wodify invoice."""
    return WodifyInvoice(
        id=92421099,
        invoice_number="00003508",
        client_id=12345,
        invoice_header_status_id=1,
        invoice_header_status="Unpaid",
        payment_due=date(2025, 2, 15),
        final_charge=Decimal("87.50"),
        notes="Monthly membership fee",
        created=WodifyCreated(
            created_by_id=1,
            created_by="System",
            created_on_datetime=datetime(2025, 1, 15, 10, 30, 0),
        ),
    )


@pytest.fixture
def wodify_invoice_no_notes() -> WodifyInvoice:
    """Create a Wodify invoice without notes."""
    return WodifyInvoice(
        id=12345678,
        invoice_number="00001234",
        client_id=99999,
        invoice_header_status_id=2,
        invoice_header_status="Paid",
        payment_due=date(2025, 3, 1),
        paid_on_date=date(2025, 2, 20),
        final_charge=Decimal("150.00"),
        created=WodifyCreated(
            created_by_id=1,
            created_by="Admin",
            created_on_datetime=datetime(2025, 2, 1, 9, 0, 0),
        ),
    )


class TestMapClientToContact:
    """Tests for client to contact mapping."""

    def test_maps_basic_fields(
        self, mapper: WodifyToBexioMapper, wodify_client: WodifyClient
    ) -> None:
        """Test that basic fields are mapped correctly."""
        contact = mapper.map_client_to_contact(wodify_client)

        assert contact.contact_type_id == 2  # Person
        assert contact.name_1 == "Doe"  # Last name
        assert contact.name_2 == "John"  # First name
        assert contact.mail == "john.doe@example.com"
        assert contact.phone_mobile == "+41 79 123 45 67"

    def test_maps_address_fields(
        self, mapper: WodifyToBexioMapper, wodify_client: WodifyClient
    ) -> None:
        """Test that address fields are mapped correctly."""
        contact = mapper.map_client_to_contact(wodify_client)

        assert contact.street_name == "Bahnhofstrasse 1"
        assert contact.postcode == "8001"
        assert contact.city == "Zürich"
        assert contact.country_id == TEST_DEFAULT_COUNTRY_ID
        assert contact.salutation_id == 1  # Male -> Mr.

    def test_maps_owner_id(
        self, mapper: WodifyToBexioMapper, wodify_client: WodifyClient
    ) -> None:
        """Test that owner_id is set correctly."""
        contact = mapper.map_client_to_contact(wodify_client)

        # user_id is intentionally NOT set by the mapper - BexioClient
        # user_id will be set by BexioClient using owner_id
        assert contact.user_id is None
        assert contact.owner_id == TEST_OWNER_ID

    def test_stores_wodify_id_in_remarks(
        self, mapper: WodifyToBexioMapper, wodify_client: WodifyClient
    ) -> None:
        """Test that Wodify client ID is stored in remarks."""
        contact = mapper.map_client_to_contact(wodify_client)

        assert contact.remarks == "Wodify Client ID: 12345"

    def test_contact_has_no_id(
        self, mapper: WodifyToBexioMapper, wodify_client: WodifyClient
    ) -> None:
        """Test that the created contact has no ID (ready for creation)."""
        contact = mapper.map_client_to_contact(wodify_client)

        assert contact.id is None

    def test_handles_missing_last_name(
        self, mapper: WodifyToBexioMapper, wodify_client_minimal: WodifyClient
    ) -> None:
        """Test that missing last name defaults to 'Unknown'."""
        contact = mapper.map_client_to_contact(wodify_client_minimal)

        assert contact.name_1 == "Unknown"

    def test_handles_missing_first_name(
        self, mapper: WodifyToBexioMapper, wodify_client_minimal: WodifyClient
    ) -> None:
        """Test that missing first name becomes None."""
        contact = mapper.map_client_to_contact(wodify_client_minimal)

        assert contact.name_2 is None

    def test_handles_missing_optional_fields(
        self, mapper: WodifyToBexioMapper, wodify_client_minimal: WodifyClient
    ) -> None:
        """Test that missing optional fields are handled gracefully."""
        contact = mapper.map_client_to_contact(wodify_client_minimal)

        assert contact.phone_mobile is None
        assert contact.street_name is None
        assert contact.city is None
        assert contact.postcode is None
        assert contact.salutation_id is None
        assert contact.address_addition is None

    def test_maps_male_gender_to_salutation(self, mapper: WodifyToBexioMapper) -> None:
        """Test that male gender is mapped to salutation_id 1 (Mr.)."""
        client = WodifyClient(id=1, email="test@example.com", gender="Male")
        contact = mapper.map_client_to_contact(client)

        assert contact.salutation_id == 1

    def test_maps_female_gender_to_salutation(self, mapper: WodifyToBexioMapper) -> None:
        """Test that female gender is mapped to salutation_id 2 (Ms.)."""
        client = WodifyClient(id=1, email="test@example.com", gender="Female")
        contact = mapper.map_client_to_contact(client)

        assert contact.salutation_id == 2

    def test_maps_unknown_gender_to_none(self, mapper: WodifyToBexioMapper) -> None:
        """Test that unknown gender is mapped to None."""
        client = WodifyClient(id=1, email="test@example.com", gender="Other")
        contact = mapper.map_client_to_contact(client)

        assert contact.salutation_id is None

    def test_maps_address_addition(self, mapper: WodifyToBexioMapper) -> None:
        """Test that street_address_2 is mapped to address_addition."""
        client = WodifyClient(
            id=1,
            email="test@example.com",
            street_address_1="Main Street 1",
            street_address_2="Building C",
        )
        contact = mapper.map_client_to_contact(client)

        assert contact.street_name == "Main Street 1"
        assert contact.address_addition == "Building C"

    def test_result_is_valid_bexio_contact(
        self, mapper: WodifyToBexioMapper, wodify_client: WodifyClient
    ) -> None:
        """Test that the result is a valid BexioContact instance."""
        contact = mapper.map_client_to_contact(wodify_client)

        assert isinstance(contact, BexioContact)
        # Should be serializable
        data = contact.model_dump(mode="json", exclude_none=True)
        assert "name_1" in data
        assert "contact_type_id" in data


class TestMapInvoice:
    """Tests for invoice mapping."""

    def test_maps_basic_fields(
        self, mapper: WodifyToBexioMapper, wodify_invoice: WodifyInvoice
    ) -> None:
        """Test that basic invoice fields are mapped correctly."""
        contact_id = 651
        invoice = mapper.map_invoice(
            wodify_invoice,
            contact_id,
            tax_id=TEST_TAX_ID,
            bank_account_id=TEST_BANK_ACCOUNT_ID,
        )

        assert invoice.contact_id == 651
        assert invoice.title == "Wodify Invoice 00003508"
        assert invoice.api_reference == "92421099"

    def test_maps_date_fields(
        self, mapper: WodifyToBexioMapper, wodify_invoice: WodifyInvoice
    ) -> None:
        """Test that date fields are mapped correctly."""
        invoice = mapper.map_invoice(
            wodify_invoice,
            contact_id=1,
            tax_id=TEST_TAX_ID,
            bank_account_id=TEST_BANK_ACCOUNT_ID,
        )

        # is_valid_from = payment_due, is_valid_to = payment_due + 30 days
        assert invoice.is_valid_from == date(2025, 2, 15)
        assert invoice.is_valid_to == date(2025, 3, 17)

    def test_uses_passed_ids(
        self, mapper: WodifyToBexioMapper, wodify_invoice: WodifyInvoice
    ) -> None:
        """Test that passed IDs are used correctly."""
        invoice = mapper.map_invoice(
            wodify_invoice,
            contact_id=1,
            tax_id=TEST_TAX_ID,
            bank_account_id=TEST_BANK_ACCOUNT_ID,
        )

        # user_id comes from owner_id
        assert invoice.user_id == TEST_OWNER_ID
        # bank_account_id is passed as parameter
        assert invoice.bank_account_id == TEST_BANK_ACCOUNT_ID

    def test_creates_line_item_with_amount(
        self, mapper: WodifyToBexioMapper, wodify_invoice: WodifyInvoice
    ) -> None:
        """Test that a line item is created with the correct amount."""
        invoice = mapper.map_invoice(
            wodify_invoice,
            contact_id=1,
            tax_id=TEST_TAX_ID,
            bank_account_id=TEST_BANK_ACCOUNT_ID,
        )

        assert len(invoice.positions) == 1
        position = invoice.positions[0]
        assert position.amount == Decimal("1")
        assert position.unit_price == Decimal("87.50")

    def test_line_item_uses_passed_ids(
        self, mapper: WodifyToBexioMapper, wodify_invoice: WodifyInvoice
    ) -> None:
        """Test that line item uses passed account and tax IDs."""
        invoice = mapper.map_invoice(
            wodify_invoice,
            contact_id=1,
            tax_id=TEST_TAX_ID,
            bank_account_id=TEST_BANK_ACCOUNT_ID,
        )

        position = invoice.positions[0]
        assert position.account_id == TEST_REVENUE_ACCOUNT_ID
        assert position.tax_id == TEST_TAX_ID

    def test_line_item_uses_notes(
        self, mapper: WodifyToBexioMapper, wodify_invoice: WodifyInvoice
    ) -> None:
        """Test that line item text uses invoice notes."""
        invoice = mapper.map_invoice(
            wodify_invoice,
            contact_id=1,
            tax_id=TEST_TAX_ID,
            bank_account_id=TEST_BANK_ACCOUNT_ID,
        )

        position = invoice.positions[0]
        # Line item text should be the notes only
        assert position.text == "Monthly membership fee"

    def test_line_item_without_notes(
        self, mapper: WodifyToBexioMapper, wodify_invoice_no_notes: WodifyInvoice
    ) -> None:
        """Test line item text when invoice has no notes."""
        invoice = mapper.map_invoice(
            wodify_invoice_no_notes,
            contact_id=1,
            tax_id=TEST_TAX_ID,
            bank_account_id=TEST_BANK_ACCOUNT_ID,
        )

        position = invoice.positions[0]
        assert position.text == "Invoice 00001234"

    def test_custom_line_item_text(
        self, mapper: WodifyToBexioMapper, wodify_invoice: WodifyInvoice
    ) -> None:
        """Test that custom line item text can be provided."""
        invoice = mapper.map_invoice(
            wodify_invoice,
            contact_id=1,
            tax_id=TEST_TAX_ID,
            bank_account_id=TEST_BANK_ACCOUNT_ID,
            line_item_text="Custom description",
        )

        position = invoice.positions[0]
        # Custom text overrides notes
        assert position.text == "Custom description"

    def test_invoice_has_no_id(
        self, mapper: WodifyToBexioMapper, wodify_invoice: WodifyInvoice
    ) -> None:
        """Test that the created invoice has no ID (ready for creation)."""
        invoice = mapper.map_invoice(
            wodify_invoice,
            contact_id=1,
            tax_id=TEST_TAX_ID,
            bank_account_id=TEST_BANK_ACCOUNT_ID,
        )

        assert invoice.id is None

    def test_vat_settings(
        self, mapper: WodifyToBexioMapper, wodify_invoice: WodifyInvoice
    ) -> None:
        """Test that VAT settings are correctly set."""
        invoice = mapper.map_invoice(
            wodify_invoice,
            contact_id=1,
            tax_id=TEST_TAX_ID,
            bank_account_id=TEST_BANK_ACCOUNT_ID,
        )

        assert invoice.mwst_type == 0  # VAT type: inclusive
        assert invoice.mwst_is_net is False  # Prices are gross (VAT included)

    def test_result_is_valid_bexio_invoice(
        self, mapper: WodifyToBexioMapper, wodify_invoice: WodifyInvoice
    ) -> None:
        """Test that the result is a valid BexioInvoice instance."""
        invoice = mapper.map_invoice(
            wodify_invoice,
            contact_id=1,
            tax_id=TEST_TAX_ID,
            bank_account_id=TEST_BANK_ACCOUNT_ID,
        )

        assert isinstance(invoice, BexioInvoice)
        # Should be serializable
        data = invoice.model_dump(mode="json", exclude_none=True)
        assert "contact_id" in data
        assert "positions" in data


class TestMapInvoiceWithClient:
    """Tests for invoice mapping with client context."""

    def test_uses_product_name_when_available(
        self,
        mapper: WodifyToBexioMapper,
        wodify_client: WodifyClient,
    ) -> None:
        """Test that product name from invoice details is used."""
        # Create invoice with invoice_details
        invoice_with_details = WodifyInvoice(
            id=92421099,
            invoice_number="00003508",
            client_id=12345,
            invoice_header_status_id=1,
            invoice_header_status="Unpaid",
            payment_due=date(2025, 2, 15),
            final_charge=Decimal("87.50"),
            notes="First month's membership",
            created=WodifyCreated(
                created_by_id=1,
                created_by="System",
                created_on_datetime=datetime(2025, 1, 15, 10, 30, 0),
            ),
            invoice_details=[
                WodifyInvoiceDetail(
                    product_id=263919,
                    product="1x Training pro Woche: Membership fee",
                    quantity=1,
                    sales_price=Decimal("87.50"),
                    final_charge=Decimal("87.50"),
                )
            ],
        )

        result = mapper.map_invoice_with_client(
            invoice_with_details,
            wodify_client,
            contact_id=1,
            tax_id=TEST_TAX_ID,
            bank_account_id=TEST_BANK_ACCOUNT_ID,
        )

        # Title should use product name
        assert result.title == "1x Training pro Woche: Membership fee"
        # Line item should use notes only (not product name)
        position = result.positions[0]
        assert position.text == "First month's membership"

    def test_still_maps_all_invoice_fields(
        self,
        mapper: WodifyToBexioMapper,
        wodify_invoice: WodifyInvoice,
        wodify_client: WodifyClient,
    ) -> None:
        """Test that all invoice fields are still mapped correctly."""
        invoice = mapper.map_invoice_with_client(
            wodify_invoice,
            wodify_client,
            contact_id=651,
            tax_id=TEST_TAX_ID,
            bank_account_id=TEST_BANK_ACCOUNT_ID,
        )

        assert invoice.contact_id == 651
        assert invoice.api_reference == "92421099"
        assert invoice.is_valid_from == date(2025, 2, 15)  # payment_due
        assert len(invoice.positions) == 1


class TestMapperConfiguration:
    """Tests for different mapper configurations."""

    def test_different_owner_id(self) -> None:
        """Test that different owner_id is used correctly."""
        mapper = WodifyToBexioMapper(
            owner_id=88,
            revenue_account_id=4000,
            default_country_id=2,
        )

        client = WodifyClient(id=1, email="test@example.com")
        contact = mapper.map_client_to_contact(client)

        assert contact.user_id is None
        assert contact.owner_id == 88
        assert contact.country_id == 2

    def test_no_default_country(self) -> None:
        """Test mapping when no default country is configured."""
        mapper = WodifyToBexioMapper(
            owner_id=1,
            revenue_account_id=3200,
            default_country_id=None,
        )

        client = WodifyClient(id=1, email="test@example.com")
        contact = mapper.map_client_to_contact(client)

        assert contact.country_id is None

    def test_invoice_uses_owner_id_as_user_id(self) -> None:
        """Test that invoice user_id comes from owner_id."""
        mapper = WodifyToBexioMapper(
            owner_id=99,
            revenue_account_id=3200,
        )

        invoice = WodifyInvoice(
            id=1,
            invoice_number="00001",
            client_id=1,
            invoice_header_status_id=1,
            invoice_header_status="Unpaid",
            payment_due=date(2025, 1, 1),
            final_charge=Decimal("100.00"),
            created=WodifyCreated(
                created_by_id=1,
                created_by="Test",
                created_on_datetime=datetime(2025, 1, 1),
            ),
        )
        bexio_invoice = mapper.map_invoice(
            invoice,
            contact_id=1,
            tax_id=16,
            bank_account_id=42,
        )

        assert bexio_invoice.user_id == 99
