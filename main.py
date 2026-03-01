"""Cloud Function HTTP entrypoint."""

import logging
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR / "src"))

from woxio.config import Config  # noqa: E402
from woxio.main import issue_synced_invoices, sync_invoices  # noqa: E402

logger = logging.getLogger(__name__)


def sync_invoices_handler(request: Any) -> tuple[dict[str, Any], int]:
    """HTTP Cloud Function entry point."""
    del request  # Request body is currently unused for scheduled execution.
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


def issue_invoices_handler(request: Any) -> tuple[dict[str, Any], int]:
    """HTTP Cloud Function entry point for sending draft invoices."""
    del request  # Request body is currently unused for scheduled execution.
    try:
        config = Config.from_env()
        result = issue_synced_invoices(config)
        return result, 200
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        return {"status": "error", "message": str(e)}, 500
    except Exception as e:
        logger.exception("Unexpected error during invoice send job")
        return {"status": "error", "message": str(e)}, 500
