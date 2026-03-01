"""Unit tests for main module workflows."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from unittest.mock import Mock

import httpx

from woxio.bexio.models import BexioInvoice
from woxio.main import issue_synced_invoices


class _BexioContext:
    """Simple context manager wrapper for a mocked client."""

    def __init__(self, client: Any) -> None:
        self.client = client

    def __enter__(self) -> Any:
        return self.client

    def __exit__(self, *args: object) -> None:
        return None


def _http_status_error(status_code: int, url: str) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", url)
    response = httpx.Response(status_code=status_code, request=request)
    return httpx.HTTPStatusError(
        f"{status_code} error",
        request=request,
        response=response,
    )


def test_issue_synced_invoices_issues_only_drafts(monkeypatch: Any) -> None:
    """Send only draft invoices when valid_from date is reached."""
    today = datetime.now(UTC).date()
    mock_client = Mock()
    mock_client.get_invoices_with_api_reference.return_value = [
        BexioInvoice(
            id=1,
            contact_id=1,
            user_id=1,
            kb_item_status_id=7,
            document_nr="RE-1",
            api_reference="wodify-1",
            is_valid_from=today - timedelta(days=1),
            is_valid_to=today + timedelta(days=30),
            total=Decimal("123.40"),
        ),
        BexioInvoice(
            id=2,
            contact_id=1,
            user_id=1,
            kb_item_status_id=5,
            document_nr="RE-2",
            api_reference="wodify-2",
            is_valid_from=today - timedelta(days=1),
            is_valid_to=today + timedelta(days=30),
            total=Decimal("150.00"),
        ),
        BexioInvoice(
            id=None,
            contact_id=1,
            user_id=1,
            kb_item_status_id=7,
            document_nr="RE-3",
            api_reference="wodify-3",
            is_valid_from=today - timedelta(days=1),
            is_valid_to=today + timedelta(days=30),
            total=Decimal("80.00"),
        ),
        BexioInvoice(
            id=4,
            contact_id=1,
            user_id=1,
            kb_item_status_id=7,
            document_nr="RE-4",
            api_reference="wodify-4",
            is_valid_from=today + timedelta(days=1),
            is_valid_to=today + timedelta(days=30),
            total=Decimal("95.00"),
        ),
        BexioInvoice(
            id=5,
            contact_id=1,
            user_id=1,
            kb_item_status_id=7,
            document_nr="RE-5",
            api_reference="",
            is_valid_from=today - timedelta(days=1),
            is_valid_to=today + timedelta(days=30),
            total=Decimal("55.00"),
        ),
    ]
    contact = Mock()
    contact.mail = "customer@example.com"
    contact.name = "Max Muster"
    mock_client.get_contact.return_value = contact
    mock_client.send_invoice.return_value = {"success": True}

    monkeypatch.setattr(
        "woxio.main.BexioClient",
        lambda _config: _BexioContext(mock_client),
    )

    config = Mock()
    config.bexio = Mock()
    result = issue_synced_invoices(config)

    assert result["sent"] == 1
    assert result["skipped"] == 4
    assert result["errors"] == 0
    assert result["error_details"] == []
    mock_client.send_invoice.assert_called_once()

    call_args = mock_client.send_invoice.call_args
    assert call_args is not None
    assert call_args.args == (1,)
    assert call_args.kwargs["recipient_email"] == "customer@example.com"
    assert call_args.kwargs["subject"] == "Rechnung - Port 3"
    assert call_args.kwargs["mark_as_open"] is True
    assert call_args.kwargs["attach_pdf"] is True
    assert "Guten Tag Max Muster" in call_args.kwargs["message"]
    assert f"Datum: {(today - timedelta(days=1)).isoformat()}" in call_args.kwargs["message"]
    assert "Betrag: 123.40" in call_args.kwargs["message"]
    assert f"Zahlbar bis: {(today + timedelta(days=30)).isoformat()}" in call_args.kwargs["message"]
    assert "[Network Link]" in call_args.kwargs["message"]


def test_issue_synced_invoices_classifies_http_errors(monkeypatch: Any) -> None:
    """Classify 400/422 as skipped and 5xx as errors for sending."""
    today = datetime.now(UTC).date()
    mock_client = Mock()
    mock_client.get_invoices_with_api_reference.return_value = [
        BexioInvoice(
            id=10,
            contact_id=1,
            user_id=1,
            kb_item_status_id=7,
            document_nr="RE-10",
            api_reference="wodify-10",
            is_valid_from=today,
            is_valid_to=today + timedelta(days=10),
            total=Decimal("10.00"),
        ),
        BexioInvoice(
            id=11,
            contact_id=1,
            user_id=1,
            kb_item_status_id=7,
            document_nr="RE-11",
            api_reference="wodify-11",
            is_valid_from=today,
            is_valid_to=today + timedelta(days=10),
            total=Decimal("11.00"),
        ),
    ]
    contact = Mock()
    contact.mail = "customer@example.com"
    contact.name = "Max Muster"
    mock_client.get_contact.return_value = contact
    mock_client.send_invoice.side_effect = [
        _http_status_error(422, "https://api.bexio.com/2.0/kb_invoice/10/send"),
        _http_status_error(500, "https://api.bexio.com/2.0/kb_invoice/11/send"),
    ]

    monkeypatch.setattr(
        "woxio.main.BexioClient",
        lambda _config: _BexioContext(mock_client),
    )

    config = Mock()
    config.bexio = Mock()
    result = issue_synced_invoices(config)

    assert result["sent"] == 0
    assert result["skipped"] == 1
    assert result["errors"] == 1
    assert len(result["error_details"]) == 1
