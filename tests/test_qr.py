"""Testes da geracao de QR codes."""
import models


class TestQRCode:
    def test_qr_btc_returns_png(self, client):
        """QR code BTC deve retornar imagem PNG."""
        models.set_config("btc_address", "bc1qtest123456")
        resp = client.get("/qr/btc")
        assert resp.status_code == 200
        assert resp.content_type == "image/png"
        # PNG magic bytes
        assert resp.data[:4] == b'\x89PNG'

    def test_qr_lightning_returns_png(self, client):
        """QR code Lightning deve retornar imagem PNG."""
        models.set_config("lightning_address", "lnurl1testaddress")
        resp = client.get("/qr/lightning")
        assert resp.status_code == 200
        assert resp.content_type == "image/png"

    def test_qr_btc_empty_address_404(self, client):
        """QR code sem endereco BTC configurado deve retornar 404."""
        models.set_config("btc_address", "")
        resp = client.get("/qr/btc")
        assert resp.status_code == 404

    def test_qr_lightning_empty_address_404(self, client):
        """QR code sem endereco Lightning configurado deve retornar 404."""
        models.set_config("lightning_address", "")
        resp = client.get("/qr/lightning")
        assert resp.status_code == 404

    def test_qr_invalid_type_404(self, client):
        """Tipo de QR invalido deve retornar 404."""
        resp = client.get("/qr/invalid")
        assert resp.status_code == 404

    def test_qr_no_cache(self, client):
        """QR code nao deve ser cacheado para refletir mudancas de endereco."""
        models.set_config("btc_address", "bc1qtest123456")
        resp = client.get("/qr/btc")
        cache = resp.headers.get("Cache-Control", "")
        assert "no-cache" in cache or "no-store" in cache

    def test_qr_changes_with_address(self, client):
        """QR code deve mudar quando o endereco muda."""
        models.set_config("btc_address", "bc1qaddress1")
        resp1 = client.get("/qr/btc")
        qr1 = resp1.data

        models.set_config("btc_address", "bc1qaddress2")
        resp2 = client.get("/qr/btc")
        qr2 = resp2.data

        assert qr1 != qr2
