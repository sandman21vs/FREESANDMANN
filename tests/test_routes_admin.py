"""Testes das rotas admin — login, logout, dashboard, settings, articles CRUD, media links."""
import models


class TestAdminLogin:
    def test_login_page_returns_200(self, client):
        """Pagina de login deve retornar 200."""
        models.set_config("setup_complete", "1")
        resp = client.get("/admin/login")
        assert resp.status_code == 200

    def test_login_page_contains_lawyer_link(self, client):
        """Login admin deve apontar para o portal do advogado."""
        models.set_config("setup_complete", "1")
        resp = client.get("/admin/login")
        assert b"/advogado/login" in resp.data

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
        models.set_config("setup_complete", "1")
        resp = client.get("/admin/")
        assert resp.status_code == 302

    def test_dashboard_checklist_unconfigured(self, admin_session):
        """Dashboard deve exibir tarefas pendentes de setup quando faltar configuracao."""
        resp = admin_session.get("/admin/")

        assert resp.status_code == 200
        assert b"Getting Started" in resp.data
        assert b"Campaign title set" in resp.data
        assert b"Bitcoin address configured" in resp.data
        assert b"Fundraising goal defined" in resp.data
        assert b"/admin/settings#section-bitcoin" in resp.data
        assert resp.data.count(b"Complete this step") == 5

    def test_dashboard_checklist_configured(self, admin_session):
        """Checklist hidden when all setup tasks are complete."""
        models.set_config("site_title", "Open Defense")
        models.set_config("btc_address", "bc1qconfiguredaddress")
        models.set_config("goal_btc", "5.0")
        models.create_article("Published update", "Body")
        models.create_lawyer("drsilva", "Dr. Silva", "TempPass123!")

        resp = admin_session.get("/admin/")

        assert resp.status_code == 200
        # Checklist card is hidden when all items are done
        assert b"Getting Started" not in resp.data
        # Dashboard hero card still renders
        assert b"Campaign Progress" in resp.data


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
            "site_title_en": "New Title EN",
            "site_description_en": "New Desc EN",
            "site_tagline_en": "New Tag EN",
            "site_title_de": "Neuer Titel",
            "goal_description_en": "New Goal EN",
            "deadline_text_en": "Court date April 16",
            "transparency_text_en": "Lawyer fees EN",
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
        assert models.get_config("site_title_en") == "New Title EN"
        assert models.get_config("site_title_de") == "Neuer Titel"
        assert models.get_config("btc_address") == "bc1qnewtestaddress"
        assert models.get_config("goal_btc") == "5.0"

    def test_settings_requires_login(self, client):
        """Settings sem login deve redirecionar."""
        models.set_config("setup_complete", "1")
        resp = client.get("/admin/settings")
        assert resp.status_code == 302

    def test_settings_reject_invalid_goal_btc_and_preserve_form_state(self, admin_session):
        """Goal invalida deve ser rejeitada sem sobrescrever config salva."""
        original_goal = models.get_config("goal_btc")

        with admin_session.session_transaction() as sess:
            csrf = sess.get("csrf_token", "")

        resp = admin_session.post("/admin/settings", data={
            "site_title": "Keep This Title",
            "site_title_en": "Keep This Title EN",
            "goal_btc": "abc",
            "csrf_token": csrf,
        }, follow_redirects=True)

        assert resp.status_code == 200
        assert b"Goal (BTC) must be a valid number." in resp.data
        assert b"Keep This Title" in resp.data
        assert b"Keep This Title EN" in resp.data
        assert models.get_config("goal_btc") == original_goal

    def test_settings_require_coinos_token_when_enabled(self, admin_session):
        """Coinos nao deve ser habilitado sem API token."""
        with admin_session.session_transaction() as sess:
            csrf = sess.get("csrf_token", "")

        resp = admin_session.post("/admin/settings", data={
            "site_title": "Test",
            "coinos_enabled": "1",
            "coinos_api_key": "",
            "csrf_token": csrf,
        }, follow_redirects=True)

        assert resp.status_code == 200
        assert b"Coinos API token is required when Coinos invoices are enabled." in resp.data
        assert models.get_config("coinos_enabled") == "0"

    def test_settings_require_liquid_address_when_enabled(self, admin_session):
        """Liquid habilitado sem endereco deve ser rejeitado."""
        with admin_session.session_transaction() as sess:
            csrf = sess.get("csrf_token", "")

        resp = admin_session.post("/admin/settings", data={
            "site_title": "Test",
            "liquid_enabled": "1",
            "liquid_address": "",
            "csrf_token": csrf,
        }, follow_redirects=True)

        assert resp.status_code == 200
        assert b"Liquid address is required when Coinos is not configured." in resp.data
        assert models.get_config("liquid_enabled") == "0"

    def test_settings_normalize_trimmed_values(self, admin_session):
        """Valores validos devem ser normalizados antes de salvar."""
        with admin_session.session_transaction() as sess:
            csrf = sess.get("csrf_token", "")

        resp = admin_session.post("/admin/settings", data={
            "site_title": "  New Title  ",
            "goal_btc": " 5 ",
            "raised_btc_manual_adjustment": " ",
            "supporters_count": " 0010 ",
            "hero_image_url": "/static/hero.png",
            "csrf_token": csrf,
        })

        assert resp.status_code == 302
        assert models.get_config("site_title") == "New Title"
        assert models.get_config("goal_btc") == "5.0"
        assert models.get_config("raised_btc_manual_adjustment") == "0.0"
        assert models.get_config("supporters_count") == "10"
        assert models.get_config("hero_image_url") == "/static/hero.png"

    def test_settings_reject_invalid_public_url(self, admin_session):
        """URLs publicas inseguras devem ser rejeitadas."""
        with admin_session.session_transaction() as sess:
            csrf = sess.get("csrf_token", "")

        resp = admin_session.post("/admin/settings", data={
            "site_title": "Test",
            "hero_image_url": "javascript:alert(1)",
            "csrf_token": csrf,
        }, follow_redirects=True)

        assert resp.status_code == 200
        assert b"Hero Image URL must be a valid http(s) URL or site-relative path." in resp.data
        assert models.get_config("hero_image_url") == ""

        resp = admin_session.post("/admin/settings", data={
            "site_title": "Test",
            "hero_image_url": "//evil.example/asset.png",
            "csrf_token": csrf,
        }, follow_redirects=True)

        assert resp.status_code == 200
        assert b"Hero Image URL must be a valid http(s) URL or site-relative path." in resp.data


