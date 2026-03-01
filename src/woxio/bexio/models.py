"""Bexio data models."""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class BexioInvoiceItem(BaseModel):
    """A line item for a Bexio invoice."""

    model_config = ConfigDict(populate_by_name=True)

    type: str = "KbPositionCustom"  # KbPositionCustom, KbPositionArticle, KbPositionText, etc.
    amount: Decimal
    unit_price: Decimal
    text: str
    account_id: int
    tax_id: int
    unit_id: int | None = None


class BexioInvoice(BaseModel):
    """A Bexio invoice."""

    model_config = ConfigDict(populate_by_name=True)

    id: int | None = None
    document_nr: str | None = None  # Bexio-generated invoice number (e.g., "RE-05081")
    kb_item_status_id: int | None = None
    contact_id: int
    user_id: int
    bank_account_id: int | None = None
    title: str | None = None
    positions: list[BexioInvoiceItem] = Field(default_factory=list)
    api_reference: str | None = None  # For storing Wodify invoice ID
    is_valid_from: date | None = None
    is_valid_to: date | None = None
    total: Decimal | None = None
    mwst_type: int = 0  # 0 = included, 1 = excluded, 2 = exempt
    mwst_is_net: bool = True


class BexioContact(BaseModel):
    """A Bexio contact (customer).

    For persons (contact_type_id=2):
      - name_1 = Last name
      - name_2 = First name

    For companies (contact_type_id=1):
      - name_1 = Company name
      - name_2 = Company addition (optional)

    Salutation IDs:
      - 1 = Mr. (Herr)
      - 2 = Ms. (Frau)
    """

    model_config = ConfigDict(populate_by_name=True)

    id: int | None = None  # None when creating a new contact
    nr: str | None = None  # Auto-assigned contact number
    contact_type_id: int = 2  # 1 = Company, 2 = Person
    name_1: str = ""  # Last name (person) or Company name
    name_2: str | None = None  # First name (person) or Company addition
    salutation_id: int | None = None  # 1 = Mr., 2 = Ms.
    mail: str | None = None
    mail_second: str | None = None
    phone_fixed: str | None = None
    phone_mobile: str | None = None
    street_name: str | None = None
    house_number: str | None = None
    address_addition: str | None = None  # Additional address info (e.g., Building C)
    postcode: str | None = None
    city: str | None = None
    country_id: int | None = None  # References Bexio country object
    language_id: int | None = None  # References Bexio language object
    user_id: int | None = None  # Required for creation - references Bexio user
    owner_id: int | None = None  # Required for creation
    remarks: str | None = None  # For storing Wodify client ID
    updated_at: str | None = None

    @property
    def name(self) -> str:
        """Get the full name."""
        if self.name_2:
            return f"{self.name_1} {self.name_2}".strip()
        return self.name_1
