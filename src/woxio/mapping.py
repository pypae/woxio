"""Mapping between Wodify and Bexio data models."""

from decimal import Decimal
from datetime import timedelta

from woxio.bexio.models import BexioContact, BexioInvoice, BexioInvoiceItem
from woxio.wodify.models import WodifyClient, WodifyInvoice


class WodifyToBexioMapper:
    """Maps Wodify data models to Bexio data models.

    This is a pure data transformation class with no API dependencies.
    All required IDs (owner_id, tax_id, bank_account_id, etc.) are passed
    directly to the constructor or methods.

    Usage:
        mapper = WodifyToBexioMapper(
            owner_id=1,
            revenue_account_id=3200,
            default_country_id=1,
        )
        contact = mapper.map_client_to_contact(wodify_client)
        invoice = mapper.map_invoice(wodify_invoice, contact_id, tax_id, bank_account_id)
    """

    def __init__(
        self,
        *,
        owner_id: int,
        revenue_account_id: int,
        default_country_id: int | None = None,
    ) -> None:
        """Initialize the mapper with required Bexio IDs.

        Args:
            owner_id: Bexio owner ID for created records.
            revenue_account_id: Bexio account ID for revenue line items.
            default_country_id: Default country ID for new contacts (optional).
        """
        self.owner_id = owner_id
        self.revenue_account_id = revenue_account_id
        self.default_country_id = default_country_id

    def map_client_to_contact(self, client: WodifyClient) -> BexioContact:
        """Map a Wodify client to a Bexio contact.

        Note: The user_id is intentionally not set here. When the contact is
        created via BexioClient.create_contact(), owner_id will be used as
        automatically created for this contact.

        Args:
            client: The Wodify client (customer/member).

        Returns:
            A BexioContact ready for creation (without ID or user_id).
        """
        return BexioContact(
            contact_type_id=2,  # Person
            name_1=client.last_name or "Unknown",
            name_2=client.first_name or None,
            salutation_id=self._map_gender_to_salutation(client.gender),
            mail=client.email,
            phone_mobile=client.phone,
            street_name=client.street_address_1,
            address_addition=client.street_address_2,
            postcode=client.zipcode,
            city=client.city,
            country_id=self.default_country_id,
            # user_id is set by BexioClient using owner_id
            owner_id=self.owner_id,
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

    def map_invoice(
        self,
        invoice: WodifyInvoice,
        contact_id: int,
        *,
        tax_id: int,
        bank_account_id: int,
        line_item_text: str | None = None,
    ) -> BexioInvoice:
        """Map a Wodify invoice to a Bexio invoice.

        Args:
            invoice: The Wodify invoice.
            contact_id: The Bexio contact ID for this invoice.
            tax_id: Bexio tax ID for line items.
            bank_account_id: Bexio bank account ID for the invoice.
            line_item_text: Optional custom text for the line item.
                           Defaults to product name or invoice number.

        Returns:
            A BexioInvoice ready for creation (without ID).
        """
        # Use product name from invoice details if available
        product_name = invoice.product_name

        # Build invoice title - prefer product name
        title = product_name or f"Wodify Invoice {invoice.invoice_number}"

        # Build line item text - use notes only (or fallback to invoice number)
        item_text = line_item_text or invoice.notes or f"Invoice {invoice.invoice_number}"

        # Create line item for the total amount
        position = BexioInvoiceItem(
            type="KbPositionCustom",
            amount=Decimal("1"),
            unit_price=invoice.final_charge,
            text=item_text,
            account_id=self.revenue_account_id,
            tax_id=tax_id,
        )

        return BexioInvoice(
            contact_id=contact_id,
            user_id=self.owner_id,  # Invoice creator is the owner
            bank_account_id=bank_account_id,
            title=title,
            api_reference=str(invoice.id),
            is_valid_from=invoice.payment_due,
            is_valid_to=invoice.payment_due + timedelta(days=30),
            positions=[position],
            mwst_type=0,  # VAT type: 0 = inclusive
            mwst_is_net=False,  # Prices are gross (VAT included)
        )

    def map_invoice_with_client(
        self,
        invoice: WodifyInvoice,
        client: WodifyClient,  # noqa: ARG002 - kept for API compatibility
        contact_id: int,
        *,
        tax_id: int,
        bank_account_id: int,
    ) -> BexioInvoice:
        """Map a Wodify invoice to a Bexio invoice.

        Note: The client parameter is kept for API compatibility but the product
        name from invoice details is now used for the title and line item text.

        Args:
            invoice: The Wodify invoice (should include invoice_details).
            client: The Wodify client associated with the invoice (unused).
            contact_id: The Bexio contact ID for this invoice.
            tax_id: Bexio tax ID for line items.
            bank_account_id: Bexio bank account ID for the invoice.

        Returns:
            A BexioInvoice ready for creation (without ID).
        """
        return self.map_invoice(
            invoice,
            contact_id,
            tax_id=tax_id,
            bank_account_id=bank_account_id,
        )
