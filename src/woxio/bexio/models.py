"""Bexio data models."""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class BexioInvoiceItem(BaseModel):
    """A line item for a Bexio invoice."""

    model_config = ConfigDict(populate_by_name=True)

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
    contact_id: int
    title: str
    positions: list[BexioInvoiceItem] = Field(default_factory=list)
    api_reference: str | None = None  # For storing Wodify invoice ID
    is_valid_from: date | None = None
    is_valid_to: date | None = None
    mwst_type: int = 0  # 0 = included, 1 = excluded, 2 = exempt
    mwst_is_net: bool = True
    kb_item_status_id: int = 7  # 7 = Draft


class BexioContact(BaseModel):
    """A Bexio contact (customer)."""

    model_config = ConfigDict(populate_by_name=True)

    id: int
    name_1: str = ""
    name_2: str | None = None
    mail: str | None = None
    contact_type_id: int = 1  # 1 = Company, 2 = Person

    @property
    def name(self) -> str:
        """Get the full name."""
        if self.name_2:
            return f"{self.name_1} {self.name_2}".strip()
        return self.name_1
