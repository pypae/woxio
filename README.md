# Woxio - Wodify to Bexio Integration

## Overview

Woxio syncs invoices from Wodify (fitness platform) to Bexio (accounting):

1. **Wodify invoice created** (auto-generated when membership is purchased) → Create corresponding invoice in Bexio
2. ~~**Bexio invoice paid** → Update Wodify invoice~~ ❌ _(not possible via API - see limitations)_

## Architecture (Stateless)

```
┌─────────────────────────────────────────────────────────────┐
│                     Google Cloud Platform                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────────┐         ┌──────────────────┐          │
│  │ Cloud Scheduler  │────────▶│ Cloud Function   │          │
│  │ (every 5-15 min) │         │ "sync_invoices"  │          │
│  └──────────────────┘         └──────────────────┘          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
         │                              │
         ▼                              ▼
    ┌─────────┐                   ┌─────────┐
    │ Wodify  │                   │  Bexio  │
    │   API   │                   │   API   │
    └─────────┘                   └─────────┘
```

## Key Insight: Wodify Auto-Generates Invoices

When a membership is created in Wodify, an invoice is **automatically generated**. This means:

- We poll **Wodify invoices** (not memberships)
- Only **unpaid** invoices are synced (paid/cancelled are skipped)
- Each Wodify invoice maps to a Bexio invoice
- We use Bexio's `api_reference` field to store the Wodify invoice ID

## Stateless ID Linking Strategy

| Platform      | Field           | Stores            |
| ------------- | --------------- | ----------------- |
| Bexio Invoice | `api_reference` | Wodify invoice ID |
| Bexio Contact | `mail`          | Used as lookup key (email match) |

This allows:

- **Idempotency**: Before creating a Bexio invoice, check if one already exists with the Wodify invoice ID in `api_reference`
- **Contact deduplication**: Search by email before creating → prevents duplicate contacts
- **No external state**: The mapping is stored in Bexio itself

## Data Flow

### Flow 1: Wodify Invoice → Bexio Invoice

```
InvoiceSyncService.initialize()
├── Fetch tax_id from active sales taxes
├── Fetch bank_account_id by IBAN lookup
└── Fetch revenue_account_id by account number lookup

sync_invoices()
├── GET Wodify invoices: /v1/financials/invoices
├── Filter to only UNPAID invoices
├── For each unpaid Wodify invoice:
│   ├── Check Bexio: GET /2.0/kb_invoice?api_reference={wodify_invoice_id}
│   ├── If no Bexio invoice exists:
│   │   ├── GET Wodify invoice details: /v1/financials/invoices/{id}
│   │   ├── GET Wodify client: /v1/clients/{client_id}
│   │   ├── Search Bexio contact: POST /2.0/contact/search (by email)
│   │   ├── If no Bexio contact exists:
│   │   │   ├── POST /3.0/fictional_users (create fictional user for customer)
│   │   │   └── POST /2.0/contact (create contact with fictional user_id)
│   │   ├── Map Wodify invoice to Bexio invoice (using product name as title)
│   │   └── POST /2.0/kb_invoice (create draft with api_reference=wodify_invoice_id)
```

### Fictional Users

When creating a new Bexio contact, a **fictional user** must first be created. In Bexio:
- `owner_id` = The real Bexio account user who manages the record (from config)
- `user_id` = The "responsible user" for the contact - must reference a user object

For imported contacts (customers), we create a **fictional user** to serve as the `user_id`:
- Fictional users are pseudo-users that don't consume Bexio licenses
- Each new contact gets its own fictional user with matching name/email
- This ensures proper assignment without using real Bexio user accounts

### Flow 2: Bexio Payment → Wodify Update

```
⚠️ NOT CURRENTLY POSSIBLE - Wodify invoices cannot be updated via API

Future options:
- Manual process in Wodify
- Wodify Workflows (Workato) if they support incoming webhooks
- Request API enhancement from Wodify
```

## Idempotency Guarantees

- **Invoice creation**: Check `api_reference` before creating → prevents duplicates
- **Contact creation**: Search by email before creating → prevents duplicate contacts
- **Polling window**: Use date filters to limit query scope without needing timestamps in state

## Field Mappings

### Client/Contact Mapping (Wodify Client → Bexio Contact)

| Wodify Field    | Bexio Field        | Notes                                           |
| --------------- | ------------------ | ----------------------------------------------- |
| `last_name`     | `name_1`           | Required - last name for persons                 |
| `first_name`    | `name_2`           | First name for persons                           |
| `email`         | `mail`             | **Used as lookup key** for existing contacts     |
| `phone`         | `phone_mobile`     | Mobile phone                                     |
| `address_1`     | `street_name`      | Street address                                   |
| `postal_code`   | `postcode`         | Postal/ZIP code                                  |
| `city`          | `city`             | City name                                        |
| —               | `contact_type_id`  | Always `2` (Person)                              |
| —               | `user_id`          | **From created fictional user** (see above)      |
| —               | `owner_id`         | Bexio owner ID (from config)                     |

**Lookup Strategy:**
1. Search Bexio for contact with matching `mail` (exact match)
2. If found → use existing `contact_id`
3. If not found → create new contact with mapped fields

### Invoice Mapping (Wodify Invoice → Bexio Invoice)

