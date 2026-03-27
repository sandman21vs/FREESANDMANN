"""Low-level Coinos.io API client and balance sync helpers."""

import json
import logging
import re
import urllib.request

import models

logger = logging.getLogger(__name__)

COINOS_API_BASE = "https://coinos.io/api"
_COINOS_HASH_PATTERN = re.compile(r"^[a-zA-Z0-9]+$")


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
        logger.exception("Coinos API request failed method=%s path=%s", method, path)
        return None


def create_invoice(amount_sats, invoice_type="lightning", webhook_url=None):
    if models.get_config("coinos_enabled") != "1":
        return None
    if not amount_sats or amount_sats < 1:
        return None
    if invoice_type not in ("lightning", "liquid"):
        return None

    invoice_data = {
        "amount": amount_sats,
        "type": invoice_type,
    }
    if webhook_url:
        webhook_secret = models.get_config("coinos_webhook_secret")
        invoice_data["webhook"] = webhook_url
        if webhook_secret:
            invoice_data["secret"] = webhook_secret

    return _coinos_request("POST", "/invoice", {"invoice": invoice_data})


def check_invoice(invoice_hash):
    if not invoice_hash:
        return None
    if not _COINOS_HASH_PATTERN.match(invoice_hash):
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
    if models.get_config("coinos_enabled") != "1":
        return None
    if models.get_config("coinos_onchain") != "1":
        return None
    result = _coinos_request(
        "POST",
        "/invoice",
        {
            "invoice": {
                "amount": 0,
                "type": "bitcoin",
            }
        },
    )
    if result and "hash" in result:
        logger.info("Coinos on-chain address generated address_suffix=%s", result["hash"][-8:])
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
        logger.info(
            "Lightning balance updated received_sats=%s total_btc=%.8f",
            received_sats,
            balance_btc,
        )
