# Lightning Network Payment APIs - Research Report
## Receiving Payments WITHOUT Running a Lightning Node

Date: 2026-03-26

---

## EXECUTIVE SUMMARY

For the FreeSandmann fundraising site, the best options (ranked by simplicity) are:

1. **Coinos.io** - Simplest, no KYC, free for Lightning, has working API
2. **OpenNode** - Most professional, 1% fee, excellent docs, webhooks
3. **LNbits (hosted)** - Free/open-source, demo server for testing
4. **Strike API** - Requires KYC, limited countries, but very polished
5. **Alby** - Transitioning away from custodial (NOT recommended for new projects)

---

## 1. COINOS.IO API (RECOMMENDED)

### Overview
- Open-source Bitcoin/Lightning web wallet
- No KYC required - just username/password registration
- Supports Lightning, on-chain Bitcoin, and Liquid
- Very low fees (0% for Lightning, 0.1% for on-chain conversion)

### Getting Started
1. Create account at https://coinos.io (username + password only)
2. Go to Settings to obtain your API Bearer Token
3. Base URL: `https://coinos.io/api/`

### Authentication
```
Authorization: Bearer YOUR_TOKEN
Content-Type: application/json
```

### API Endpoints

#### Create Lightning Invoice
```bash
# Step 1: Generate a Lightning invoice
curl -X POST https://coinos.io/api/lightning/invoice \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"amount": 10000, "memo": "Donation for FreeSandmann"}'

# Step 2: Associate invoice with your user account
curl -X POST https://coinos.io/api/invoice \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"invoice": "<bolt11_invoice_from_step1>"}'
```

#### Check Balance
```bash
curl https://coinos.io/api/me \
  -H "Authorization: Bearer $TOKEN"
# Returns JSON with .balance field (in satoshis)
```

#### List Payments (poll for payment status)
```bash
curl https://coinos.io/api/payments \
  -H "Authorization: Bearer $TOKEN"
# Returns array of payments, search by invoice ID
```

### Python Example (using coinoslib)
```python
from coinoslib import Coinoslib

coinos = Coinoslib("YOUR_TOKEN")

# Create invoice for 10000 sats
invoice = coinos.add_invoice(10000, memo="FreeSandmann Donation")
print(invoice)  # Returns BOLT11 invoice string

# Check balance
balance = coinos.get_balance()

# Look up invoice status
status = coinos.lookup_invoice("lnbc...")

# List all invoices
invoices = coinos.list_invoices()
```

### PHP Example (using coinosphplib)
```php
require_once 'api_coinos.php';
// Set TOKEN and USUARIO in config.php

$api = new API_COINOS();

// Create invoice for 5000 sats
$result = $api->crearInvoice(5000);
// Returns: ['resultado' => 'ok', 'id' => '...', 'invoice' => 'lnbc...']

// Check if invoice was paid
$paid = $api->buscarInvoice($invoice_id);
// Returns: true/false

// Get balance
$balance = $api->obtenerBalance();
```

### Fees
- Lightning receiving: FREE (0%)
- Lightning sending: FREE (0%)
- On-chain/Liquid conversion: 0.1%
- No setup fees, no merchant fees

### Payment Status Detection
- **Polling**: Use `GET /api/payments` and search for your invoice
- **Webhooks**: The invoice route supports a `webhook` field (set on update)
- **Python lib**: Use `lookup_invoice()` to check individual invoices

### Pros
- No KYC, instant setup
- Zero fees for Lightning
- Open-source
- Simple REST API
- Lightning Address support (username@coinos.io)

### Cons
- API documentation is minimal (must read source code)
- Custodial (they hold your funds)
- Smaller operation than Strike/OpenNode
- No official webhook documentation

### Documentation
- Docs page: https://coinos.io/docs
- Server source: https://github.com/coinos/coinos-server
- Python lib: https://github.com/coinos/coinoslib
- PHP lib: https://github.com/bitao36/coinosphplib

---

## 2. OPENNODE

### Overview
- Professional Bitcoin payment processor
- 1% fee on transactions
- Excellent documentation and webhooks
- KYC required for production

