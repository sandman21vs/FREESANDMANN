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

    def test_invoice_widget_renders_shared_translations_on_index(self, client):
        """Homepage deve usar widget com data attrs + JS compartilhado."""
        models.set_config("coinos_enabled", "1")
        with client.session_transaction() as sess:
            sess["lang"] = "pt"

        resp = client.get("/")
        assert resp.status_code == 200
        assert b"/static/app.js" in resp.data
        assert "Gerar Invoice".encode() in resp.data
        assert "Valor personalizado em sats".encode() in resp.data
        assert "Aguardando pagamento...".encode() in resp.data
        assert b'data-create-url="/donate/create-invoice"' in resp.data
        assert b'data-copy-target=".invoice-bolt11"' in resp.data
        assert b"function createInvoice()" not in resp.data

    def test_invoice_widget_renders_shared_translations_on_donate(self, client):
        """Pagina de doacao deve renderizar o mesmo widget compartilhado."""
        models.set_config("coinos_enabled", "1")
        with client.session_transaction() as sess:
            sess["lang"] = "pt"

        resp = client.get("/donate")
        assert resp.status_code == 200
        assert b"/static/app.js" in resp.data
        assert "Escolha um valor e método de pagamento:".encode() in resp.data
        assert "Gerar Invoice".encode() in resp.data
        assert "Valor personalizado em sats".encode() in resp.data
        assert b'data-check-url-template="/donate/check-invoice/__HASH__"' in resp.data
        assert b"function createInvoice()" not in resp.data

    def test_qr_and_share_copy_buttons_use_data_targets(self, client):
        """Botoes de copiar devem usar data attrs e JS compartilhado."""
        models.set_config("btc_address", "bc1qexampleaddress123")

        resp = client.get("/")
        assert resp.status_code == 200
        assert b'data-copy-target="#btc-addr"' in resp.data
        assert b'data-copy-target="#share-url"' in resp.data
        assert b"function copyAddr(" not in resp.data

    def test_index_with_articles(self, client):
        """Homepage com artigos fixados deve mostrar titulos."""
        models.create_article("Pinned Story", "Important", pinned=1)
        with client.session_transaction() as sess:
            sess["lang"] = "pt"

        resp = client.get("/")
        assert b"Pinned Story" in resp.data
        assert "Leia mais".encode() in resp.data

    def test_index_with_articles_uses_translated_read_more_cta(self, client):
        """Homepage deve mostrar CTA traduzido para abrir o artigo."""
        models.create_article("Pinned Story", "Important", pinned=1)
        with client.session_transaction() as sess:
            sess["lang"] = "en"

        resp = client.get("/")
        assert resp.status_code == 200
        assert b"Read more" in resp.data

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

    def test_index_uses_translated_config_copy_for_selected_language(self, client):
        """Homepage deve usar os textos localizados do config com fallback por idioma."""
        models.set_config("site_title", "Titulo PT")
        models.set_config("site_description", "Descricao PT")
        models.set_config("site_tagline", "Slogan PT")
        models.set_config("deadline_text", "Prazo PT")
        models.set_config("transparency_text", "Texto PT")
        models.set_config("site_title_en", "English Title")
        models.set_config("site_description_en", "English Description")
        models.set_config("site_tagline_en", "English Tagline")
        models.set_config("deadline_text_en", "English Deadline")
        models.set_config("transparency_text_en", "English transparency")

        with client.session_transaction() as sess:
            sess["lang"] = "en"

        resp = client.get("/")
        assert resp.status_code == 200
        assert b"English Title" in resp.data
        assert b"English Description" in resp.data
        assert b"English Tagline" in resp.data
        assert b"English Deadline" in resp.data
        assert b"English transparency" in resp.data

    def test_index_falls_back_to_portuguese_when_translation_is_missing(self, client):
        """Quando EN/DE estiver vazio, o site deve cair no texto base."""
        models.set_config("site_title", "Titulo Base")
        models.set_config("site_title_de", "")

        with client.session_transaction() as sess:
            sess["lang"] = "de"

        resp = client.get("/")
        assert resp.status_code == 200
        assert "Titulo Base".encode() in resp.data

    def test_updates_with_articles_show_read_more_cta(self, client):
        """Lista publica de updates deve mostrar CTA explicito para abrir o artigo."""
        models.create_article("Public Update", "Body for excerpt")
        with client.session_transaction() as sess:
            sess["lang"] = "de"

        resp = client.get("/updates")
        assert resp.status_code == 200
        assert b"Public Update" in resp.data
        assert "Mehr lesen".encode() in resp.data


