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


def get_fresh_onchain_address():
    """Generate a fresh Coinos BTC address (creates a 0-amount bitcoin invoice)."""
    if not models.get_config("coinos_api_key"):
        return None
    result = _coinos_request(
        "POST",
        "/invoice",
        {"invoice": {"amount": 0, "type": "bitcoin"}},
    )
    if result and "hash" in result:
        logger.info("Coinos BTC address generated address_suffix=%s", result["hash"][-8:])
        return result["hash"]
    return None


def get_fresh_liquid_address():
    """Generate a fresh Coinos Liquid address (creates a 0-amount liquid invoice)."""
    if not models.get_config("coinos_api_key"):
        return None
    result = _coinos_request(
        "POST",
        "/invoice",
        {"invoice": {"amount": 0, "type": "liquid"}},
    )
    if result and "hash" in result:
        logger.info("Coinos Liquid address generated address_suffix=%s", result["hash"][-8:])
        return result["hash"]
    return None


def _coinos_public_request(path):
    """Fetch from a public (no-auth) Coinos API endpoint."""
    url = f"{COINOS_API_BASE}{path}"
    req = urllib.request.Request(url, method="GET")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception:
        logger.exception("Coinos public API request failed path=%s", path)
        return None


def get_account_username():
    """Fetch the Coinos account username for LN address derivation.

    Tries /me first (works with full tokens), then falls back to
    creating a 0-amount invoice to get the uid and looking it up
    via the public /users/<uid> endpoint (works with read-only tokens).
    """
    if not models.get_config("coinos_api_key"):
        return None

    # Try /me first (full-access tokens)
    result = _coinos_request("GET", "/me")
    if result and "username" in result:
        return result["username"]

    # Fallback: create a dummy invoice to get uid, then public lookup
    invoice = _coinos_request(
        "POST", "/invoice",
        {"invoice": {"amount": 0, "type": "bitcoin"}},
    )
    if not invoice or "uid" not in invoice:
        return None

    uid = invoice["uid"]
    user_info = _coinos_public_request(f"/users/{uid}")
    if user_info and "username" in user_info:
        logger.info("Coinos username resolved via public API username=%s", user_info["username"])
        return user_info["username"]
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
