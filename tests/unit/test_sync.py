"""Unit tests for the InvoiceSyncService."""

from datetime import date, datetime
from decimal import Decimal
from unittest.mock import Mock

import pytest

from woxio.bexio.models import BexioContact, BexioInvoice
from woxio.config import SyncConfig
from woxio.sync import InvoiceSyncService
from woxio.wodify.models import WodifyClient, WodifyCreated, WodifyInvoice

# Test constants
TEST_TAX_ID = 16
TEST_BANK_ACCOUNT_ID = 42
TEST_REVENUE_ACCOUNT_ID = 123  # Internal Bexio ID for account_no 3200


@pytest.fixture
def sync_config() -> SyncConfig:
    """Create a test sync configuration."""
    return SyncConfig(
        owner_id=1,
        revenue_account_no=3200,
        bank_iban="CH00 0000 0000 0000 0000 0",
        default_country_id=1,
    )


@pytest.fixture
def mock_bexio_client() -> Mock:
    """Create a mock BexioClient."""
    client = Mock()
    client.get_active_sales_taxes.return_value = [{"id": TEST_TAX_ID, "name": "VAT"}]
    client.get_bank_account_id_by_iban.return_value = TEST_BANK_ACCOUNT_ID
    client.search_accounts_by_account_no.return_value = [
        {"id": TEST_REVENUE_ACCOUNT_ID, "account_no": "3200"}
    ]
    client.invoice_exists_for_reference.return_value = False
    return client


@pytest.fixture
def mock_wodify_client() -> Mock:
    """Create a mock WodifyClient."""
    return Mock()


@pytest.fixture
def sync_service(
    sync_config: SyncConfig,
    mock_bexio_client: Mock,
    mock_wodify_client: Mock,
) -> InvoiceSyncService:
    """Create an initialized sync service."""
    service = InvoiceSyncService(sync_config, mock_bexio_client, mock_wodify_client)
    service.initialize()
    return service


@pytest.fixture
def sync_service_uninitialized(
    sync_config: SyncConfig,
    mock_bexio_client: Mock,
    mock_wodify_client: Mock,
) -> InvoiceSyncService:
    """Create an uninitialized sync service."""
    return InvoiceSyncService(sync_config, mock_bexio_client, mock_wodify_client)


