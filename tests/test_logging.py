"""Testes de logging para falhas externas."""
import logging

import models


def test_onchain_balance_failure_is_logged(temp_database, monkeypatch, caplog):
    """Falha na API do mempool.space deve gerar log de exceção."""
    models.set_config("btc_address", "bc1qtest1234567890")

    def fake_urlopen(*args, **kwargs):
        raise OSError("network down")

    monkeypatch.setattr("models.urllib.request.urlopen", fake_urlopen)

    with caplog.at_level(logging.ERROR):
        models.check_onchain_balance()

    assert "Failed to update on-chain balance" in caplog.text


def test_recalculate_invalid_numeric_config_is_logged(temp_database, caplog):
    """Configuracao numerica invalida deve gerar log util ao recalcular total."""
    models.set_config("raised_onchain_btc", "1.0")
    models.set_config("raised_lightning_btc", "not-a-number")
    models.set_config("raised_btc_manual_adjustment", "0.1")

    with caplog.at_level(logging.WARNING):
        models.recalculate_raised_btc()

    assert "Failed to recalculate raised_btc due to invalid numeric config" in caplog.text