### Getting Started
1. Sign up at https://opennode.com
2. Get API key at https://dev.opennode.co/settings/api
3. Select "Invoices" permission type for the key

### Authentication
```
Authorization: YOUR_API_KEY
Content-Type: application/json
```

### Create Invoice (Charge)
```bash
curl -X POST https://api.opennode.com/v1/charges \
  -H "Content-Type: application/json" \
  -H "Authorization: YOUR_API_KEY" \
  -d '{
    "amount": 10000,
    "currency": "BTC",
    "description": "FreeSandmann Donation",
    "callback_url": "https://yoursite.com/webhook/opennode",
    "success_url": "https://yoursite.com/thank-you",
    "auto_settle": false
  }'
```

**Response:**
```json
{
  "data": {
    "id": "charge-uuid",
    "address": "bc1q...",
    "lightning_invoice": {
      "payreq": "lnbc10000n1..."
    },
    "uri": "bitcoin:bc1q...?lightning=lnbc...",
    "hosted_checkout_url": "https://checkout.opennode.com/{id}",
    "status": "unpaid"
  }
}
```

### Check Payment Status
```bash
curl https://api.opennode.com/v1/charge/{charge_id} \
  -H "Authorization: YOUR_API_KEY"
```

### Webhooks
- Set `callback_url` when creating a charge
- OpenNode sends POST with status updates (paid/processing/underpaid)
- Also provides hosted checkout page automatically

### Python Example
```python
import requests

API_KEY = "your-opennode-api-key"
BASE_URL = "https://api.opennode.com/v1"

# Create charge
response = requests.post(
    f"{BASE_URL}/charges",
    headers={
        "Authorization": API_KEY,
        "Content-Type": "application/json"
    },
    json={
        "amount": 5000,       # amount in satoshis (or fiat with currency param)
        "description": "FreeSandmann Donation",
        "callback_url": "https://yoursite.com/webhook",
    }
)
charge = response.json()["data"]
bolt11 = charge["lightning_invoice"]["payreq"]
charge_id = charge["id"]

# Check status
status_resp = requests.get(
    f"{BASE_URL}/charge/{charge_id}",
    headers={"Authorization": API_KEY}
)
status = status_resp.json()["data"]["status"]  # "unpaid", "paid", "processing"
```

### Fees
- 1% per transaction
- No setup fees
- No conversion fees
- Lightning withdrawals: FREE
- Limit: No Lightning invoice > 5 BTC (500,000,000 sats)

### Pros
- Best documentation of all options
- Built-in hosted checkout page
- Dual payment (Lightning + on-chain) in one charge
- Professional webhooks
- Fiat currency support (USD amount auto-converted)

### Cons
- 1% fee
- KYC required for production
- Development environment available for testing

### Documentation
- Developer docs: https://developers.opennode.com
- Creating charges: https://developers.opennode.com/docs/creating-a-charge
- Pricing: https://opennode.com/pricing/

---

## 3. LNBITS (HOSTED INSTANCE)

### Overview
- Free, open-source Lightning wallet/accounts system
- Can use hosted demo for testing (demo.lnbits.com)
- Production: lnbits.com offers hosted instances (21 sats/hr)
- Very simple API with just invoice/read keys

### Getting Started
1. Go to https://demo.lnbits.com (testing) or https://lnbits.com (production)
2. Create a wallet - you get two API keys automatically:
   - **Invoice/Read key**: Can only create invoices (safe to expose in frontend)
   - **Admin key**: Can spend funds (keep secret)

### Authentication
```
X-Api-Key: YOUR_INVOICE_READ_KEY
Content-Type: application/json
```

### Create Invoice
```bash
curl -X POST https://demo.lnbits.com/api/v1/payments \
  -H "X-Api-Key: YOUR_INVOICE_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "out": false,
    "amount": 1000,
    "memo": "FreeSandmann Donation",
    "expiry": 3600,
    "webhook": "https://yoursite.com/webhook/lnbits"
  }'
```

**Response:**
```json
{
  "payment_hash": "abc123...",
  "payment_request": "lnbc1000n1...",
  "checking_id": "..."
}
```

