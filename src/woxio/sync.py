"""Invoice synchronization service between Wodify and Bexio."""

from woxio.bexio.client import BexioClient
from woxio.bexio.models import BexioContact, BexioInvoice
from woxio.config import SyncConfig
from woxio.mapping import WodifyToBexioMapper
from woxio.wodify.client import WodifyClient
from woxio.wodify.models import WodifyClient as WodifyClientModel
from woxio.wodify.models import WodifyInvoice


class InvoiceSyncService:
    """Service for synchronizing invoices from Wodify to Bexio.

    This service handles the full synchronization workflow:
    1. Fetches dynamic Bexio settings (tax_id, bank_account_id)
    2. Gets or creates Bexio contacts for Wodify clients
    3. Maps and creates Bexio invoices from Wodify invoices

    Usage:
        with BexioClient(bexio_config) as bexio, WodifyClient(wodify_config) as wodify:
            sync = InvoiceSyncService(sync_config, bexio, wodify)
            sync.initialize()  # Fetch Bexio settings

            # Sync a single invoice
            wodify_invoice = wodify.get_invoice(invoice_id)
            bexio_invoice = sync.sync_invoice(wodify_invoice)
    """

    def __init__(
        self,
        config: SyncConfig,
        bexio_client: BexioClient,
        wodify_client: WodifyClient,
    ) -> None:
        """Initialize the sync service.

        Args:
            config: Sync configuration containing Bexio IDs and IBAN.
            bexio_client: Client for Bexio API operations.
            wodify_client: Client for Wodify API operations.
        """
        self.config = config
        self.bexio = bexio_client
        self.wodify = wodify_client

        # These are fetched during initialize()
        self._bank_account_id: int | None = None
        self._revenue_account_id: int | None = None
        self._mapper: WodifyToBexioMapper | None = None

    def initialize(self) -> None:
        """Initialize the sync service by fetching Bexio settings.

        This method must be called before syncing invoices. It fetches:
        - bank_account_id: By looking up the configured IBAN
        - revenue_account_id: By looking up the configured account number

        Note: tax_id is configured via BEXIO_TAX_ID environment variable.

        Raises:
            RuntimeError: If any lookup fails.
        """
        # Look up bank account by IBAN
        bank_account_id = self.bexio.get_bank_account_id_by_iban(self.config.bank_iban)
        if bank_account_id is None:
            raise RuntimeError(
                f"Bank account not found for IBAN: {self.config.bank_iban}"
            )
        self._bank_account_id = bank_account_id

        # Look up revenue account by account number
        accounts = self.bexio.search_accounts_by_account_no(
            str(self.config.revenue_account_no)
        )
        if not accounts:
            raise RuntimeError(
                f"Revenue account not found for account_no: "
                f"{self.config.revenue_account_no}"
            )
        self._revenue_account_id = int(accounts[0]["id"])

        # Create the mapper with resolved IDs
        self._mapper = WodifyToBexioMapper(
            owner_id=self.config.owner_id,
            revenue_account_id=self._revenue_account_id,
            default_country_id=self.config.default_country_id,
        )

    @property
    def tax_id(self) -> int:
        """Get the configured tax ID."""
        return self.config.tax_id

    @property
    def bank_account_id(self) -> int:
        """Get the fetched bank account ID."""
        if self._bank_account_id is None:
            raise RuntimeError("bank_account_id not available. Call initialize() first.")
        return self._bank_account_id

    @property
    def revenue_account_id(self) -> int:
        """Get the fetched revenue account ID."""
        if self._revenue_account_id is None:
            raise RuntimeError(
                "revenue_account_id not available. Call initialize() first."
            )
        return self._revenue_account_id

    @property
    def mapper(self) -> WodifyToBexioMapper:
        """Get the mapper instance."""
        if self._mapper is None:
            raise RuntimeError("mapper not available. Call initialize() first.")
        return self._mapper

    def get_or_create_contact(self, client: WodifyClientModel) -> tuple[BexioContact, bool]:
        """Get or create a Bexio contact for a Wodify client.

        Searches for an existing contact by email. If not found, creates a new
        contact.

        Args:
            client: The Wodify client.

        Returns:
            Tuple of (contact, created) where created is True if a new contact
            was created, False if an existing contact was found.

        Raises:
            ValueError: If the client has no email address.
        """
        if not client.email:
            raise ValueError(f"Wodify client {client.id} has no email address")

        # Map gender to salutation_id
        salutation_id = self._map_gender_to_salutation(client.gender)

        return self.bexio.get_or_create_contact_by_email(
            email=client.email,
            first_name=client.first_name,
            last_name=client.last_name,
            phone=client.phone,
            street_address=client.street_address_1,
            address_addition=client.street_address_2,
            postcode=client.zipcode,
            city=client.city,
            country_id=self.config.default_country_id,
            salutation_id=salutation_id,
            owner_id=self.config.owner_id,
            remarks=f"Wodify Client ID: {client.id}",
        )

    @staticmethod
    def _map_gender_to_salutation(gender: str | None) -> int | None:
        """Map Wodify gender to Bexio salutation_id.

        Args:
            gender: Wodify gender string ("Male", "Female", etc.).

        Returns:
            Bexio salutation_id (1 = Mr., 2 = Ms.) or None if unknown.
        """
        if not gender:
            return None
        gender_lower = gender.lower()
        if gender_lower == "male":
            return 1  # Mr. (Herr)
        if gender_lower == "female":
            return 2  # Ms. (Frau)
        return None

    def sync_invoice(
        self,
        wodify_invoice: WodifyInvoice,
        *,
        create_if_missing: bool = True,
    ) -> tuple[BexioInvoice | None, bool]:
        """Sync a single Wodify invoice to Bexio.

        This method:
        1. Checks if the invoice already exists in Bexio (by api_reference)
        2. Fetches the Wodify client for the invoice
        3. Gets or creates the corresponding Bexio contact
        4. Maps the Wodify invoice to a Bexio invoice
        5. Creates the invoice in Bexio

        Args:
            wodify_invoice: The Wodify invoice to sync.
            create_if_missing: If True, create the invoice if it doesn't exist.
                              If False, only return existing invoice.

        Returns:
            Tuple of (bexio_invoice, created) where created is True if a new
            invoice was created, False if an existing invoice was found.
            Returns (None, False) if the invoice doesn't exist and
            create_if_missing is False.

        Raises:
            RuntimeError: If initialize() hasn't been called.
        """
        # Check if invoice already exists
        if self.bexio.invoice_exists_for_reference(str(wodify_invoice.id)):
            existing = self.bexio.get_invoices(api_reference=str(wodify_invoice.id))
            return (existing[0] if existing else None, False)

        if not create_if_missing:
            return (None, False)

        # Fetch the full invoice details (includes product info)
        full_invoice = self.wodify.get_invoice(wodify_invoice.id)

        # Fetch the Wodify client
        wodify_client = self.wodify.get_client(full_invoice.client_id)

        # Get or create Bexio contact
        contact, _created = self.get_or_create_contact(wodify_client)
        if contact.id is None:
            raise RuntimeError("Contact was created but has no ID")

        # Map and create the invoice
        bexio_invoice = self.mapper.map_invoice_with_client(
            full_invoice,
            wodify_client,
            contact.id,
            tax_id=self.tax_id,
            bank_account_id=self.bank_account_id,
        )

        created_invoice = self.bexio.create_invoice(bexio_invoice)
        return (created_invoice, True)

    def sync_invoices(
        self,
        wodify_invoices: list[WodifyInvoice],
    ) -> list[tuple[WodifyInvoice, BexioInvoice | None, bool, str | None]]:
        """Sync multiple Wodify invoices to Bexio.

        Args:
            wodify_invoices: List of Wodify invoices to sync.

        Returns:
            List of tuples (wodify_invoice, bexio_invoice, created, error_message).
            - created is True if a new invoice was created, False if existing.
            - If sync failed, bexio_invoice is None and error_message contains the error.
        """
        results: list[tuple[WodifyInvoice, BexioInvoice | None, bool, str | None]] = []

        for wodify_invoice in wodify_invoices:
            try:
                bexio_invoice, created = self.sync_invoice(wodify_invoice)
                results.append((wodify_invoice, bexio_invoice, created, None))
            except Exception as e:
                results.append((wodify_invoice, None, False, str(e)))

        return results
