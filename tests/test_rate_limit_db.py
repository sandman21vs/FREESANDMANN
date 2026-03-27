"""Testes do rate limiting em SQLite."""
import models


class TestRateLimitStorage:
    def test_below_limit_not_blocked(self, temp_database):
        """Quatro tentativas não devem bloquear o IP."""
        ip = "203.0.113.10"
        for _ in range(models.MAX_LOGIN_ATTEMPTS - 1):
            models.record_login_attempt(ip)

        assert models.is_rate_limited(ip) is False

    def test_at_limit_blocks_ip(self, temp_database):
        """A quinta tentativa já deve colocar o IP em lockout."""
        ip = "203.0.113.10"
        for _ in range(models.MAX_LOGIN_ATTEMPTS):
            models.record_login_attempt(ip)

        assert models.is_rate_limited(ip) is True

    def test_clear_login_attempts_removes_lockout(self, temp_database):
        """Login bem-sucedido limpa o histórico do IP."""
        ip = "203.0.113.10"
        for _ in range(models.MAX_LOGIN_ATTEMPTS):
            models.record_login_attempt(ip)

        models.clear_login_attempts(ip)

        assert models.is_rate_limited(ip) is False

    def test_expired_attempts_do_not_count(self, temp_database):
        """Tentativas com mais de 5 minutos não devem contar para o limite."""
        ip = "203.0.113.10"
        for _ in range(models.MAX_LOGIN_ATTEMPTS):
            models.record_login_attempt(ip)

        conn = models.get_db()
        conn.execute(
            "UPDATE login_attempts SET attempted_at = datetime('now', '-6 minutes') WHERE ip = ?",
            (ip,),
        )
        conn.commit()
        conn.close()

        assert models.is_rate_limited(ip) is False

    def test_cleanup_old_attempts_removes_stale_rows(self, temp_database):
        """Cleanup periódico deve remover registros expirados."""
        ip = "203.0.113.10"
        for _ in range(3):
            models.record_login_attempt(ip)

        conn = models.get_db()
        conn.execute(
            "UPDATE login_attempts SET attempted_at = datetime('now', '-11 minutes') WHERE ip = ?",
            (ip,),
        )
        conn.commit()
        conn.close()

        deleted = models.cleanup_old_attempts()

        conn = models.get_db()
        row = conn.execute("SELECT COUNT(*) AS count FROM login_attempts WHERE ip = ?", (ip,)).fetchone()
        conn.close()

        assert deleted == 3
        assert row["count"] == 0

    def test_rate_limit_is_shared_across_clients(self, app):
        """Dois clients diferentes devem compartilhar o mesmo lockout pelo banco."""
        shared_ip = "198.51.100.77"
        client_one = app.test_client()
        client_two = app.test_client()

        def get_csrf(client):
            client.get("/admin/login")
            with client.session_transaction() as sess:
                return sess.get("csrf_token", "")

        csrf_one = get_csrf(client_one)
        csrf_two = get_csrf(client_two)

        for _ in range(3):
            client_one.post(
                "/admin/login",
                data={"username": "FREE", "password": "wrong", "csrf_token": csrf_one},
                follow_redirects=True,
                environ_base={"REMOTE_ADDR": shared_ip},
            )

        resp = None
        for _ in range(3):
            resp = client_two.post(
                "/admin/login",
                data={"username": "FREE", "password": "wrong", "csrf_token": csrf_two},
                follow_redirects=True,
                environ_base={"REMOTE_ADDR": shared_ip},
            )

        assert resp is not None
        assert b"Too many" in resp.data or b"rate" in resp.data.lower()
