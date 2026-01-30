"""Wodify data models."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class WodifyPagination(BaseModel):
    """Pagination info from Wodify API response."""

    page: int
    page_size: int
    has_more: bool


class WodifyCreated(BaseModel):
    """Created metadata from Wodify."""

    created_by_id: int
    created_by: str
    created_on_datetime: datetime


class WodifyInvoiceDetail(BaseModel):
    """A line item on a Wodify invoice."""

    model_config = ConfigDict(extra="ignore")

    product_id: int
    product: str = ""
    quantity: int | Decimal = 1
    sales_price: Decimal
    final_charge: Decimal


class WodifyInvoice(BaseModel):
    """A Wodify invoice."""

    model_config = ConfigDict(extra="ignore")

    id: int
    invoice_number: str
    client_id: int
    invoice_header_status_id: int
    invoice_header_status: str = ""
    payment_due: date
    paid_on_date: date | None = None
    final_charge: Decimal
    notes: str = ""
    invoice_footer: str = ""
    created: WodifyCreated
    # invoice_details is only present when fetching a single invoice
    invoice_details: list[WodifyInvoiceDetail] = []

    @property
    def is_paid(self) -> bool:
        """Check if invoice is paid."""
        return self.invoice_header_status.lower() == "paid"

    @property
    def is_unpaid(self) -> bool:
        """Check if invoice is unpaid (the only status we should sync)."""
        return self.invoice_header_status.lower() == "unpaid"

    @property
    def product_name(self) -> str | None:
        """Get the product name from the first invoice detail."""
        if self.invoice_details:
            return self.invoice_details[0].product
        return None


class WodifyInvoicesResponse(BaseModel):
    """Response from the Wodify invoices endpoint."""

    invoices: list[WodifyInvoice]
    pagination: WodifyPagination
    wodify_validation_result: str = ""


class WodifyClient(BaseModel):
    """A Wodify client (customer/member).

    Note: This is named WodifyClient to match Wodify's terminology,
    but represents a customer/member, not an API client.
    """

    model_config = ConfigDict(extra="ignore")

    id: int
    first_name: str = ""
    last_name: str = ""
    email: str | None = None
    phone: str | None = None
    address_1: str | None = None
    address_2: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    country: str | None = None

    @property
    def full_name(self) -> str:
        """Get the full name."""
        return f"{self.first_name} {self.last_name}".strip()
