"""Testes das rotas admin — login, logout, dashboard, settings, articles CRUD, media links."""
import models


class TestAdminLogin:
    def test_login_page_returns_200(self, client):
        """Pagina de login deve retornar 200."""
        resp = client.get("/admin/login")
        assert resp.status_code == 200

    def test_login_correct_credentials(self, client, csrf_token):
        """Login com credenciais corretas deve redirecionar (302)."""
        resp = client.post("/admin/login", data={
            "username": "FREE",
            "password": "FREE",
            "csrf_token": csrf_token,
        })
        # Deve redirecionar para change_password (primeiro login)
        assert resp.status_code == 302

    def test_login_wrong_password(self, client, csrf_token):
        """Login com senha errada deve mostrar erro."""
        resp = client.post("/admin/login", data={
            "username": "FREE",
            "password": "wrongpassword",
            "csrf_token": csrf_token,
        }, follow_redirects=True)
        assert b"Invalid" in resp.data or resp.status_code == 200

    def test_login_wrong_username(self, client, csrf_token):
        """Login com username errado deve falhar."""
        resp = client.post("/admin/login", data={
            "username": "WRONGUSER",
            "password": "FREE",
            "csrf_token": csrf_token,
        }, follow_redirects=True)
        assert b"Invalid" in resp.data

    def test_rate_limiting(self, client, csrf_token):
        """Apos 5 tentativas erradas, deve bloquear."""
        for i in range(6):
            resp = client.post("/admin/login", data={
                "username": "FREE",
                "password": "wrong",
                "csrf_token": csrf_token,
            }, follow_redirects=True)
        # Na 6a tentativa, deve mostrar mensagem de rate limit
        assert b"Too many" in resp.data or b"rate" in resp.data.lower()


class TestAdminLogout:
    def test_logout_redirects(self, admin_session):
        """Logout deve redirecionar para homepage."""
        resp = admin_session.get("/admin/logout")
        assert resp.status_code == 302

    def test_logout_clears_session(self, admin_session):
        """Apos logout, acessar dashboard deve redirecionar para login."""
        admin_session.get("/admin/logout")
        resp = admin_session.get("/admin/")
        assert resp.status_code == 302  # redirect para login


class TestForcePasswordChange:
    def test_force_change_on_first_login(self, client, csrf_token):
        """Primeiro login deve forcar troca de senha."""
        resp = client.post("/admin/login", data={
            "username": "FREE",
            "password": "FREE",
            "csrf_token": csrf_token,
        })
        # Deve redirecionar para change-password
        assert resp.status_code == 302
        assert "change-password" in resp.headers.get("Location", "")

    def test_admin_routes_redirect_when_force_change(self, client, csrf_token):
        """Com force_change ativo, rotas admin devem redirecionar para troca de senha."""
        # Login
        client.post("/admin/login", data={
            "username": "FREE",
            "password": "FREE",
            "csrf_token": csrf_token,
        })
        # Tentar acessar dashboard
        resp = client.get("/admin/")
        assert resp.status_code == 302
        assert "change-password" in resp.headers.get("Location", "")

    def test_change_password_success(self, client, csrf_token):
        """Trocar senha com dados validos deve funcionar."""
        # Login primeiro
        client.post("/admin/login", data={
            "username": "FREE",
            "password": "FREE",
            "csrf_token": csrf_token,
        })
        # Trocar senha
        resp = client.post("/admin/change-password", data={
            "new_password": "newsecure123",
            "confirm_password": "newsecure123",
            "csrf_token": csrf_token,
        })
        assert resp.status_code == 302  # redirect para dashboard

    def test_change_password_too_short(self, client, csrf_token):
        """Senha menor que 8 caracteres deve ser rejeitada."""
        client.post("/admin/login", data={
            "username": "FREE",
            "password": "FREE",
            "csrf_token": csrf_token,
        })
        resp = client.post("/admin/change-password", data={
            "new_password": "short",
            "confirm_password": "short",
            "csrf_token": csrf_token,
        }, follow_redirects=True)
        assert b"8 characters" in resp.data or b"least 8" in resp.data

    def test_change_password_mismatch(self, client, csrf_token):
        """Senhas que nao conferem devem ser rejeitadas."""
        client.post("/admin/login", data={
            "username": "FREE",
            "password": "FREE",
            "csrf_token": csrf_token,
        })
        resp = client.post("/admin/change-password", data={
            "new_password": "newsecure123",
            "confirm_password": "different456",
            "csrf_token": csrf_token,
        }, follow_redirects=True)
        assert b"match" in resp.data.lower()

    def test_change_password_reuse_default(self, client, csrf_token):
        """Nao deve permitir reusar a senha padrao 'FREE'."""
        client.post("/admin/login", data={
            "username": "FREE",
            "password": "FREE",
            "csrf_token": csrf_token,
        })
        resp = client.post("/admin/change-password", data={
            "new_password": "FREE",
            "confirm_password": "FREE",
            "csrf_token": csrf_token,
        }, follow_redirects=True)
        assert b"default" in resp.data.lower() or b"cannot" in resp.data.lower()


class TestAdminDashboard:
    def test_dashboard_returns_200(self, admin_session):
        """Dashboard deve retornar 200 para admin logado."""
        resp = admin_session.get("/admin/")
        assert resp.status_code == 200

    def test_dashboard_requires_login(self, client):
        """Dashboard sem login deve redirecionar para login."""
        resp = client.get("/admin/")
        assert resp.status_code == 302


