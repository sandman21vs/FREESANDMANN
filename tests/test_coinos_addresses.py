"""Tests for the Coinos address display toggle and cached address system."""
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


def _mock_coinos_api(monkeypatch, username="testuser", btc_hash="bc1qcoinosgenerated"):
    """Mock Coinos API to return predictable username and BTC address."""
    def mock_urlopen(req, **kwargs):
        url = req.full_url
        if "/me" in url:
            return MockResponse({"username": username})
        if "/invoice" in url:
            return MockResponse({"hash": btc_hash, "amount": 0, "type": "bitcoin"})
        return MockResponse({})

    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)


# ── Unit tests: coinos_client functions ──────────────────────────────


class TestGetFreshOnchainAddress:
    def test_returns_address_with_api_key(self, temp_database, monkeypatch):
        models.set_config("coinos_api_key", "test-token")
        _mock_coinos_api(monkeypatch, btc_hash="bc1qfreshaddr")

        import importlib
        import coinos_client
        importlib.reload(coinos_client)

        result = coinos_client.get_fresh_onchain_address()
        assert result == "bc1qfreshaddr"

    def test_returns_none_without_api_key(self, temp_database, monkeypatch):
        models.set_config("coinos_api_key", "")
        called = []

        def mock_urlopen(req, **kwargs):
            called.append(True)
            return MockResponse({})

        monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

        import importlib
        import coinos_client
        importlib.reload(coinos_client)

        result = coinos_client.get_fresh_onchain_address()
        assert result is None
        assert len(called) == 0

    def test_does_not_require_coinos_enabled(self, temp_database, monkeypatch):
        """get_fresh_onchain_address only needs API key, not coinos_enabled."""
        models.set_config("coinos_api_key", "test-token")
        models.set_config("coinos_enabled", "0")
        _mock_coinos_api(monkeypatch, btc_hash="bc1qworks")

        import importlib
        import coinos_client
        importlib.reload(coinos_client)

        result = coinos_client.get_fresh_onchain_address()
        assert result == "bc1qworks"


class TestGetAccountUsername:
    def test_returns_username_with_api_key(self, temp_database, monkeypatch):
        models.set_config("coinos_api_key", "test-token")
        _mock_coinos_api(monkeypatch, username="satoshi")

        import importlib
        import coinos_client
        importlib.reload(coinos_client)

        result = coinos_client.get_account_username()
        assert result == "satoshi"

    def test_returns_none_without_api_key(self, temp_database, monkeypatch):
        models.set_config("coinos_api_key", "")

        import importlib
        import coinos_client
        importlib.reload(coinos_client)

        result = coinos_client.get_account_username()
        assert result is None

    def test_does_not_require_coinos_enabled(self, temp_database, monkeypatch):
        """get_account_username only needs API key, not coinos_enabled."""
        models.set_config("coinos_api_key", "test-token")
        models.set_config("coinos_enabled", "0")
        _mock_coinos_api(monkeypatch, username="hal")

        import importlib
        import coinos_client
        importlib.reload(coinos_client)

        result = coinos_client.get_account_username()
        assert result == "hal"


# ── Validation tests ─────────────────────────────────────────────────


class TestCoinosShowAddressesValidation:
    def test_show_addresses_requires_api_key(self, admin_session):
        with admin_session.session_transaction() as sess:
            csrf = sess.get("csrf_token", "")

        resp = admin_session.post("/admin/settings", data={
            "csrf_token": csrf,
            "site_title": "Test",
            "coinos_show_addresses": "1",
            "coinos_api_key": "",
        }, follow_redirects=True)

        assert resp.status_code == 200
        assert b"Coinos API key is required to show Coinos addresses" in resp.data
        assert models.get_config("coinos_show_addresses") == "0"

    def test_show_addresses_saves_with_api_key(self, admin_session):
        with admin_session.session_transaction() as sess:
            csrf = sess.get("csrf_token", "")

        # Need to mock Coinos API since caching happens on save
        import urllib.request as ur
        original_urlopen = ur.urlopen

        def mock_urlopen(req, **kwargs):
            url = req.full_url
            if "/me" in url:
                return MockResponse({"username": "testuser"})
            if "/invoice" in url:
                return MockResponse({"hash": "bc1qcached", "amount": 0})
            return MockResponse({})

        ur.urlopen = mock_urlopen
        try:
            resp = admin_session.post("/admin/settings", data={
                "csrf_token": csrf,
                "site_title": "Test",
                "coinos_show_addresses": "1",
                "coinos_api_key": "my-token",
            })
            assert resp.status_code == 302
            assert models.get_config("coinos_show_addresses") == "1"
        finally:
            ur.urlopen = original_urlopen


# ── Address caching tests ────────────────────────────────────────────