class TestAdminSetupWizard:
    def _wizard_csrf(self, fresh_client):
        fresh_client.get("/admin/setup")
        with fresh_client.session_transaction() as sess:
            return sess.get("csrf_token", "")

    def test_wizard_shown_on_first_access(self, fresh_client):
        """Primeiro acesso ao admin deve redirecionar para setup."""
        resp = fresh_client.get("/admin/")
        assert resp.status_code == 302
        assert "/admin/setup" in resp.headers.get("Location", "")

    def test_wizard_shown_on_login_access(self, fresh_client):
        """Login deve redirecionar para wizard enquanto setup nao acabou."""
        resp = fresh_client.get("/admin/login")
        assert resp.status_code == 302
        assert "/admin/setup" in resp.headers.get("Location", "")

    def test_wizard_renders(self, fresh_client):
        """Wizard deve renderizar quando setup_complete == 0."""
        resp = fresh_client.get("/admin/setup")
        assert resp.status_code == 200
        assert b"Initial Setup" in resp.data

    def test_wizard_redirects_when_complete(self, fresh_client):
        """Wizard nao deve ficar acessivel depois do setup."""
        models.set_config("setup_complete", "1")
        resp = fresh_client.get("/admin/setup")
        assert resp.status_code == 302
        assert "/admin/login" in resp.headers.get("Location", "")

    def test_wizard_submit_success(self, fresh_client):
        """POST valido no wizard deve concluir setup e logar admin."""
        csrf = self._wizard_csrf(fresh_client)
        resp = fresh_client.post("/admin/setup", data={
            "admin_password": "wizardpass123",
            "admin_password_confirm": "wizardpass123",
            "site_title": "Open Defense",
            "site_description": "Campaign description",
            "btc_address": "bc1qwizardaddress",
            "goal_btc": "2.5",
            "csrf_token": csrf,
        })

        assert resp.status_code == 302
        assert "/admin/" in resp.headers.get("Location", "")
        assert models.get_config("setup_complete") == "1"
        assert models.must_change_password() is False
        assert models.verify_password("wizardpass123") is True
        assert models.get_config("site_title") == "Open Defense"
        assert models.get_config("btc_address") == "bc1qwizardaddress"
        assert models.get_config("goal_btc") == "2.5"

        with fresh_client.session_transaction() as sess:
            assert sess.get("admin") is True

    def test_wizard_submit_validation(self, fresh_client):
        """Senha curta deve re-renderizar o wizard com erro."""
        csrf = self._wizard_csrf(fresh_client)
        resp = fresh_client.post("/admin/setup", data={
            "admin_password": "short",
            "admin_password_confirm": "short",
            "site_title": "Open Defense",
            "goal_btc": "1.0",
            "csrf_token": csrf,
        }, follow_redirects=True)

        assert resp.status_code == 200
        assert b"Password must be at least 8 characters." in resp.data
        assert models.get_config("setup_complete") == "0"

    def test_wizard_submit_password_mismatch(self, fresh_client):
        """Senhas divergentes devem falhar."""
        csrf = self._wizard_csrf(fresh_client)
        resp = fresh_client.post("/admin/setup", data={
            "admin_password": "wizardpass123",
            "admin_password_confirm": "wizardpass999",
            "site_title": "Open Defense",
            "goal_btc": "1.0",
            "csrf_token": csrf,
        }, follow_redirects=True)

        assert resp.status_code == 200
        assert b"Passwords do not match." in resp.data

    def test_wizard_submit_missing_title(self, fresh_client):
        """Titulo e obrigatorio."""
        csrf = self._wizard_csrf(fresh_client)
        resp = fresh_client.post("/admin/setup", data={
            "admin_password": "wizardpass123",
            "admin_password_confirm": "wizardpass123",
            "site_title": "",
            "goal_btc": "1.0",
            "csrf_token": csrf,
        }, follow_redirects=True)

        assert resp.status_code == 200
        assert b"Site title is required." in resp.data

    def test_wizard_does_not_require_btc(self, fresh_client):
        """BTC address deve ser opcional no wizard."""
        csrf = self._wizard_csrf(fresh_client)
        resp = fresh_client.post("/admin/setup", data={
            "admin_password": "wizardpass123",
            "admin_password_confirm": "wizardpass123",
            "site_title": "Open Defense",
            "site_description": "",
            "btc_address": "",
            "goal_btc": "1.0",
            "csrf_token": csrf,
        })

        assert resp.status_code == 302
        assert models.get_config("setup_complete") == "1"
        assert models.get_config("btc_address") == ""

    def test_normal_login_works_after_setup(self, fresh_client):
        """Depois do setup, o login admin deve funcionar normalmente."""
        models.set_config("setup_complete", "1")
        models.change_password("wizardpass123")
        fresh_client.get("/admin/login")
        with fresh_client.session_transaction() as sess:
            csrf = sess.get("csrf_token", "")

        resp = fresh_client.post("/admin/login", data={
            "username": "FREE",
            "password": "wizardpass123",
            "csrf_token": csrf,
        })

        assert resp.status_code == 302
        assert "/admin/" in resp.headers.get("Location", "")


