"""Cloud Function entry point for Woxio invoice sync."""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from woxio.bexio import BexioClient
from woxio.config import Config
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
        # Calculate cutoff: now - poll_interval - buffer
        cutoff = datetime.now(UTC) - timedelta(
            minutes=config.poll_interval_minutes,
            hours=config.poll_buffer_hours,
        )
        logger.info(
            f"Fetching invoices from Wodify created after {cutoff.isoformat()} "
            f"(poll_interval={config.poll_interval_minutes}min, buffer={config.poll_buffer_hours}h)"
        )

        for wodify_invoice in wodify.get_recent_invoices(cutoff):
            try:
                # Check if invoice already exists in Bexio
                if bexio.invoice_exists_for_reference(wodify_invoice.id):
                    logger.debug(f"Invoice {wodify_invoice.id} already synced, skipping")
                    skipped_count += 1
                    continue

                # TODO: Map Wodify invoice to Bexio invoice
                # This requires:
                # 1. Finding or creating the contact in Bexio
                # 2. Mapping invoice fields and line items
                # 3. Creating the invoice

                logger.info(f"Would create Bexio invoice for Wodify invoice {wodify_invoice.id}")
                # Placeholder - actual implementation needs field mapping
                created_count += 1

            except Exception as e:
                logger.error(f"Error processing invoice {wodify_invoice.id}: {e}")
                errors.append(f"{wodify_invoice.id}: {str(e)}")
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
