"""Testes da protecao CSRF — POST sem token deve ser bloqueado."""


class TestCSRF:
    def test_post_without_csrf_returns_403(self, client):
        """POST sem CSRF token deve retornar 403."""
        resp = client.post("/admin/login", data={
            "username": "FREE",
            "password": "FREE",
        })
        assert resp.status_code == 403

    def test_post_with_wrong_csrf_returns_403(self, client):
        """POST com CSRF token errado deve retornar 403."""
        # Fazer GET para gerar session
        client.get("/admin/login")
        resp = client.post("/admin/login", data={
            "username": "FREE",
            "password": "FREE",
            "csrf_token": "wrong-token-12345",
        })
        assert resp.status_code == 403

    def test_post_with_correct_csrf_works(self, client, csrf_token):
        """POST com CSRF token correto deve funcionar (nao 403)."""
        resp = client.post("/admin/login", data={
            "username": "FREE",
            "password": "FREE",
            "csrf_token": csrf_token,
        })
        # Deve ser 302 (redirect) ou 200, mas NAO 403
        assert resp.status_code != 403
