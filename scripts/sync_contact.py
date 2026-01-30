#!/usr/bin/env python3
"""Test script to fetch Wodify client and sync to Bexio contact.

This script demonstrates the contact sync flow:
1. Get a Wodify invoice
2. Fetch the associated Wodify client
3. Search for existing Bexio contact by email
4. Create Bexio contact if not found
"""

import json
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv

from woxio.bexio.client import BexioClient
from woxio.config import BexioConfig, WodifyConfig
from woxio.wodify.client import WodifyClient

# Load environment variables from .env file
load_dotenv(Path(__file__).parent.parent / ".env")


def main() -> None:
    """Test the contact sync workflow."""
    wodify_config = WodifyConfig()
    bexio_config = BexioConfig()

    with WodifyClient(wodify_config) as wodify, BexioClient(bexio_config) as bexio:
        # Step 1: Get a recent Wodify invoice
        print("=== Step 1: Fetching recent Wodify invoices ===")
        response = wodify.get_invoices(page_size=1)
        if not response.invoices:
            print("No invoices found")
            return
        invoice = response.invoices[0]
        print(f"Using invoice ID: {invoice.id}")
        print(f"Invoice: {invoice.invoice_number}")
        print(f"Client ID: {invoice.client_id}")
        print(f"Amount: {invoice.final_charge}")
        print()

        # Step 2: Fetch the Wodify client
        print(f"=== Step 2: Fetching Wodify client {invoice.client_id} ===")
        client = wodify.get_client(invoice.client_id)
        print(f"Client: {client.full_name}")
        print(f"Email: {client.email}")
        print(f"Phone: {client.phone}")
        print(f"Raw data:")
        print(json.dumps(client.model_dump(mode="json"), indent=2, default=str))
        print()

        if not client.email:
            print("ERROR: Client has no email address, cannot search/create contact")
            return

        # Step 3: Search for existing Bexio contact
        print(f"=== Step 3: Searching Bexio for contact with email: {client.email} ===")
        existing_contacts = bexio.search_contacts_by_email(client.email)

        if existing_contacts:
            print(f"Found {len(existing_contacts)} existing contact(s):")
            for contact in existing_contacts:
                print(f"  - ID: {contact.id}, Name: {contact.name}, Email: {contact.mail}")
            print()
            print("Contact already exists - no need to create")
        else:
            print("No existing contact found")
            print()
            print("=== Step 4: Would create new Bexio contact ===")
            print("(Not actually creating - this is a test script)")
            print(f"  contact_type_id: 2 (Person)")
            print(f"  name_1 (last name): {client.last_name}")
            print(f"  name_2 (first name): {client.first_name}")
            print(f"  mail: {client.email}")
            print(f"  phone_mobile: {client.phone}")
            print(f"  remarks: Wodify Client ID: {client.id}")

            # Uncomment to actually create:
            # contact, created = bexio.get_or_create_contact_by_email(
            #     email=client.email,
            #     first_name=client.first_name,
            #     last_name=client.last_name,
            #     phone=client.phone,
            #     user_id=1,  # TODO: Get from config
            #     owner_id=1,  # TODO: Get from config
            #     remarks=f"Wodify Client ID: {client.id}",
            # )
            # print(f"Created contact: {contact.id}")


if __name__ == "__main__":
    main()
