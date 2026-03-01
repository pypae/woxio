"""Unit tests for main module workflows."""

from datetime import UTC, datetime, timedelta
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
    """Issue only draft invoices when valid_from date is reached."""
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
        ),
        BexioInvoice(
            id=2,
            contact_id=1,
            user_id=1,
            kb_item_status_id=5,
            document_nr="RE-2",
            api_reference="wodify-2",
            is_valid_from=today - timedelta(days=1),
        ),
        BexioInvoice(
            id=None,
            contact_id=1,
            user_id=1,
            kb_item_status_id=7,
            document_nr="RE-3",
            api_reference="wodify-3",
            is_valid_from=today - timedelta(days=1),
        ),
        BexioInvoice(
            id=4,
            contact_id=1,
            user_id=1,
            kb_item_status_id=7,
            document_nr="RE-4",
            api_reference="wodify-4",
            is_valid_from=today + timedelta(days=1),
        ),
        BexioInvoice(
            id=5,
            contact_id=1,
            user_id=1,
            kb_item_status_id=7,
            document_nr="RE-5",
            api_reference="",
            is_valid_from=today - timedelta(days=1),
        ),
    ]
    mock_client.issue_invoice.return_value = {"success": True}

    monkeypatch.setattr(
        "woxio.main.BexioClient",
        lambda _config: _BexioContext(mock_client),
    )

    config = Mock()
    config.bexio = Mock()
    result = issue_synced_invoices(config)

    assert result["issued"] == 1
    assert result["skipped"] == 4
    assert result["errors"] == 0
    assert result["error_details"] == []
    mock_client.issue_invoice.assert_called_once_with(1)


def test_issue_synced_invoices_classifies_http_errors(monkeypatch: Any) -> None:
    """Classify 400/422 as skipped and 5xx as errors."""
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
        ),
        BexioInvoice(
            id=11,
            contact_id=1,
            user_id=1,
            kb_item_status_id=7,
            document_nr="RE-11",
            api_reference="wodify-11",
            is_valid_from=today,
        ),
    ]
    mock_client.issue_invoice.side_effect = [
        _http_status_error(422, "https://api.bexio.com/2.0/kb_invoice/10/issue"),
        _http_status_error(500, "https://api.bexio.com/2.0/kb_invoice/11/issue"),
    ]

    monkeypatch.setattr(
        "woxio.main.BexioClient",
        lambda _config: _BexioContext(mock_client),
    )

    config = Mock()
    config.bexio = Mock()
    result = issue_synced_invoices(config)

    assert result["issued"] == 0
    assert result["skipped"] == 1
    assert result["errors"] == 1
    assert len(result["error_details"]) == 1
