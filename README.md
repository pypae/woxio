# Woxio - Wodify ↔ Bexio Integration

## Overview

Woxio syncs invoices from Wodify (fitness platform) to Bexio (accounting):

1. **Wodify invoice created** (auto-generated when membership is purchased) → Create corresponding invoice in Bexio
2. **Bexio invoice paid** → Update Wodify invoice ❌ _(not possible via API - see limitations)_

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
- Each Wodify invoice maps to a Bexio invoice
- We use Bexio's `api_reference` field to store the Wodify invoice ID

## Stateless ID Linking Strategy

| Platform      | Field           | Stores            |
| ------------- | --------------- | ----------------- |
| Bexio Invoice | `api_reference` | Wodify invoice ID |

This allows:

- **Idempotency**: Before creating a Bexio invoice, check if one already exists with the Wodify invoice ID in `api_reference`
- **No external state**: The mapping is stored in Bexio itself

## Data Flow

### Flow 1: Wodify Invoice → Bexio Invoice

```
sync_invoices()
├── GET Wodify invoices: /v1/financials/invoices
├── For each Wodify invoice:
│   ├── Check Bexio: GET /2.0/kb_invoice?api_reference={wodify_invoice_id}
│   ├── If no Bexio invoice exists:
│   │   ├── Map Wodify invoice data to Bexio invoice fields
│   │   ├── POST /2.0/kb_invoice (create draft with api_reference=wodify_invoice_id)
```

### Flow 2: Bexio Payment → Wodify Update (TODO)

```
⚠️ NOT CURRENTLY POSSIBLE - Wodify invoices cannot be updated via API

Future options:
- Manual process in Wodify
- Wodify Workflows (Workato) if they support incoming webhooks
- Request API enhancement from Wodify
```

## Idempotency Guarantees

- **Invoice creation**: Check `api_reference` before creating → prevents duplicates
- **Polling window**: Use date filters to limit query scope without needing timestamps in state

## API Endpoints

### Wodify API

- Base URL: `https://api.wodify.com/v1`
- Documentation: `https://docs.wodify.com` (requires login)
- Auth: `X-Api-Key: {api_key}` header
- Endpoints:
  - `GET /financials/invoices` - List invoices
  - ❌ `PATCH /financials/invoices/{id}` - **Not available** (invoices are read-only)

### Bexio API

- Base URL: `https://api.bexio.com`
- Documentation: `https://docs.bexio.com`
- Auth: `Authorization: Bearer {token}`
- Endpoints:
  - `GET /2.0/kb_invoice` - List invoices (supports `api_reference` filter)
  - `POST /2.0/kb_invoice` - Create invoice
  - `POST /2.0/kb_invoice/{id}/issue` - Issue invoice
  - `GET /2.0/kb_invoice/{id}/payment` - Get payments for invoice
  - `GET /2.0/contact` - Get contacts (for customer lookup)

## Project Structure

```
woxio/
├── src/woxio/           # Main package
│   ├── __init__.py
│   ├── config.py        # Configuration from environment
│   ├── main.py          # Cloud Function entry point & sync logic
│   ├── wodify/          # Wodify API client package
│   │   ├── __init__.py
│   │   ├── client.py    # WodifyClient class
│   │   └── models.py    # WodifyInvoice, WodifyInvoiceItem
│   └── bexio/           # Bexio API client package
│       ├── __init__.py
│       ├── client.py    # BexioClient class
│       └── models.py    # BexioInvoice, BexioContact
├── tests/               # Test suite
│   ├── conftest.py      # Pytest configuration
│   └── integration/     # Integration tests against live APIs
│       ├── test_wodify.py
│       └── test_bexio.py
├── .env                 # Local environment variables (not committed)
├── .env.template        # Template for environment variables
├── pyproject.toml       # Dependencies and tool config
└── AGENTS.md            # This file
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

## TODO

- [x] ~~Verify Wodify API endpoints~~ → Use `GET /v1/financials/invoices`
- [x] ~~Identify Wodify field for storing Bexio invoice ID~~ → Not needed (one-way sync)
- [ ] Define field mapping: Wodify invoice → Bexio invoice
- [ ] Implement Wodify client (`GET /v1/financials/invoices`)
- [ ] Implement Bexio client (create invoice, issue invoice)
- [ ] Add error handling and retries
- [ ] Add logging/monitoring
- [ ] Deploy to GCP
- [ ] **Future**: Investigate Bexio → Wodify payment sync (requires Wodify API update or Workflows)

## API Notes

### Bexio `api_reference` field

- Available on invoice objects
- Stores Wodify invoice ID for linking
- Used for idempotency: `GET /2.0/kb_invoice?api_reference={wodify_invoice_id}`

### Wodify Invoice API

- `GET /v1/financials/invoices` - Retrieves invoices
- Invoices are **read-only** via API (cannot update payment status)
- Invoices are auto-generated when memberships are created

### OpenAPI Specifications

- **Bexio**: Does not currently provide an OpenAPI definition (per their docs)
- **Wodify**: No public OpenAPI spec found; docs require login
- API clients must be implemented by manually referencing their documentation

## Limitations

1. **One-way sync only**: Wodify invoices cannot be updated via API

   - When a Bexio invoice is paid, we cannot automatically mark the Wodify invoice as paid
   - This requires manual reconciliation in Wodify or a future API enhancement

2. **Wodify API documentation**: Requires login to access full docs at `docs.wodify.com`