@pytest.fixture
def wodify_client_model() -> WodifyClient:
    """Create a sample Wodify client model."""
    return WodifyClient(
        id=12345,
        first_name="John",
        last_name="Doe",
        email="john.doe@example.com",
        phone="+41 79 123 45 67",
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


class TestInitialize:
    """Tests for the initialize method."""

    def test_fetches_tax_id_from_api(
        self,
        sync_config: SyncConfig,
        mock_bexio_client: Mock,
        mock_wodify_client: Mock,
    ) -> None:
        """Test that tax_id is fetched from the API."""
        service = InvoiceSyncService(sync_config, mock_bexio_client, mock_wodify_client)
        service.initialize()

        assert service.tax_id == TEST_TAX_ID
        mock_bexio_client.get_active_sales_taxes.assert_called_once()

    def test_fetches_bank_account_id_by_iban(
        self,
        sync_config: SyncConfig,
        mock_bexio_client: Mock,
        mock_wodify_client: Mock,
    ) -> None:
        """Test that bank_account_id is fetched by IBAN lookup."""
        service = InvoiceSyncService(sync_config, mock_bexio_client, mock_wodify_client)
        service.initialize()

        assert service.bank_account_id == TEST_BANK_ACCOUNT_ID
        mock_bexio_client.get_bank_account_id_by_iban.assert_called_once_with(
            "CH00 0000 0000 0000 0000 0"
        )

    def test_creates_mapper(
        self,
        sync_config: SyncConfig,
        mock_bexio_client: Mock,
        mock_wodify_client: Mock,
    ) -> None:
        """Test that mapper is created after initialization."""
        service = InvoiceSyncService(sync_config, mock_bexio_client, mock_wodify_client)
        service.initialize()

        mapper = service.mapper
        assert mapper.owner_id == 1
        assert mapper.revenue_account_id == TEST_REVENUE_ACCOUNT_ID
        assert mapper.default_country_id == 1

    def test_fetches_revenue_account_id_by_account_no(
        self,
        sync_config: SyncConfig,
        mock_bexio_client: Mock,
        mock_wodify_client: Mock,
    ) -> None:
        """Test that revenue_account_id is fetched by account number lookup."""
        service = InvoiceSyncService(sync_config, mock_bexio_client, mock_wodify_client)
        service.initialize()

        assert service.revenue_account_id == TEST_REVENUE_ACCOUNT_ID
        mock_bexio_client.search_accounts_by_account_no.assert_called_once_with("3200")

    def test_raises_error_when_no_taxes_found(
        self,
        sync_config: SyncConfig,
        mock_wodify_client: Mock,
    ) -> None:
        """Test that RuntimeError is raised when no taxes are found."""
        bexio = Mock()
        bexio.get_active_sales_taxes.return_value = []
        service = InvoiceSyncService(sync_config, bexio, mock_wodify_client)

        with pytest.raises(RuntimeError, match="No active sales taxes"):
            service.initialize()

    def test_raises_error_when_iban_not_found(
        self,
        sync_config: SyncConfig,
        mock_wodify_client: Mock,
    ) -> None:
        """Test that RuntimeError is raised when IBAN lookup fails."""
        bexio = Mock()
        bexio.get_active_sales_taxes.return_value = [{"id": 1}]
        bexio.get_bank_account_id_by_iban.return_value = None
        service = InvoiceSyncService(sync_config, bexio, mock_wodify_client)

        with pytest.raises(RuntimeError, match="Bank account not found"):
            service.initialize()

    def test_raises_error_when_account_no_not_found(
        self,
        sync_config: SyncConfig,
        mock_wodify_client: Mock,
    ) -> None:
        """Test that RuntimeError is raised when account number lookup fails."""
        bexio = Mock()
        bexio.get_active_sales_taxes.return_value = [{"id": 1}]
        bexio.get_bank_account_id_by_iban.return_value = 42
        bexio.search_accounts_by_account_no.return_value = []
        service = InvoiceSyncService(sync_config, bexio, mock_wodify_client)

        with pytest.raises(RuntimeError, match="Revenue account not found"):
            service.initialize()


class TestPropertiesBeforeInitialize:
    """Tests for property access before initialization."""

    def test_tax_id_raises_before_initialize(
        self, sync_service_uninitialized: InvoiceSyncService
    ) -> None:
        """Test that accessing tax_id before initialize raises an error."""
        with pytest.raises(RuntimeError, match="initialize"):
            _ = sync_service_uninitialized.tax_id

    def test_bank_account_id_raises_before_initialize(
        self, sync_service_uninitialized: InvoiceSyncService
    ) -> None:
        """Test that accessing bank_account_id before initialize raises an error."""
        with pytest.raises(RuntimeError, match="initialize"):
            _ = sync_service_uninitialized.bank_account_id

    def test_revenue_account_id_raises_before_initialize(
        self, sync_service_uninitialized: InvoiceSyncService
    ) -> None:
        """Test that accessing revenue_account_id before initialize raises an error."""
        with pytest.raises(RuntimeError, match="initialize"):
            _ = sync_service_uninitialized.revenue_account_id

    def test_mapper_raises_before_initialize(
        self, sync_service_uninitialized: InvoiceSyncService
    ) -> None:
        """Test that accessing mapper before initialize raises an error."""
        with pytest.raises(RuntimeError, match="initialize"):
            _ = sync_service_uninitialized.mapper


class TestGetOrCreateContact:
    """Tests for the get_or_create_contact method."""

    def test_calls_bexio_get_or_create(
        self,
        sync_service: InvoiceSyncService,
        wodify_client_model: WodifyClient,
        mock_bexio_client: Mock,
    ) -> None:
        """Test that get_or_create_contact calls bexio client correctly."""
        mock_contact = BexioContact(id=651, name_1="Doe", name_2="John")
        mock_bexio_client.get_or_create_contact_by_email.return_value = (
            mock_contact,
            False,
        )

        contact, created = sync_service.get_or_create_contact(wodify_client_model)

        assert contact.id == 651
        assert created is False
        mock_bexio_client.get_or_create_contact_by_email.assert_called_once_with(
            email="john.doe@example.com",
            first_name="John",
            last_name="Doe",
            phone="+41 79 123 45 67",
            owner_id=1,
            remarks="Wodify Client ID: 12345",
        )

    def test_raises_error_for_client_without_email(
        self,
        sync_service: InvoiceSyncService,
    ) -> None:
        """Test that ValueError is raised for client without email."""
        client = WodifyClient(id=1, email=None)

        with pytest.raises(ValueError, match="no email"):
            sync_service.get_or_create_contact(client)


class TestSyncInvoice:
    """Tests for the sync_invoice method."""

    def test_returns_existing_invoice_if_found(
        self,
        sync_service: InvoiceSyncService,
        wodify_invoice: WodifyInvoice,
        mock_bexio_client: Mock,
    ) -> None:
        """Test that existing invoice is returned with created=False."""
        existing_invoice = BexioInvoice(
            id=100, contact_id=1, user_id=1, api_reference="92421099"
        )
        mock_bexio_client.invoice_exists_for_reference.return_value = True
        mock_bexio_client.get_invoices.return_value = [existing_invoice]

        invoice, created = sync_service.sync_invoice(wodify_invoice)

        assert invoice == existing_invoice
        assert created is False
        mock_bexio_client.invoice_exists_for_reference.assert_called_with("92421099")

    def test_returns_none_if_not_found_and_create_disabled(
        self,
        sync_service: InvoiceSyncService,
        wodify_invoice: WodifyInvoice,
        mock_bexio_client: Mock,
    ) -> None:
        """Test that (None, False) is returned if not found and create disabled."""
        mock_bexio_client.invoice_exists_for_reference.return_value = False

        invoice, created = sync_service.sync_invoice(
            wodify_invoice, create_if_missing=False
        )

        assert invoice is None
        assert created is False

    def test_creates_invoice_if_not_found(
        self,
        sync_service: InvoiceSyncService,
        wodify_invoice: WodifyInvoice,
        wodify_client_model: WodifyClient,
        mock_bexio_client: Mock,
        mock_wodify_client: Mock,
    ) -> None:
        """Test that invoice is created with created=True."""
        mock_bexio_client.invoice_exists_for_reference.return_value = False
        # get_invoice is called to fetch full invoice details
        mock_wodify_client.get_invoice.return_value = wodify_invoice
        mock_wodify_client.get_client.return_value = wodify_client_model
        mock_contact = BexioContact(id=651, name_1="Doe", name_2="John")
        mock_bexio_client.get_or_create_contact_by_email.return_value = (
            mock_contact,
            True,
        )
        created_invoice = BexioInvoice(
            id=100, contact_id=651, user_id=1, api_reference="92421099"
        )
        mock_bexio_client.create_invoice.return_value = created_invoice

        invoice, created = sync_service.sync_invoice(wodify_invoice)

        assert invoice == created_invoice
        assert created is True
        mock_wodify_client.get_invoice.assert_called_with(92421099)
        mock_wodify_client.get_client.assert_called_with(12345)
        mock_bexio_client.create_invoice.assert_called_once()


class TestSyncInvoices:
    """Tests for the sync_invoices method."""

    def test_syncs_multiple_invoices(
        self,
        sync_service: InvoiceSyncService,
        wodify_invoice: WodifyInvoice,
        wodify_client_model: WodifyClient,
        mock_bexio_client: Mock,
        mock_wodify_client: Mock,
    ) -> None:
        """Test that multiple invoices can be synced."""
        mock_bexio_client.invoice_exists_for_reference.return_value = False
        mock_wodify_client.get_invoice.return_value = wodify_invoice
        mock_wodify_client.get_client.return_value = wodify_client_model
        mock_contact = BexioContact(id=651, name_1="Doe")
        mock_bexio_client.get_or_create_contact_by_email.return_value = (
            mock_contact,
            False,
        )
        created_invoice = BexioInvoice(id=100, contact_id=651, user_id=1)
        mock_bexio_client.create_invoice.return_value = created_invoice

        results = sync_service.sync_invoices([wodify_invoice])

        assert len(results) == 1
        wodify_inv, bexio_inv, created, error = results[0]
        assert wodify_inv == wodify_invoice
        assert bexio_inv == created_invoice
        assert created is True
        assert error is None

    def test_captures_errors_per_invoice(
        self,
        sync_service: InvoiceSyncService,
        wodify_invoice: WodifyInvoice,
        mock_bexio_client: Mock,
        mock_wodify_client: Mock,
    ) -> None:
        """Test that errors are captured per invoice."""
        mock_bexio_client.invoice_exists_for_reference.return_value = False
        mock_wodify_client.get_client.side_effect = Exception("API error")

        results = sync_service.sync_invoices([wodify_invoice])

        assert len(results) == 1
        wodify_inv, bexio_inv, created, error = results[0]
        assert wodify_inv == wodify_invoice
        assert bexio_inv is None
        assert created is False
        assert error is not None
        assert "API error" in error
