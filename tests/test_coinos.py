"""Testes da integracao com a API Coinos.io."""
import json
import urllib.request

import models


class MockResponse:
    def __init__(self, data, status=200):
        self._data = json.dumps(data).encode()
        self.status = status

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


# ── Testes unitarios do modulo coinos.py ────────────────────────────


class TestCreateInvoice:
    def test_success(self, temp_database, monkeypatch):
        models.set_config("coinos_enabled", "1")
        models.set_config("coinos_api_key", "test-token")

        def mock_urlopen(req, **kwargs):
            return MockResponse({
                "hash": "abc123",
                "text": "lnbc1000n1...",
                "amount": 1000,
                "received": 0,
            })

        monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

        import importlib
        import coinos
        importlib.reload(coinos)

        result = coinos.create_invoice(1000)
        assert result is not None
        assert result["hash"] == "abc123"
        assert result["text"] == "lnbc1000n1..."

    def test_api_failure(self, temp_database, monkeypatch):
        models.set_config("coinos_enabled", "1")
        models.set_config("coinos_api_key", "test-token")

        def mock_urlopen(req, **kwargs):
            raise ConnectionError("API down")

        monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

        import importlib
        import coinos
        importlib.reload(coinos)

        result = coinos.create_invoice(1000)
        assert result is None

    def test_disabled(self, temp_database, monkeypatch):
        models.set_config("coinos_enabled", "0")
        models.set_config("coinos_api_key", "test-token")

        called = []

        def mock_urlopen(req, **kwargs):
            called.append(True)
            return MockResponse({})

        monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

        import importlib
        import coinos
        importlib.reload(coinos)

        result = coinos.create_invoice(1000)
        assert result is None
        assert len(called) == 0

    def test_no_api_key(self, temp_database, monkeypatch):
        models.set_config("coinos_enabled", "1")
        models.set_config("coinos_api_key", "")

        called = []

        def mock_urlopen(req, **kwargs):
            called.append(True)
            return MockResponse({})

        monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

        import importlib
        import coinos
        importlib.reload(coinos)

        result = coinos.create_invoice(1000)
        assert result is None
        assert len(called) == 0

    def test_invalid_amount(self, temp_database, monkeypatch):
        models.set_config("coinos_enabled", "1")
        models.set_config("coinos_api_key", "test-token")

        import importlib
        import coinos
        importlib.reload(coinos)

        assert coinos.create_invoice(0) is None
        assert coinos.create_invoice(-1) is None
        assert coinos.create_invoice(None) is None


class TestCheckInvoice:
    def test_paid(self, temp_database, monkeypatch):
        models.set_config("coinos_api_key", "test-token")

        def mock_urlopen(req, **kwargs):
            return MockResponse({
                "hash": "abc123",
                "amount": 1000,
                "received": 1000,
            })

        monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

        import importlib
        import coinos
        importlib.reload(coinos)

        result = coinos.check_invoice("abc123")
        assert result is not None
        assert result["received"] == 1000

    def test_unpaid(self, temp_database, monkeypatch):
        models.set_config("coinos_api_key", "test-token")

        def mock_urlopen(req, **kwargs):
            return MockResponse({
                "hash": "abc123",
                "amount": 1000,
                "received": 0,
            })

        monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

        import importlib
        import coinos
        importlib.reload(coinos)

        result = coinos.check_invoice("abc123")
        assert result is not None
        assert result["received"] == 0

    def test_invalid_hash(self, temp_database):
        import importlib
        import coinos
        importlib.reload(coinos)

        assert coinos.check_invoice("") is None
        assert coinos.check_invoice("abc!@#") is None
        assert coinos.check_invoice(None) is None

    def test_long_bolt11_hash(self, temp_database, monkeypatch):
        """Coinos uses the bolt11 string as the hash, which can be ~400 chars."""
        models.set_config("coinos_api_key", "test-token")

        bolt11 = "lnbc1u1p5ut32x" + "a" * 380

        def mock_urlopen(req, **kwargs):
            return MockResponse({"hash": bolt11, "amount": 1000, "received": 1000})

        monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

        import importlib
        import coinos
        importlib.reload(coinos)

        result = coinos.check_invoice(bolt11)
        assert result is not None
        assert result["received"] == 1000


