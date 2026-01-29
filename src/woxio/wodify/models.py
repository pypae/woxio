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

    @property
    def is_paid(self) -> bool:
        """Check if invoice is paid."""
        return self.invoice_header_status.lower() == "paid"


class WodifyInvoicesResponse(BaseModel):
    """Response from the Wodify invoices endpoint."""

    invoices: list[WodifyInvoice]
    pagination: WodifyPagination
    wodify_validation_result: str = ""