### Check Payment Status
```bash
curl https://demo.lnbits.com/api/v1/payments/PAYMENT_HASH \
  -H "X-Api-Key: YOUR_INVOICE_KEY"
```

**Response:**
```json
{
  "paid": true,
  "pending": false,
  "amount_sats": 1000,
  "fee_msat": 0,
  "preimage": "..."
}
```

### Python Example
```python
import requests

LNBITS_URL = "https://demo.lnbits.com"
INVOICE_KEY = "your-invoice-read-key"

# Create invoice
resp = requests.post(
    f"{LNBITS_URL}/api/v1/payments",
    headers={
        "X-Api-Key": INVOICE_KEY,
        "Content-Type": "application/json"
    },
    json={
        "out": False,
        "amount": 1000,  # satoshis
        "memo": "FreeSandmann Donation",
        "webhook": "https://yoursite.com/webhook"
    }
)
data = resp.json()
bolt11 = data["payment_request"]
payment_hash = data["payment_hash"]

# Check if paid
status = requests.get(
    f"{LNBITS_URL}/api/v1/payments/{payment_hash}",
    headers={"X-Api-Key": INVOICE_KEY}
)
is_paid = status.json()["paid"]
```

### Fees
- Software itself: FREE (open source)
- Hosted demo: FREE (but not for production)
- Hosted production (lnbits.com): 21 sats/hour (~504 sats/day)
- No per-transaction fees

### Webhooks
- Set `webhook` parameter when creating invoice
- LNbits sends POST to your URL when invoice is paid
- Can also poll via GET endpoint

### Pros
- Simplest API of all options
- Invoice key is safe to expose (can only receive, not spend)
- Built-in webhook support
- Open source, self-hostable
- Extensive extension system
- No KYC on demo

### Cons
- Demo server NOT for production use
- Hosted instance costs sats/hour
- Self-hosting requires a Lightning backend node
- Less reliable than commercial services

### Documentation
- Main docs: https://docs.lnbits.org
- API guide: https://bitclawd.com/code/lightning-create-invoice/
- GitHub: https://github.com/lnbits/lnbits

---

## 4. STRIKE API

### Overview
- Very polished, corporate-grade API
- Requires KYC and business account
- Limited country availability
- 1% fee with currency conversion

### Getting Started
1. Sign up at https://strike.me
2. Contact partners@strike.me for API access
3. Get API keys from the dashboard
4. Sandbox available for testing

### Authentication
```
Authorization: Bearer YOUR_API_KEY
Content-Type: application/json
```

### Create Invoice
```bash
# Step 1: Create invoice
curl -X POST https://api.strike.me/v1/invoices \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "correlationId": "donation-001",
    "description": "FreeSandmann Donation",
    "amount": {
      "currency": "USD",
      "amount": "10.00"
    }
  }'

# Step 2: Generate quote (creates the actual Lightning invoice)
curl -X POST https://api.strike.me/v1/invoices/{INVOICE_ID}/quote \
  -H "Authorization: Bearer $API_KEY"
# Response includes: lnInvoice (BOLT11), quoteId, expiration
# Cross-currency quotes expire in 30 SECONDS
# Same-currency quotes expire in 1 HOUR
```

### Check Payment Status
```bash
curl https://api.strike.me/v1/invoices/{INVOICE_ID} \
  -H "Authorization: Bearer $API_KEY"
# Status: UNPAID, PENDING, PAID
```

### Webhooks
```bash
# Subscribe to invoice updates
curl -X POST https://api.strike.me/v1/subscriptions \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "webhookUrl": "https://yoursite.com/webhook/strike",
    "webhookVersion": "v1",
    "secret": "your-webhook-secret",
    "enabled": true,
    "eventTypes": ["invoice.updated"]
  }'
```

### Fees
- Lightning routing: ~0.15% of invoice
- Currency conversion: 1% spread
- No withdrawal fees
- Strike-to-Strike: FREE

### Pros
- Professional, well-documented
- Fiat currency support (USD, EUR, GBP)
- Sandbox environment for testing
- Proper webhook system

