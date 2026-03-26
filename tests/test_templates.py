"""Testes que verificam se todos os templates renderizam sem erro."""
import models


class TestPublicTemplates:
    def test_index_renders(self, client):
        """Homepage renderiza sem erro de template."""
        resp = client.get("/")
        assert resp.status_code == 200
        # Deve conter elementos basicos do base.html
        assert b"</html>" in resp.data
        assert b"Pico" in resp.data or b"pico" in resp.data

    def test_donate_renders(self, client):
        """Pagina de doacao renderiza sem erro."""
        resp = client.get("/donate")
        assert resp.status_code == 200
        assert b"</html>" in resp.data

    def test_updates_renders(self, client):
        """Lista de updates renderiza sem erro."""
        resp = client.get("/updates")
        assert resp.status_code == 200
        assert b"</html>" in resp.data

    def test_article_renders(self, client):
        """Artigo individual renderiza sem erro."""
        slug = models.create_article("Test", "Content")
        resp = client.get(f"/updates/{slug}")
        assert resp.status_code == 200
        assert b"</html>" in resp.data

    def test_error_page_renders(self, client):
        """Pagina 404 renderiza sem erro."""
        resp = client.get("/nonexistent")
        assert resp.status_code == 404
        assert b"</html>" in resp.data

    def test_index_has_nav(self, client):
        """Homepage deve ter navegacao."""
        resp = client.get("/")
        assert b"<nav" in resp.data

    def test_index_has_footer(self, client):
        """Homepage deve ter footer."""
        resp = client.get("/")
        assert b"<footer" in resp.data

    def test_donate_has_qr_section(self, client):
        """Pagina de doacao deve ter secao de QR (mesmo sem enderecos configurados)."""
        resp = client.get("/donate")
        assert resp.status_code == 200

    def test_index_with_articles(self, client):
        """Homepage com artigos fixados deve mostrar titulos."""
        models.create_article("Pinned Story", "Important", pinned=1)
        resp = client.get("/")
        assert b"Pinned Story" in resp.data

    def test_index_with_media_links(self, client):
        """Homepage com media links deve mostrar links."""
        models.add_media_link("Watch This", "https://youtube.com/abc", "video")
        resp = client.get("/")
        assert b"Watch This" in resp.data

    def test_index_has_sticky_donate(self, client):
        """Homepage deve ter botao sticky de doacao (para mobile)."""
        resp = client.get("/")
        assert b"sticky-donate" in resp.data

    def test_index_has_open_graph(self, client):
        """Homepage deve ter meta tags Open Graph."""
        resp = client.get("/")
        assert b"og:title" in resp.data


class TestAdminTemplates:
    def test_login_renders(self, client):
        """Login renderiza sem erro."""
        resp = client.get("/admin/login")
        assert resp.status_code == 200
        assert b"<form" in resp.data
        assert b"csrf_token" in resp.data

    def test_dashboard_renders(self, admin_session):
        """Dashboard renderiza sem erro."""
        resp = admin_session.get("/admin/")
        assert resp.status_code == 200
        assert b"Dashboard" in resp.data or b"dashboard" in resp.data

    def test_settings_renders(self, admin_session):
        """Settings renderiza sem erro."""
        resp = admin_session.get("/admin/settings")
        assert resp.status_code == 200
        assert b"<form" in resp.data

    def test_articles_list_renders(self, admin_session):
        """Lista de artigos admin renderiza sem erro."""
        resp = admin_session.get("/admin/articles")
        assert resp.status_code == 200

    def test_article_form_new_renders(self, admin_session):
        """Formulario de novo artigo renderiza sem erro."""
        resp = admin_session.get("/admin/articles/new")
        assert resp.status_code == 200
        assert b"<form" in resp.data
        assert b"body_md" in resp.data

    def test_article_form_edit_renders(self, admin_session):
        """Formulario de editar artigo renderiza sem erro."""
        slug = models.create_article("For Edit", "Content")
        article = models.get_article_by_slug(slug)
        resp = admin_session.get(f"/admin/articles/{article['id']}/edit")
        assert resp.status_code == 200
        assert b"For Edit" in resp.data

    def test_media_links_renders(self, admin_session):
        """Pagina de media links renderiza sem erro."""
        resp = admin_session.get("/admin/media-links")
        assert resp.status_code == 200
        assert b"<form" in resp.data

    def test_change_password_renders(self, admin_session):
        """Pagina de troca de senha renderiza sem erro."""
        resp = admin_session.get("/admin/change-password")
        assert resp.status_code == 200
        assert b"<form" in resp.data

    def test_all_admin_forms_have_csrf(self, admin_session):
        """Todos os formularios admin devem ter campo csrf_token."""
        pages = [
            "/admin/settings",
            "/admin/articles/new",
            "/admin/media-links",
            "/admin/change-password",
        ]
        for page in pages:
            resp = admin_session.get(page)
            assert b"csrf_token" in resp.data, f"CSRF token missing in {page}"