class TestCheckLightningBalance:
    def test_updates_config(self, temp_database, monkeypatch):
        models.set_config("coinos_enabled", "1")
        models.set_config("coinos_api_key", "test-token")
        models.set_config("raised_lightning_btc", "0")

        def mock_urlopen(req, **kwargs):
            return MockResponse({
                "payments": [],
                "count": 2,
                "incoming": {"CHF": {"sats": 500000, "fiat": "273.00"}},
                "outgoing": {},
            })

        monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

        import importlib
        import coinos
        importlib.reload(coinos)

        coinos.check_lightning_balance()

        assert models.get_config("raised_lightning_btc") == "0.005"

    def test_disabled_does_nothing(self, temp_database, monkeypatch):
        models.set_config("coinos_enabled", "0")
        models.set_config("coinos_api_key", "test-token")
        models.set_config("raised_lightning_btc", "0")

        called = []

        def mock_urlopen(req, **kwargs):
            called.append(True)
            return MockResponse({
                "payments": [],
                "incoming": {"CHF": {"sats": 500000}},
                "outgoing": {},
            })

        monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

        import importlib
        import coinos
        importlib.reload(coinos)

        coinos.check_lightning_balance()

        assert models.get_config("raised_lightning_btc") == "0"
        assert len(called) == 0


# ── Testes de rotas ─────────────────────────────────────────────────


class TestCreateInvoiceRoute:
    def _setup_coinos(self, monkeypatch):
        models.set_config("coinos_enabled", "1")
        models.set_config("coinos_api_key", "test-token")

        def mock_urlopen(req, **kwargs):
            return MockResponse({
                "hash": "testhash123",
                "text": "lnbc1000n1testinvoice",
                "amount": 1000,
                "received": 0,
            })

        monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

    def test_success(self, client, monkeypatch):
        self._setup_coinos(monkeypatch)

        client.get("/donate")
        with client.session_transaction() as sess:
            csrf = sess.get("csrf_token", "")

        resp = client.post("/donate/create-invoice",
            data=json.dumps({"amount_sats": 1000}),
            content_type="application/json",
            headers={"X-CSRFToken": csrf})

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["hash"] == "testhash123"
        assert data["bolt11"] == "lnbc1000n1testinvoice"

    def test_disabled(self, client, monkeypatch):
        models.set_config("coinos_enabled", "0")

        client.get("/donate")
        with client.session_transaction() as sess:
            csrf = sess.get("csrf_token", "")

        resp = client.post("/donate/create-invoice",
            data=json.dumps({"amount_sats": 1000}),
            content_type="application/json",
            headers={"X-CSRFToken": csrf})

        assert resp.status_code == 400
        data = resp.get_json()
        assert data["ok"] is False

    def test_invalid_amount(self, client, monkeypatch):
        self._setup_coinos(monkeypatch)

        client.get("/donate")
        with client.session_transaction() as sess:
            csrf = sess.get("csrf_token", "")

        for bad_amount in [0, -1, 20000000, "abc"]:
            resp = client.post("/donate/create-invoice",
                data=json.dumps({"amount_sats": bad_amount}),
                content_type="application/json",
                headers={"X-CSRFToken": csrf})
            assert resp.status_code == 400

    def test_no_csrf(self, client, monkeypatch):
        self._setup_coinos(monkeypatch)

        resp = client.post("/donate/create-invoice",
            data=json.dumps({"amount_sats": 1000}),
            content_type="application/json")

        assert resp.status_code == 403


