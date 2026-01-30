"""Bexio API client."""

from typing import Any

import httpx

from woxio.config import BexioConfig

from .models import BexioContact, BexioFictionalUser, BexioInvoice


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
            json=invoice.model_dump(mode="json", exclude_none=True, exclude={"id"}),
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

    def search_invoices(
        self,
        *,
        field: str,
        value: str,
        criteria: str = "=",
        limit: int = 500,
        offset: int = 0,
    ) -> list[BexioInvoice]:
        """Search invoices by a specific field.

        Args:
            field: The field to search on (e.g., "document_nr", "api_reference").
            value: The value to search for.
            criteria: The search criteria ("=", "like", "!=", etc.).
            limit: Maximum number of invoices to return.
            offset: Offset for pagination.

        Returns:
            List of matching Bexio invoices.
        """
        params: dict[str, str | int] = {
            "limit": limit,
            "offset": offset,
        }
        search_params = [
            {
                "field": field,
                "value": value,
                "criteria": criteria,
            }
        ]
        response = self.client.post(
            "/2.0/kb_invoice/search",
            json=search_params,
            params=params,
        )
        response.raise_for_status()
        data = response.json()

        return [BexioInvoice.model_validate(inv) for inv in data]

    def get_invoice_by_document_nr(self, document_nr: str) -> BexioInvoice | None:
        """Get an invoice by its document number.

        Args:
            document_nr: The Bexio document number (e.g., "RE-05081").

        Returns:
            The matching invoice, or None if not found.
        """
        invoices = self.search_invoices(field="document_nr", value=document_nr)
        return invoices[0] if invoices else None

    def delete_invoice(self, invoice_id: int) -> bool:
        """Delete an invoice from Bexio.

        Args:
            invoice_id: The Bexio invoice ID to delete.

        Returns:
            True if the invoice was deleted successfully.
        """
        response = self.client.delete(f"/2.0/kb_invoice/{invoice_id}")
        response.raise_for_status()
        result = response.json()
        return bool(result.get("success", False))

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

    def get_contact(self, contact_id: int) -> BexioContact:
        """Get a single contact by ID.

        Args:
            contact_id: The Bexio contact ID.

        Returns:
            The Bexio contact.
        """
        response = self.client.get(f"/2.0/contact/{contact_id}")
        response.raise_for_status()
        return BexioContact.model_validate(response.json())

    def create_contact(
        self,
        contact: BexioContact,
        *,
        create_fictional_user: bool = True,
    ) -> BexioContact:
        """Create a new contact in Bexio.

        If the contact doesn't have a user_id set and create_fictional_user is True,
        a fictional user will be automatically created for this contact using the
        contact's name and email.

        Args:
            contact: The contact to create. Must have owner_id set.
            create_fictional_user: If True and user_id is None, automatically
                create a fictional user for this contact.

        Returns:
            The created contact with ID populated.

        Raises:
            ValueError: If owner_id is not set, or if user_id is not set and
                create_fictional_user is False.
        """
        if contact.owner_id is None:
            raise ValueError("owner_id is required for contact creation")

        # If no user_id, create a fictional user for this contact
        if contact.user_id is None:
            if not create_fictional_user:
                raise ValueError(
                    "user_id is required for contact creation when "
                    "create_fictional_user is False"
                )
            fictional_user = self._create_fictional_user_for_contact(contact)
            # Create a copy of the contact with the fictional user's ID
            contact = contact.model_copy(update={"user_id": fictional_user.id})

        payload = contact.model_dump(
            mode="json",
            exclude_none=True,
            exclude={"id", "updated_at"},
        )
        response = self.client.post("/2.0/contact", json=payload)
        response.raise_for_status()
        return BexioContact.model_validate(response.json())

    def _create_fictional_user_for_contact(
        self, contact: BexioContact
    ) -> BexioFictionalUser:
        """Create a fictional user based on contact information.

        Args:
            contact: The contact to create a fictional user for.

        Returns:
            The created fictional user.
        """
        return self.create_fictional_user(
            first_name=contact.name_2 or "Unknown",
            last_name=contact.name_1 or "Customer",
            email=contact.mail or f"fictional-{contact.name_1}@placeholder.local",
        )

    def get_or_create_contact_by_email(
        self,
        email: str,
        *,
        first_name: str = "",
        last_name: str = "",
        phone: str | None = None,
        owner_id: int,
        remarks: str | None = None,
    ) -> tuple[BexioContact, bool]:
        """Get an existing contact by email, or create a new one if not found.

        When creating a new contact, this method also creates a fictional user
        for the contact and uses its ID as the user_id. This is required because
        the user_id on a contact represents the "responsible user" for that
        contact, which should be a fictional user representing the customer.

        Args:
            email: The email address to search/create with.
            first_name: First name for new contact.
            last_name: Last name for new contact.
            phone: Phone number for new contact.
            owner_id: Bexio owner ID (required for creation).
            remarks: Optional remarks (e.g., Wodify client ID).

        Returns:
            Tuple of (contact, created) where created is True if a new contact
            was created, False if an existing contact was found.
        """
        # Search for existing contact by email
        existing = self.search_contacts_by_email(email)
        if existing:
            return existing[0], False

        # Create a fictional user for this contact
        fictional_user = self.create_fictional_user(
            first_name=first_name or "Unknown",
            last_name=last_name or "Customer",
            email=email,
        )

        # Create new contact using the fictional user's ID
        new_contact = BexioContact(
            contact_type_id=2,  # Person
            name_1=last_name or "Unknown",
            name_2=first_name or None,
            mail=email,
            phone_mobile=phone,
            user_id=fictional_user.id,
            owner_id=owner_id,
            remarks=remarks,
        )
        created = self.create_contact(new_contact)
        return created, True

    # Fictional User endpoints

    def get_fictional_users(self) -> list[BexioFictionalUser]:
        """Get all fictional users from Bexio.

        Returns:
            List of fictional users.
        """
        response = self.client.get("/3.0/fictional_users")
        response.raise_for_status()
        return [BexioFictionalUser.model_validate(u) for u in response.json()]

    def get_fictional_user(self, fictional_user_id: int) -> BexioFictionalUser:
        """Get a single fictional user by ID.

        Args:
            fictional_user_id: The Bexio fictional user ID.

        Returns:
            The fictional user.
        """
        response = self.client.get(f"/3.0/fictional_users/{fictional_user_id}")
        response.raise_for_status()
        return BexioFictionalUser.model_validate(response.json())

    def create_fictional_user(
        self,
        *,
        first_name: str,
        last_name: str,
        email: str,
        salutation_type: str = "male",
    ) -> BexioFictionalUser:
        """Create a new fictional user in Bexio.

        Fictional users are pseudo-users that can be assigned as the responsible
        user for contacts. When creating contacts for customers, a corresponding
        fictional user should be created and its ID used as the contact's user_id.

        Args:
            first_name: The fictional user's first name.
            last_name: The fictional user's last name.
            email: The fictional user's email address.
            salutation_type: Salutation type ("male" or "female").

        Returns:
            The created fictional user with ID populated.
        """
        payload = {
            "salutation_type": salutation_type,
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
        }
        response = self.client.post("/3.0/fictional_users", json=payload)
        response.raise_for_status()
        return BexioFictionalUser.model_validate(response.json())

    # Tax endpoints

    def get_active_sales_taxes(self) -> list[dict[str, Any]]:
        """Get active sales taxes valid for invoices.

        Returns:
            List of active sales tax objects.
        """
        response = self.client.get(
            "/3.0/taxes",
            params={"types": "sales_tax", "scope": "active"},
        )
        response.raise_for_status()
        return list(response.json())

    # Accounting endpoints

    def get_accounts(self) -> list[dict[str, Any]]:
        """Get accounting accounts from Bexio.

        Returns:
            List of accounting account objects.
        """
        response = self.client.get("/2.0/accounts")
        response.raise_for_status()
        return list(response.json())

    def search_accounts_by_account_no(self, account_no: str) -> list[dict[str, Any]]:
        """Search for accounting accounts by account number.

        Args:
            account_no: The account number to search for.

        Returns:
            List of matching accounting account objects.
        """
        search_params = [
            {
                "field": "account_no",
                "value": account_no,
                "criteria": "=",
            }
        ]
        response = self.client.post("/2.0/accounts/search", json=search_params)
        response.raise_for_status()
        return list(response.json())

    # Bank account endpoints

    def get_bank_accounts(self) -> list[dict[str, Any]]:
        """Get bank accounts from Bexio.

        Returns:
            List of bank account objects.
        """
        response = self.client.get("/3.0/banking/accounts")
        response.raise_for_status()
        return list(response.json())

    def get_bank_account_id_by_iban(self, iban: str) -> int | None:
        """Find a bank account ID by its IBAN.

        Args:
            iban: The IBAN to search for (spaces are ignored).

        Returns:
            The bank account ID, or None if not found.
        """
        # Normalize IBAN by removing spaces for comparison
        normalized_iban = iban.replace(" ", "")
        accounts = self.get_bank_accounts()
        for account in accounts:
            account_iban = account.get("iban_nr", "").replace(" ", "")
            if account_iban == normalized_iban:
                return int(account["id"])
        return None