class TestAdminTemplates:
    def test_login_renders(self, client):
        """Login renderiza sem erro."""
        models.set_config("setup_complete", "1")
        resp = client.get("/admin/login")
        assert resp.status_code == 200
        assert b"<form" in resp.data
        assert b"csrf_token" in resp.data
        assert b"bo-sidebar" not in resp.data
        assert b"sticky-donate" in resp.data
        assert b"/advogado/login" in resp.data

    def test_setup_wizard_renders(self, client):
        """Wizard inicial deve renderizar no primeiro acesso."""
        resp = client.get("/admin/setup")
        assert resp.status_code == 200
        assert b"Initial Setup" in resp.data
        assert b"csrf_token" in resp.data

    def test_dashboard_renders(self, admin_session):
        """Dashboard renderiza sem erro."""
        resp = admin_session.get("/admin/")
        assert resp.status_code == 200
        assert b"Dashboard" in resp.data or b"dashboard" in resp.data
        assert b"bo-sidebar" in resp.data
        assert b"Pending Articles" in resp.data
        assert b"Getting Started" in resp.data

    def test_settings_renders(self, admin_session):
        """Settings renderiza sem erro."""
        resp = admin_session.get("/admin/settings")
        assert resp.status_code == 200
        assert b"<form" in resp.data
        assert b"bo-sidebar" in resp.data
        assert b"sticky-donate" not in resp.data
        assert b"bo-section-nav" in resp.data
        assert b'href="#section-general"' in resp.data
        assert b"bo-sticky-save" in resp.data
        assert b'name="site_title_en"' in resp.data
        assert b'name="transparency_text_de"' in resp.data

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
        assert b'name="publish_mode"' in resp.data
        assert b'name="pinned"' in resp.data

    def test_article_form_edit_renders(self, admin_session):
        """Formulario de editar artigo renderiza sem erro."""
        slug = models.create_article("For Edit", "Content")
        article = models.get_article_by_slug(slug)
        resp = admin_session.get(f"/admin/articles/{article['id']}/edit")
        assert resp.status_code == 200
        assert b"For Edit" in resp.data

    def test_lawyer_article_form_hides_admin_only_controls(self, lawyer_session):
        """Formulario do advogado nao deve expor publish_mode nem pinned."""
        resp = lawyer_session.get("/advogado/articles/new")
        assert resp.status_code == 200
        assert b"<form" in resp.data
        assert b'name="publish_mode"' not in resp.data
        assert b'name="pinned"' not in resp.data

    def test_lawyer_dashboard_renders_task_queue_layout(self, lawyer_session):
        """Dashboard do advogado deve usar o shell novo e separar fila de historico."""
        resp = lawyer_session.get("/advogado/")
        assert resp.status_code == 200
        assert b"bo-sidebar" in resp.data
        assert b"History" in resp.data
        assert b"Awaiting Review" in resp.data

    def test_media_links_renders(self, admin_session):
        """Pagina de media links renderiza sem erro."""
        resp = admin_session.get("/admin/media-links")
        assert resp.status_code == 200
        assert b"<form" in resp.data
        assert b"bo-sidebar" in resp.data
        assert b"Open Link" in resp.data or b"No media links yet" in resp.data

    def test_lawyers_page_uses_card_layout(self, admin_session):
        """Pagina de advogados deve renderizar no shell novo com cards."""
        resp = admin_session.get("/admin/lawyers")
        assert resp.status_code == 200
        assert b"bo-sidebar" in resp.data
        assert b"Create the first lawyer account" in resp.data or b"Reset Password" in resp.data

    def test_change_password_renders(self, admin_session):
        """Pagina de troca de senha renderiza sem erro."""
        resp = admin_session.get("/admin/change-password")
        assert resp.status_code == 200
        assert b"<form" in resp.data
        assert b"bo-sidebar" in resp.data

    def test_admin_flash_messages_render_as_toasts(self, admin_session):
        """Shell admin deve renderizar flashes dentro do container de toast."""
        with admin_session.session_transaction() as sess:
            csrf = sess.get("csrf_token", "")

        resp = admin_session.post("/admin/refresh-balance", data={
            "csrf_token": csrf,
        }, follow_redirects=True)

        assert resp.status_code == 200
        assert b"bo-toast-stack" in resp.data
        assert b"flash-dismiss" in resp.data

    def test_lawyer_change_password_uses_backoffice_shell(self, lawyer_session):
        """Troca de senha do advogado deve usar o shell autenticado."""
        resp = lawyer_session.get("/advogado/change-password")
        assert resp.status_code == 200
        assert b"<form" in resp.data
        assert b"bo-sidebar" in resp.data
        assert b"sticky-donate" not in resp.data

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
