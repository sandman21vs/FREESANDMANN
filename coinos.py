"""Compatibility facade for Coinos helpers."""

from coinos_client import (
    COINOS_API_BASE,
    check_invoice,
    check_lightning_balance,
    create_invoice,
    get_account_username,
    get_fresh_liquid_address,
    get_fresh_onchain_address,
    get_onchain_address,
    get_received_sats,
)

__all__ = [
    "COINOS_API_BASE",
    "check_invoice",
    "check_lightning_balance",
    "create_invoice",
    "get_account_username",
    "get_fresh_liquid_address",
    "get_fresh_onchain_address",
    "get_onchain_address",
    "get_received_sats",
]