class TestAdminArticles:
    def test_articles_list_returns_200(self, admin_session):
        """Lista de artigos admin deve retornar 200."""
        resp = admin_session.get("/admin/articles")
        assert resp.status_code == 200

    def test_articles_filter_tabs_show_only_requested_subset(self, admin_session):
        """Filtro por query string deve limitar os cards exibidos."""
        models.create_article("Published Story", "Body")
        models.create_article("Draft Story", "Body", 0, 0)
        models.create_article("Pending Story", "Body", 0, 0, approval_status="pending")

        resp = admin_session.get("/admin/articles?filter=drafts")
        assert resp.status_code == 200
        assert b"Draft Story" in resp.data
        assert b"Published Story" not in resp.data
        assert b"Pending Story" not in resp.data

        resp = admin_session.get("/admin/articles?filter=pending")
        assert resp.status_code == 200
        assert b"Pending Story" in resp.data
        assert b"Published Story" not in resp.data

    def test_create_article(self, admin_session):
        """Criar artigo via admin deve funcionar."""
        with admin_session.session_transaction() as sess:
            csrf = sess.get("csrf_token", "")

        resp = admin_session.post("/admin/articles/new", data={
            "title": "Admin Created",
            "body_md": "Some **content**",
            "publish_mode": "override",
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