| Wodify Field                      | Bexio Field        | Notes                                    |
| --------------------------------- | ------------------ | ---------------------------------------- |
| `id`                              | `api_reference`    | **Used as idempotency key**              |
| `invoice_details[0].product`      | `title`            | Product name from invoice details        |
| `client_id`                       | `contact_id`       | Via client lookup (see above)            |
| `payment_due`                     | `is_valid_to`      | Payment due date                         |
| `created.created_on`              | `is_valid_from`    | Invoice date                             |
| `final_charge`                    | (position amount)  | Total amount (mapped to line items)      |
| —                                 | `user_id`          | Bexio owner ID (from config)             |
| —                                 | `bank_account_id`  | **Auto-fetched** by IBAN lookup          |
| —                                 | `mwst_type`        | `0` (VAT inclusive)                      |
| —                                 | `mwst_is_net`      | `false` (prices are gross)               |

### Invoice Line Items (Wodify → Bexio Positions)

| Wodify Field                 | Bexio Field    | Notes                               |
| ---------------------------- | -------------- | ----------------------------------- |
| `notes`                      | `text`         | Invoice notes only                  |
| `1`                          | `amount`       | Quantity (always 1)                 |
| `final_charge`               | `unit_price`   | Total invoice amount                |
| —                            | `type`         | `KbPositionCustom` for custom items |
| —                            | `account_id`   | **Auto-fetched** by account number  |
| —                            | `tax_id`       | **Auto-fetched** from active taxes  |

## Configuration

The sync service dynamically fetches these values from Bexio during initialization:

| Config Variable         | Fetched From                          |
| ----------------------- | ------------------------------------- |
| `BEXIO_INVOICE_IBAN`    | → `bank_account_id` via IBAN lookup   |
| `BEXIO_INVOICE_ACCOUNT_NO` | → `account_id` via account search  |
| (automatic)             | → `tax_id` from first active sales tax |

## API Endpoints

### Wodify API

- Base URL: `https://api.wodify.com/v1`
- Documentation: `https://docs.wodify.com` (requires login)
- Auth: `X-Api-Key: {api_key}` header
- Endpoints:
  - `GET /financials/invoices` - List invoices
  - `GET /financials/invoices/{id}` - Get invoice details (includes product info)
  - `GET /clients/{id}` - Get client details
  - ❌ `PATCH /financials/invoices/{id}` - **Not available** (invoices are read-only)

### Bexio API

- Base URL: `https://api.bexio.com`
- Documentation: `https://docs.bexio.com`
- Auth: `Authorization: Bearer {token}`, get your token here: https://developer.bexio.com/pat/ 
- Endpoints:
  - `GET /2.0/kb_invoice` - List invoices (supports `api_reference` filter)
  - `POST /2.0/kb_invoice` - Create invoice
  - `POST /2.0/kb_invoice/{id}/issue` - Issue invoice
  - `POST /2.0/contact/search` - Search contacts (by email)
  - `POST /2.0/contact` - Create contact
  - `GET /3.0/banking/accounts` - Get bank accounts (for IBAN lookup)
  - `POST /2.0/accounts/search` - Search accounts (for account_no lookup)
  - `GET /3.0/taxes` - Get tax rates

## Project Structure

```
woxio/
├── src/woxio/           # Main package
│   ├── __init__.py
│   ├── config.py        # Configuration (WodifyConfig, BexioConfig, SyncConfig)
│   ├── main.py          # Cloud Function entry point
│   ├── sync.py          # InvoiceSyncService - orchestrates the sync workflow
│   ├── mapping.py       # WodifyToBexioMapper - pure data transformation
│   ├── wodify/          # Wodify API client package
│   │   ├── __init__.py
│   │   ├── client.py    # WodifyClient class
│   │   └── models.py    # WodifyInvoice, WodifyInvoiceDetail, WodifyClient
│   └── bexio/           # Bexio API client package
│       ├── __init__.py
│       ├── client.py    # BexioClient class
│       └── models.py    # BexioInvoice, BexioContact
├── tests/               # Test suite
│   ├── conftest.py      # Pytest configuration
│   ├── unit/            # Unit tests
│   │   ├── test_mapping.py
│   │   └── test_sync.py
│   └── integration/     # Integration tests against live APIs
│       ├── test_wodify.py
│       └── test_bexio.py
├── scripts/             # One-off scripts for testing
├── .env                 # Local environment variables (not committed)
├── .env.template        # Template for environment variables
├── pyproject.toml       # Dependencies and tool config
└── README.md            # This file
```

## Local Development

```bash
# Setup
cp .env.template .env
# Edit .env with your API keys

# Install dependencies (including dev tools)
uv sync --all-extras

# Run sync locally
uv run python -m woxio.main

# Run unit tests
uv run pytest tests/unit/ -v

# Run integration tests (requires API keys in .env)
uv run pytest tests/integration/test_wodify.py -v
uv run pytest tests/integration/test_bexio.py -v

# Lint and type check
uv run ruff check src tests
uv run mypy src
```

## Deployment (GCP)

```bash
# Deploy sync_invoices function
gcloud functions deploy sync_invoices \
  --runtime python312 \
  --trigger-http \
  --env-vars-file .env.yaml

# Create scheduler (run every 15 minutes)
gcloud scheduler jobs create http sync-invoices-job \
  --schedule="*/15 * * * *" \
  --uri="https://REGION-PROJECT.cloudfunctions.net/sync_invoices"
```