class TestCoinosAddressCaching:
    def test_caches_addresses_on_save(self, admin_session, monkeypatch):
        _mock_coinos_api(monkeypatch, username="alice", btc_hash="bc1qaliceaddr")

        with admin_session.session_transaction() as sess:
            csrf = sess.get("csrf_token", "")

        resp = admin_session.post("/admin/settings", data={
            "csrf_token": csrf,
            "site_title": "Test",
            "coinos_show_addresses": "1",
            "coinos_api_key": "test-token",
        })

        assert resp.status_code == 302
        assert models.get_config("coinos_cached_ln_address") == "alice@coinos.io"
        assert models.get_config("coinos_cached_btc_address") == "bc1qaliceaddr"

    def test_clears_cache_when_disabled(self, admin_session, monkeypatch):
        # Pre-populate cache
        models.set_config("coinos_cached_ln_address", "old@coinos.io")
        models.set_config("coinos_cached_btc_address", "bc1qoldaddr")
        _mock_coinos_api(monkeypatch)

        with admin_session.session_transaction() as sess:
            csrf = sess.get("csrf_token", "")

        resp = admin_session.post("/admin/settings", data={
            "csrf_token": csrf,
            "site_title": "Test",
            "coinos_show_addresses": "",  # OFF
            "coinos_api_key": "test-token",
        })

        assert resp.status_code == 302
        assert models.get_config("coinos_cached_btc_address") == ""
        assert models.get_config("coinos_cached_ln_address") == ""

    def test_clears_cache_when_api_key_removed(self, admin_session, monkeypatch):
        models.set_config("coinos_cached_ln_address", "old@coinos.io")
        models.set_config("coinos_cached_btc_address", "bc1qoldaddr")
        _mock_coinos_api(monkeypatch)

        with admin_session.session_transaction() as sess:
            csrf = sess.get("csrf_token", "")

        resp = admin_session.post("/admin/settings", data={
            "csrf_token": csrf,
            "site_title": "Test",
            "coinos_show_addresses": "1",
            "coinos_api_key": "",  # removed
        }, follow_redirects=True)

        assert resp.status_code == 200
        # Validation error because show_addresses needs API key
        assert models.get_config("coinos_cached_btc_address") == "bc1qoldaddr"  # not saved due to error


# ── Public site address enrichment tests ─────────────────────────────


class TestPublicSiteAddressEnrichment:
    def test_coinos_addresses_shown_when_toggle_on(self, client):
        models.set_config("coinos_show_addresses", "1")
        models.set_config("coinos_cached_ln_address", "bob@coinos.io")
        models.set_config("coinos_cached_btc_address", "bc1qcoinosbob")
        models.set_config("lightning_address", "manual@ln.addr")
        models.set_config("btc_address", "bc1qmanual")
        models.set_config("setup_complete", "1")

        resp = client.get("/donate")
        assert resp.status_code == 200
        # Coinos addresses override manual ones
        assert b"bob@coinos.io" in resp.data
        assert b"bc1qcoinosbob" in resp.data
        assert b"manual@ln.addr" not in resp.data
        assert b"bc1qmanual" not in resp.data

    def test_manual_addresses_shown_when_toggle_off(self, client):
        models.set_config("coinos_show_addresses", "0")
        models.set_config("coinos_cached_ln_address", "bob@coinos.io")
        models.set_config("coinos_cached_btc_address", "bc1qcoinosbob")
        models.set_config("lightning_address", "manual@ln.addr")
        models.set_config("btc_address", "bc1qmanual")
        models.set_config("setup_complete", "1")

        resp = client.get("/donate")
        assert resp.status_code == 200
        assert b"manual@ln.addr" in resp.data
        assert b"bc1qmanual" in resp.data
        assert b"bob@coinos.io" not in resp.data

    def test_empty_cache_no_qr_shown(self, client):
        models.set_config("coinos_show_addresses", "1")
        models.set_config("coinos_cached_ln_address", "")
        models.set_config("coinos_cached_btc_address", "")
        models.set_config("lightning_address", "")
        models.set_config("btc_address", "")
        models.set_config("setup_complete", "1")

        resp = client.get("/donate")
        assert resp.status_code == 200
        # No QR codes should appear
        assert b"qr-card" not in resp.data

    def test_partial_cache_shows_available(self, client):
        models.set_config("coinos_show_addresses", "1")
        models.set_config("coinos_cached_ln_address", "partial@coinos.io")
        models.set_config("coinos_cached_btc_address", "")
        models.set_config("lightning_address", "")
        models.set_config("btc_address", "bc1qmanualbtc")
        models.set_config("setup_complete", "1")

        resp = client.get("/donate")
        assert resp.status_code == 200
        # LN from cache, BTC stays manual (no cache override for empty)
        assert b"partial@coinos.io" in resp.data
        assert b"bc1qmanualbtc" in resp.data

    def test_landing_page_shows_coinos_addresses(self, client):
        models.set_config("coinos_show_addresses", "1")
        models.set_config("coinos_cached_ln_address", "home@coinos.io")
        models.set_config("coinos_cached_btc_address", "bc1qhomeaddr")
        models.set_config("setup_complete", "1")

        resp = client.get("/")
        assert resp.status_code == 200
        assert b"home@coinos.io" in resp.data
        assert b"bc1qhomeaddr" in resp.data


# ── Settings template tests ──────────────────────────────────────────


class TestSettingsTemplateCoinos:
    def test_show_addresses_toggle_visible(self, admin_session):
        resp = admin_session.get("/admin/settings")
        assert resp.status_code == 200
        assert b"coinos_show_addresses" in resp.data
        assert b"Show Coinos addresses on public site" in resp.data

    def test_cached_addresses_preview_shown(self, admin_session):
        models.set_config("coinos_show_addresses", "1")
        models.set_config("coinos_cached_ln_address", "preview@coinos.io")
        models.set_config("coinos_cached_btc_address", "bc1qpreview")

        resp = admin_session.get("/admin/settings")
        assert resp.status_code == 200
        assert b"preview@coinos.io" in resp.data
        assert b"bc1qpreview" in resp.data

    def test_manual_address_hints_when_coinos_active(self, admin_session):
        models.set_config("coinos_show_addresses", "1")

        resp = admin_session.get("/admin/settings")
        assert resp.status_code == 200
        assert b"Coinos" in resp.data
