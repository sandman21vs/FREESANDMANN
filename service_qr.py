"""Shared QR-code response helpers for public routes."""

import io

import qrcode
from flask import send_file

import models

_QR_TYPE_CONFIG = {
    "btc": ("btc_address", "bitcoin:{value}"),
    "lightning": ("lightning_address", "{value}"),
    "liquid": ("liquid_address", "liquidnetwork:{value}"),
}


def _build_png_response(data, max_age, no_cache=False):
    img = qrcode.make(data, box_size=8, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    response = send_file(buf, mimetype="image/png", max_age=max_age)
    if no_cache:
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


def get_wallet_qr_response(qr_type):
    config_entry = _QR_TYPE_CONFIG.get(qr_type)
    if not config_entry:
        return None

    config_key, format_string = config_entry
    value = models.get_config(config_key)
    if not value:
        return None

    return _build_png_response(format_string.format(value=value), max_age=0, no_cache=True)


def get_invoice_qr_response(bolt11):
    if not bolt11 or len(bolt11) > 2000:
        return None
    return _build_png_response(bolt11, max_age=60)
