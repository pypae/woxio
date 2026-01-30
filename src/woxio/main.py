"""Cloud Function entry point for Woxio invoice sync."""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

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


def sync_invoices_handler(request: Any) -> tuple[dict[str, Any], int]:
    """HTTP Cloud Function entry point.

    Args:
        request: The Flask request object.

    Returns:
        JSON response with sync results.
    """
    try:
        config = Config.from_env()
        result = sync_invoices(config)
        return result, 200
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        return {"status": "error", "message": str(e)}, 500
    except Exception as e:
        logger.exception("Unexpected error during sync")
        return {"status": "error", "message": str(e)}, 500


def main() -> None:
    """Run sync locally for development/testing."""
    from dotenv import load_dotenv

    load_dotenv()

    config = Config.from_env()
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
