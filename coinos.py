"""Cliente da API Coinos.io para receber pagamentos Lightning e Liquid."""
import json
import re
import urllib.request

import models


COINOS_API_BASE = "https://coinos.io/api"


def _coinos_request(method, path, body=None):
    api_key = models.get_config("coinos_api_key")
    if not api_key:
        return None

    url = f"{COINOS_API_BASE}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {api_key}")

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception:
        return None


def create_invoice(amount_sats, invoice_type="lightning"):
    if models.get_config("coinos_enabled") != "1":
        return None
    if not amount_sats or amount_sats < 1:
        return None
    if invoice_type not in ("lightning", "liquid"):
        return None

    result = _coinos_request("POST", "/invoice", {
        "invoice": {
            "amount": amount_sats,
            "type": invoice_type,
        }
    })
    return result


def check_invoice(invoice_hash):
    if not invoice_hash:
        return None
    # Coinos hash is the bolt11 string itself (lnbc...) which contains numbers and letters
    if not re.match(r'^[a-zA-Z0-9]+$', invoice_hash):
        return None
    return _coinos_request("GET", f"/invoice/{invoice_hash}")


def get_received_sats():
    result = _coinos_request("GET", "/payments")
    if not result or "incoming" not in result:
        return None
    total_sats = 0
    for currency_data in result["incoming"].values():
        total_sats += currency_data.get("sats", 0)
    return total_sats


def get_onchain_address():
    """Generate a Coinos onchain address via their API."""
    if models.get_config("coinos_enabled") != "1":
        return None
    if models.get_config("coinos_onchain") != "1":
        return None
    result = _coinos_request("POST", "/invoice", {
        "invoice": {
            "amount": 0,
            "type": "bitcoin",
        }
    })
    if result and "hash" in result:
        return result["hash"]
    return None


def check_lightning_balance():
    if models.get_config("coinos_enabled") != "1":
        return
    if not models.get_config("coinos_api_key"):
        return

    received_sats = get_received_sats()
    if received_sats is not None:
        balance_btc = received_sats / 100_000_000
        models.set_config("raised_lightning_btc", str(round(balance_btc, 8)))
        models.recalculate_raised_btc()
