"""Cloud Function entry point for Woxio invoice sync."""

import logging
import sys
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from woxio.bexio import BexioClient
from woxio.config import Config
from woxio.sync import InvoiceSyncService
from woxio.wodify import WodifyClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def sync_invoices(config: Config) -> dict[str, Any]:
    """Sync invoices from Wodify to Bexio.

    Args:
        config: Application configuration.

    Returns:
        Summary of the sync operation.
    """
    created_count = 0
    skipped_count = 0
    error_count = 0
    errors: list[str] = []

    with WodifyClient(config.wodify) as wodify, BexioClient(config.bexio) as bexio:
        # Initialize the sync service
        sync_service = InvoiceSyncService(config.sync, bexio, wodify)
        sync_service.initialize()
        logger.info(
            f"Sync service initialized (tax_id={sync_service.tax_id}, "
            f"bank_account_id={sync_service.bank_account_id}, "
            f"revenue_account_id={sync_service.revenue_account_id})"
        )

        # Calculate cutoff: now - poll_interval - buffer
        cutoff = datetime.now(UTC) - timedelta(
            minutes=config.poll_interval_minutes,
            hours=config.poll_buffer_hours,
        )
        logger.info(
            f"Fetching invoices from Wodify created after {cutoff.isoformat()} "
            f"(poll_interval={config.poll_interval_minutes}min, "
            f"buffer={config.poll_buffer_hours}h)"
        )

        # Fetch recent invoices from Wodify
        all_invoices = list(wodify.get_recent_invoices(cutoff))
        # Only sync unpaid invoices (skip paid, cancelled, etc.)
        wodify_invoices = [inv for inv in all_invoices if inv.is_unpaid]
        logger.info(
            f"Found {len(all_invoices)} invoices, {len(wodify_invoices)} unpaid to sync"
        )

        # Sync each unpaid invoice
        for wodify_invoice in wodify_invoices:
            try:
                bexio_invoice, created = sync_service.sync_invoice(wodify_invoice)

                if created and bexio_invoice:
                    logger.info(
                        f"Created Bexio invoice {bexio_invoice.id} for "
                        f"Wodify invoice {wodify_invoice.invoice_number}"
                    )
                    created_count += 1
                elif bexio_invoice:
                    logger.debug(
                        f"Invoice {wodify_invoice.invoice_number} already synced "
                        f"(Bexio ID: {bexio_invoice.id})"
                    )
                    skipped_count += 1

            except Exception as e:
                logger.error(
                    f"Error syncing invoice {wodify_invoice.invoice_number}: {e}"
                )
                errors.append(f"{wodify_invoice.invoice_number}: {str(e)}")
                error_count += 1

    return {
        "status": "completed",
        "created": created_count,
        "skipped": skipped_count,
        "errors": error_count,
        "error_details": errors,
    }


def issue_synced_invoices(config: Config) -> dict[str, Any]:
    """Issue Woxio-created draft invoices in Bexio.

    Only invoices with a non-empty api_reference are considered, which identifies
    invoices created by this integration.

    Args:
        config: Application configuration.

    Returns:
        Summary of issue operation.
    """
    issued_count = 0
    skipped_count = 0
    error_count = 0
    errors: list[str] = []
    issue_from_cutoff_date = datetime.now(UTC).date()

    with BexioClient(config.bexio) as bexio:
        invoices = bexio.get_invoices_with_api_reference()
        logger.info(
            f"Found {len(invoices)} Woxio-linked invoices in Bexio "
            f"(issuing when valid_from <= {issue_from_cutoff_date.isoformat()})"
        )

        for invoice in invoices:
            invoice_ref = invoice.document_nr or invoice.api_reference or str(invoice.id)
            api_reference = (invoice.api_reference or "").strip()
            if not api_reference:
                logger.info(f"Skipping invoice {invoice.id} without api_reference")
                skipped_count += 1
                continue

            if invoice.id is None:
                logger.warning(f"Skipping invoice without id ({invoice_ref})")
                skipped_count += 1
                continue

            # 7 = draft in Bexio
            if invoice.kb_item_status_id != 7:
                logger.info(
                    f"Skipping non-draft invoice {invoice.id} "
                    f"(status={invoice.kb_item_status_id})"
                )
                skipped_count += 1
                continue

            if invoice.is_valid_from is None:
                logger.info(f"Skipping invoice {invoice.id} without valid_from date")
                skipped_count += 1
                continue

            if invoice.is_valid_from > issue_from_cutoff_date:
                logger.info(
                    f"Skipping invoice {invoice.id} valid from {invoice.is_valid_from.isoformat()} "
                    f"(later than cutoff {issue_from_cutoff_date.isoformat()})"
                )
                skipped_count += 1
                continue

            try:
                result = bexio.issue_invoice(invoice.id)
                if result.get("success", False):
                    issued_count += 1
                    logger.info(f"Issued Bexio invoice {invoice.id} ({invoice_ref})")
                else:
                    # Treat non-success issue responses as skip to avoid retries on non-drafts
                    skipped_count += 1
                    logger.warning(
                        f"Issue call returned non-success for invoice {invoice.id}: {result}"
                    )
            except httpx.HTTPStatusError as e:
                status_code = e.response.status_code
                if status_code in (400, 422):
                    skipped_count += 1
                    logger.info(
                        f"Skipping invoice {invoice.id} due to non-issueable status "
                        f"(HTTP {status_code})"
                    )
                else:
                    error_count += 1
                    message = f"{invoice_ref}: HTTP {status_code}"
                    errors.append(message)
                    logger.error(f"Error issuing invoice {invoice.id}: {e}")
            except Exception as e:
                error_count += 1
                message = f"{invoice_ref}: {str(e)}"
                errors.append(message)
                logger.error(f"Error issuing invoice {invoice.id}: {e}")

    return {
        "status": "completed",
        "issued": issued_count,
        "skipped": skipped_count,
        "errors": error_count,
        "error_details": errors,
    }


def main() -> None:
    """Run sync or issue locally for development/testing."""
    from dotenv import load_dotenv

    load_dotenv()

    mode = sys.argv[1] if len(sys.argv) > 1 else "sync"
    if mode not in {"sync", "issue"}:
        print("Usage: uv run python -m woxio.main [sync|issue]")
        raise SystemExit(2)

    config = Config.from_env()
    if mode == "issue":
        result = issue_synced_invoices(config)
        print("Issue completed:")
        print(f"  Issued: {result['issued']}")
    else:
        result = sync_invoices(config)
        print("Sync completed:")
        print(f"  Created: {result['created']}")

    print(f"  Skipped: {result['skipped']}")
    print(f"  Errors: {result['errors']}")
    if result["error_details"]:
        print("  Error details:")
        for error in result["error_details"]:
            print(f"    - {error}")


if __name__ == "__main__":
    main()
