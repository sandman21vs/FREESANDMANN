import json
import logging
import urllib.request
from datetime import datetime, timezone

from model_config import get_config, set_config

logger = logging.getLogger(__name__)


def recalculate_raised_btc():
    try:
        onchain = float(get_config("raised_onchain_btc", "0"))
        lightning = float(get_config("raised_lightning_btc", "0"))
        adjustment = float(get_config("raised_btc_manual_adjustment", "0"))
        total = onchain + lightning + adjustment
        set_config("raised_btc", str(round(total, 8)))
    except (ValueError, TypeError):
        logger.warning(
            "Failed to recalculate raised_btc due to invalid numeric config "
            "onchain=%r lightning=%r adjustment=%r",
            get_config("raised_onchain_btc", "0"),
            get_config("raised_lightning_btc", "0"),
            get_config("raised_btc_manual_adjustment", "0"),
        )


def check_onchain_balance():
    address = get_config("btc_address")
    if not address:
        logger.debug("Skipping on-chain balance check because btc_address is not configured")
        return
    url = f"https://mempool.space/api/address/{address}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
        confirmed = data["chain_stats"]["funded_txo_sum"]
        mempool = data.get("mempool_stats", {}).get("funded_txo_sum", 0)
        balance_btc = (confirmed + mempool) / 100_000_000
        set_config("raised_onchain_btc", str(round(balance_btc, 8)))
        lightning = float(get_config("raised_lightning_btc", "0"))
        adjustment = float(get_config("raised_btc_manual_adjustment", "0"))
        total = balance_btc + lightning + adjustment
        set_config("raised_btc", str(round(total, 8)))
        set_config("last_balance_check", datetime.now(timezone.utc).isoformat())
        logger.info(
            "On-chain balance updated address_suffix=%s confirmed_sats=%s mempool_sats=%s total_btc=%.8f",
            address[-8:],
            confirmed,
            mempool,
            balance_btc,
        )
    except Exception:
        logger.exception(
            "Failed to update on-chain balance address_suffix=%s",
            address[-8:] if address else "unknown",
        )