### Cons
- KYC required
- Limited country availability
- Two-step invoice creation (create + quote)
- Cross-currency quotes expire in 30 seconds
- Must contact sales for API access

### Documentation
- Main docs: https://docs.strike.me
- Receiving payments: https://docs.strike.me/walkthrough/receiving-payments/
- Sandbox: https://docs.strike.me/sandbox/

---

## 5. ALBY (NOT RECOMMENDED FOR NEW PROJECTS)

### Overview
- Was a popular custodial Lightning wallet with API
- **Custodial wallet was SHUT DOWN in January 2025**
- Transitioning to self-custodial Alby Hub (requires running a node)
- NWC (Nostr Wallet Connect) replacing old OAuth API

### Status
- Custodial service: DISCONTINUED
- Alby Hub: Self-custodial (requires node) - defeats the purpose
- Old wallet API still partially functional but deprecated

### Documentation
- Developer guide: https://guides.getalby.com/developer-guide
- Alby Hub: https://github.com/getAlby/hub

**Verdict**: Do NOT use Alby for new custodial integrations.

---

## COMPARISON TABLE

| Feature              | Coinos.io       | OpenNode        | LNbits (hosted) | Strike          |
|---------------------|-----------------|-----------------|-----------------|-----------------|
| KYC Required        | No              | Yes             | No (demo)       | Yes             |
| Setup Time          | 5 minutes       | Days (KYC)      | 5 minutes       | Days (KYC+sales)|
| Fee                 | 0%              | 1%              | 0% (21sat/hr)   | 0.15-1%         |
| Webhooks            | Basic           | Excellent       | Good            | Excellent       |
| Invoice Creation    | 1 API call      | 1 API call      | 1 API call      | 2 API calls     |
| Payment Check       | Poll            | Poll + Webhook  | Poll + Webhook  | Poll + Webhook  |
| Fiat Amounts        | No              | Yes             | No              | Yes             |
| Documentation       | Minimal         | Excellent       | Good            | Excellent       |
| Hosted Checkout     | No              | Yes             | No              | No              |
| Open Source         | Yes             | No              | Yes             | No              |
| Lightning Address   | Yes             | No              | No              | Yes             |
| Max Invoice         | No limit noted  | 5 BTC           | Depends on node | No limit noted  |

---

## RECOMMENDATION FOR FREESANDMANN

### Primary: Coinos.io
- Zero fees means 100% of donations reach the cause
- No KYC means you can start TODAY
- Simple API with Python/PHP libraries available
- Lightning Address (username@coinos.io) can be shared directly

### Backup/Alternative: LNbits on lnbits.com
- Slightly better documented API
- Built-in webhook support
- Very small hosting cost (21 sats/hour)

### Implementation Strategy
1. Create a Coinos account, get API token
2. For each donation: call `POST /api/lightning/invoice` with amount
3. Display the BOLT11 invoice as QR code
4. Poll `GET /api/payments` every few seconds to detect payment
5. On payment detected, update the donation tracker

### Simplest Possible Integration (Python/Flask)
```python
import requests
import time

COINOS_TOKEN = "your-token-here"
COINOS_API = "https://coinos.io/api"
HEADERS = {
    "Authorization": f"Bearer {COINOS_TOKEN}",
    "Content-Type": "application/json"
}

def create_lightning_invoice(amount_sats, memo="FreeSandmann Donation"):
    """Create a Lightning invoice for the given amount in satoshis."""
    # Create the Lightning invoice
    resp = requests.post(
        f"{COINOS_API}/lightning/invoice",
        headers=HEADERS,
        json={"amount": amount_sats, "memo": memo}
    )
    return resp.json()

def check_payment(invoice_id):
    """Check if an invoice has been paid by searching payments."""
    resp = requests.get(
        f"{COINOS_API}/payments",
        headers=HEADERS
    )
    payments = resp.json()
    for payment in payments:
        if payment.get("id") == invoice_id:
            return True
    return False

def wait_for_payment(invoice_id, timeout=300):
    """Poll for payment status, return True if paid within timeout."""
    start = time.time()
    while time.time() - start < timeout:
        if check_payment(invoice_id):
            return True
        time.sleep(3)
    return False
```