class TestCheckInvoiceRoute:
    def test_paid(self, client, monkeypatch):
        models.set_config("coinos_api_key", "test-token")
        models.set_config("coinos_enabled", "1")
        bolt11 = "lnbc1000n1testinvoice" + "a" * 100

        call_count = []

        def mock_urlopen(req, **kwargs):
            call_count.append(req.full_url)
            if "/payments" in req.full_url:
                return MockResponse({
                    "payments": [],
                    "incoming": {"CHF": {"sats": 5000}},
                    "outgoing": {},
                })
            return MockResponse({
                "hash": bolt11,
                "amount": 1000,
                "received": 1000,
            })

        monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

        resp = client.get(f"/donate/check-invoice/{bolt11}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["paid"] is True
        # Should also trigger balance update
        assert any("/payments" in url for url in call_count)

    def test_unpaid(self, client, monkeypatch):
        models.set_config("coinos_api_key", "test-token")
        bolt11 = "lnbc1000n1testinvoice" + "b" * 100

        def mock_urlopen(req, **kwargs):
            return MockResponse({
                "hash": bolt11,
                "amount": 1000,
                "received": 0,
            })

        monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

        resp = client.get(f"/donate/check-invoice/{bolt11}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["paid"] is False


class TestInvoiceQrRoute:
    def test_generates_qr(self, client):
        resp = client.get("/donate/invoice-qr?bolt11=lnbc1000n1test")
        assert resp.status_code == 200
        assert resp.content_type == "image/png"

    def test_missing_bolt11(self, client):
        resp = client.get("/donate/invoice-qr")
        assert resp.status_code == 400

    def test_empty_bolt11(self, client):
        resp = client.get("/donate/invoice-qr?bolt11=")
        assert resp.status_code == 400


class TestAdminSettingsSavesCoinos:
    def test_saves_coinos_fields(self, admin_session):
        with admin_session.session_transaction() as sess:
            csrf = sess.get("csrf_token", "")

        resp = admin_session.post("/admin/settings", data={
            "csrf_token": csrf,
            "site_title": "Test",
            "coinos_enabled": "1",
            "coinos_api_key": "my-secret-token",
        })

        assert resp.status_code == 302
        assert models.get_config("coinos_enabled") == "1"
        assert models.get_config("coinos_api_key") == "my-secret-token"

    def test_lightning_btc_readonly_when_enabled(self, admin_session):
        models.set_config("raised_lightning_btc", "0.005")

        with admin_session.session_transaction() as sess:
            csrf = sess.get("csrf_token", "")

        resp = admin_session.post("/admin/settings", data={
            "csrf_token": csrf,
            "site_title": "Test",
            "coinos_enabled": "1",
            "coinos_api_key": "token",
            "raised_lightning_btc": "999",
        })

        assert resp.status_code == 302
        assert models.get_config("raised_lightning_btc") == "0.005"

    def test_coinos_onchain_generates_address(self, admin_session, monkeypatch):
        """When coinos_onchain is enabled, btc_address is set from Coinos API."""
        models.set_config("coinos_api_key", "test-token")

        def mock_urlopen(req, **kwargs):
            return MockResponse({
                "hash": "bc1qtestaddressfromcoinos",
                "text": "bc1qtestaddressfromcoinos",
                "amount": 0,
                "type": "bitcoin",
            })

        monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

        with admin_session.session_transaction() as sess:
            csrf = sess.get("csrf_token", "")

        resp = admin_session.post("/admin/settings", data={
            "csrf_token": csrf,
            "site_title": "Test",
            "coinos_enabled": "1",
            "coinos_onchain": "1",
            "coinos_api_key": "test-token",
            "btc_address": "old-address-should-be-ignored",
        })

        assert resp.status_code == 302
        assert models.get_config("coinos_onchain") == "1"
        assert models.get_config("btc_address") == "bc1qtestaddressfromcoinos"

    def test_coinos_onchain_disabled_keeps_manual_address(self, admin_session):
        """When coinos_onchain is disabled, btc_address is set from form."""
        with admin_session.session_transaction() as sess:
            csrf = sess.get("csrf_token", "")

        resp = admin_session.post("/admin/settings", data={
            "csrf_token": csrf,
            "site_title": "Test",
            "coinos_enabled": "1",
            "coinos_api_key": "test-token",
            "btc_address": "bc1qmanualaddress",
        })

        assert resp.status_code == 302
        assert models.get_config("coinos_onchain") == "0"
        assert models.get_config("btc_address") == "bc1qmanualaddress"
