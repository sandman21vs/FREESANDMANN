"""Compatibility facade for Coinos helpers."""

from coinos_client import (
    COINOS_API_BASE,
    check_invoice,
    check_lightning_balance,
    create_invoice,
    get_onchain_address,
    get_received_sats,
)

import coinos_client as _coinos_client

urllib = _coinos_client.urllib

__all__ = [
    "COINOS_API_BASE",
    "check_invoice",
    "check_lightning_balance",
    "create_invoice",
    "get_onchain_address",
    "get_received_sats",
    "urllib",
]
