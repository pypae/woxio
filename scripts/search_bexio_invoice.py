#!/usr/bin/env python3
"""Search for a Bexio invoice by document_nr."""

import json
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv

from woxio.bexio.client import BexioClient
from woxio.config import BexioConfig

# Load environment variables from .env file
load_dotenv(Path(__file__).parent.parent / ".env")


def main() -> None:
    """Search for a Bexio invoice by document_nr."""
    document_nr = "RE-05081"

    config = BexioConfig()
    with BexioClient(config) as client:
        print(f"Searching for invoice with document_nr: {document_nr}")
        invoice = client.get_invoice_by_document_nr(document_nr)

        if invoice and invoice.id:
            print(f"\nFound invoice (search result):")
            print(json.dumps(invoice.model_dump(mode="json"), indent=2, default=str))

            # Fetch full invoice details including positions
            print(f"\n--- Fetching full invoice details (ID: {invoice.id}) ---\n")
            full_invoice = client.get_invoice(invoice.id)
            print(json.dumps(full_invoice.model_dump(mode="json"), indent=2, default=str))

            # Also fetch raw response to see all available fields
            print(f"\n--- Raw API response ---\n")
            response = client.client.get(f"/2.0/kb_invoice/{invoice.id}")
            response.raise_for_status()
            print(json.dumps(response.json(), indent=2, default=str))
        else:
            print(f"\nNo invoice found with document_nr: {document_nr}")


if __name__ == "__main__":
    main()
