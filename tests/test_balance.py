"""Testes do balance checker via rota admin (refresh manual)."""
import models


class TestBalanceRefresh:
    def test_refresh_balance_route(self, admin_session):
        """Rota de refresh manual deve funcionar."""
        models.set_config("btc_address", "")  # sem endereco, nao faz request externo

        with admin_session.session_transaction() as sess:
            csrf = sess.get("csrf_token", "")

        resp = admin_session.post("/admin/refresh-balance", data={
            "csrf_token": csrf,
        })
        assert resp.status_code == 302  # redirect para dashboard

    def test_refresh_balance_requires_login(self, client):
        """Refresh sem login deve redirecionar."""
        resp = client.post("/admin/refresh-balance")
        assert resp.status_code in (302, 403)