class TestAdminSettings:
    def test_settings_returns_200(self, admin_session):
        """Settings deve retornar 200."""
        resp = admin_session.get("/admin/settings")
        assert resp.status_code == 200

    def test_settings_update(self, admin_session):
        """Atualizar settings deve salvar valores."""
        with admin_session.session_transaction() as sess:
            csrf = sess.get("csrf_token", "")

        resp = admin_session.post("/admin/settings", data={
            "site_title": "New Title",
            "site_description": "New Desc",
            "site_tagline": "New Tag",
            "btc_address": "bc1qnewtestaddress",
            "lightning_address": "lnurl1test",
            "goal_btc": "5.0",
            "raised_lightning_btc": "0.5",
            "raised_btc_manual_adjustment": "0.1",
            "goal_description": "New Goal",
            "supporters_count": "10",
            "hero_image_url": "",
            "deadline_text": "Court date April 15",
            "transparency_text": "Lawyer fees",
            "og_image_url": "",
            "wallet_explorer_url": "",
            "csrf_token": csrf,
        })
        assert resp.status_code == 302  # redirect

        # Verificar que valores foram salvos
        assert models.get_config("site_title") == "New Title"
        assert models.get_config("btc_address") == "bc1qnewtestaddress"
        assert models.get_config("goal_btc") == "5.0"

    def test_settings_requires_login(self, client):
        """Settings sem login deve redirecionar."""
        resp = client.get("/admin/settings")
        assert resp.status_code == 302


class TestAdminArticles:
    def test_articles_list_returns_200(self, admin_session):
        """Lista de artigos admin deve retornar 200."""
        resp = admin_session.get("/admin/articles")
        assert resp.status_code == 200

    def test_create_article(self, admin_session):
        """Criar artigo via admin deve funcionar."""
        with admin_session.session_transaction() as sess:
            csrf = sess.get("csrf_token", "")

        resp = admin_session.post("/admin/articles/new", data={
            "title": "Admin Created",
            "body_md": "Some **content**",
            "published": "on",
            "csrf_token": csrf,
        })
        assert resp.status_code == 302

        article = models.get_article_by_slug("admin-created")
        assert article is not None
        assert article["published"] == 1

    def test_create_article_empty_title(self, admin_session):
        """Titulo vazio deve ser rejeitado."""
        with admin_session.session_transaction() as sess:
            csrf = sess.get("csrf_token", "")

        resp = admin_session.post("/admin/articles/new", data={
            "title": "",
            "body_md": "Content",
            "csrf_token": csrf,
        }, follow_redirects=True)
        assert b"required" in resp.data.lower() or b"Title" in resp.data

    def test_edit_article(self, admin_session):
        """Editar artigo via admin deve atualizar dados."""
        slug = models.create_article("To Edit", "Old")
        article = models.get_article_by_slug(slug)

        with admin_session.session_transaction() as sess:
            csrf = sess.get("csrf_token", "")

        resp = admin_session.post(f"/admin/articles/{article['id']}/edit", data={
            "title": "Edited Title",
            "body_md": "New content",
            "published": "on",
            "csrf_token": csrf,
        })
        assert resp.status_code == 302

        updated = models.get_article_by_id(article["id"])
        assert updated["title"] == "Edited Title"

    def test_delete_article(self, admin_session):
        """Deletar artigo via admin deve funcionar."""
        slug = models.create_article("To Delete", "Bye")
        article = models.get_article_by_slug(slug)

        with admin_session.session_transaction() as sess:
            csrf = sess.get("csrf_token", "")

        resp = admin_session.post(f"/admin/articles/{article['id']}/delete", data={
            "csrf_token": csrf,
        })
        assert resp.status_code == 302
        assert models.get_article_by_id(article["id"]) is None

    def test_edit_nonexistent_article(self, admin_session):
        """Editar artigo inexistente deve retornar 404."""
        resp = admin_session.get("/admin/articles/99999/edit")
        assert resp.status_code == 404


class TestAdminMediaLinks:
    def test_media_links_returns_200(self, admin_session):
        """Pagina de media links deve retornar 200."""
        resp = admin_session.get("/admin/media-links")
        assert resp.status_code == 200

    def test_add_media_link(self, admin_session):
        """Adicionar media link deve funcionar."""
        with admin_session.session_transaction() as sess:
            csrf = sess.get("csrf_token", "")

        resp = admin_session.post("/admin/media-links", data={
            "title": "My Video",
            "url": "https://youtube.com/xyz",
            "link_type": "video",
            "csrf_token": csrf,
        })
        assert resp.status_code == 302

        links = models.get_media_links()
        assert len(links) == 1
        assert links[0]["title"] == "My Video"

    def test_add_media_link_empty_fields(self, admin_session):
        """Campos vazios devem ser rejeitados."""
        with admin_session.session_transaction() as sess:
            csrf = sess.get("csrf_token", "")

        resp = admin_session.post("/admin/media-links", data={
            "title": "",
            "url": "",
            "link_type": "article",
            "csrf_token": csrf,
        }, follow_redirects=True)
        assert b"required" in resp.data.lower()

    def test_delete_media_link(self, admin_session):
        """Deletar media link deve funcionar."""
        models.add_media_link("To Delete", "https://x.com", "tweet")
        links = models.get_media_links()

        with admin_session.session_transaction() as sess:
            csrf = sess.get("csrf_token", "")

        resp = admin_session.post(f"/admin/media-links/{links[0]['id']}/delete", data={
            "csrf_token": csrf,
        })
        assert resp.status_code == 302
        assert len(models.get_media_links()) == 0
