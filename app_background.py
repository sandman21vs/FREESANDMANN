import logging
import threading

import coinos
import models

logger = logging.getLogger(__name__)

_balance_checker_started = False


def _start_balance_checker():
    global _balance_checker_started
    if _balance_checker_started:
        logger.info("Background maintenance loop already started; skipping duplicate init")
        return

    _balance_checker_started = True
    logger.info("Starting background maintenance loop interval_seconds=300")

    def _run():
        try:
            deleted_attempts = models.cleanup_old_attempts()
            if deleted_attempts:
                logger.info("Expired login attempts cleaned deleted=%s", deleted_attempts)
            models.check_onchain_balance()
            coinos.check_lightning_balance()
        except Exception:
            logger.exception("Background maintenance loop failed")
        finally:
            timer = threading.Timer(300, _run)
            timer.daemon = True
            timer.start()

    timer = threading.Timer(10, _run)
    timer.daemon = True
    timer.start()
