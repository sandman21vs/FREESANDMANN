"""Application-level donation flow helpers for routes."""

import logging

import coinos
import models

logger = logging.getLogger(__name__)

MIN_INVOICE_AMOUNT_SATS = 1
MAX_INVOICE_AMOUNT_SATS = 100_000_000
SUPPORTED_INVOICE_TYPES = ("lightning", "liquid")
MAX_INVOICE_HASH_LENGTH = 1000


def _parse_amount_sats(raw_amount):
    try:
        return int(raw_amount), None
    except (ValueError, TypeError):
        return None, "Invalid amount"


def _parse_received_sats(raw_received):
    if raw_received in (None, "", 0, "0"):
        return 0, None
    try:
        received = int(raw_received)
    except (ValueError, TypeError):
        return None, "Invalid webhook payload"
    if received < 0:
        return None, "Invalid webhook payload"
    return received, None


def create_invoice_response(data, webhook_url, remote_ip="unknown"):
    if models.get_config("coinos_enabled") != "1":
        logger.warning("Invoice creation rejected because Coinos is disabled ip=%s", remote_ip)
        return {"ok": False, "error": "Invoices not enabled"}, 400

    if not data or "amount_sats" not in data:
        return {"ok": False, "error": "amount_sats required"}, 400

    amount, amount_error = _parse_amount_sats(data.get("amount_sats"))
    if amount_error:
        return {"ok": False, "error": amount_error}, 400

    if amount < MIN_INVOICE_AMOUNT_SATS or amount > MAX_INVOICE_AMOUNT_SATS:
        return {
            "ok": False,
            "error": f"Amount must be between {MIN_INVOICE_AMOUNT_SATS} and {MAX_INVOICE_AMOUNT_SATS:,} sats",
        }, 400

    invoice_type = data.get("type", "lightning")
    if invoice_type not in SUPPORTED_INVOICE_TYPES:
        return {"ok": False, "error": "Type must be lightning or liquid"}, 400

    result = coinos.create_invoice(amount, invoice_type, webhook_url=webhook_url)
    if not result:
        logger.warning(
            "Invoice creation failed ip=%s amount_sats=%s type=%s",
            remote_ip,
            amount,
            invoice_type,
        )
        return {"ok": False, "error": "Failed to create invoice"}, 500

    logger.info(
        "Invoice created ip=%s amount_sats=%s type=%s hash_prefix=%s",
        remote_ip,
        amount,
        invoice_type,
        result.get("hash", "")[:12],
    )
    return {
        "ok": True,
        "hash": result.get("hash", ""),
        "bolt11": result.get("text", ""),
        "amount_sats": amount,
        "type": invoice_type,
    }, 200


def check_invoice_response(invoice_hash):
    if not invoice_hash or len(invoice_hash) > MAX_INVOICE_HASH_LENGTH:
        return {"paid": False, "error": "Invalid hash"}, 400

    result = coinos.check_invoice(invoice_hash)
    if result is None:
        return {"paid": False, "error": "Invoice not found"}, 404

    received, received_error = _parse_received_sats(result.get("received", 0))
    if received_error:
        logger.warning("Invoice check returned invalid received amount hash_prefix=%s", invoice_hash[:12])
        return {"paid": False, "error": "Invalid invoice data"}, 502

    paid = received > 0
    if paid:
        coinos.check_lightning_balance()
    return {"paid": paid, "amount_received": received}, 200


def handle_coinos_webhook(data):
    if not data:
        logger.warning("Coinos webhook rejected because body is empty")
        return {"ok": False}, 400

    webhook_secret = models.get_config("coinos_webhook_secret")
    if webhook_secret and data.get("secret") != webhook_secret:
        logger.warning("Coinos webhook rejected due to invalid secret")
        return {"ok": False}, 403

    received, received_error = _parse_received_sats(data.get("received", 0))
    if received_error:
        logger.warning("Coinos webhook rejected due to invalid received value value=%r", data.get("received"))
        return {"ok": False}, 400

    logger.info("Coinos webhook received received=%s", received)
    if received > 0:
        coinos.check_lightning_balance()

    return {"ok": True}, 200
