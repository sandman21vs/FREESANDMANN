"""Testes do workflow de aprovacao do advogado — criacao de conta, login, artigos, aprovacao, restricoes."""
import models


class TestLawyerAccountCreation:
    def test_admin_can_create_lawyer(self, admin_session):
        """Admin cria conta de advogado com sucesso."""
        with admin_session.session_transaction() as sess:
            csrf = sess.get("csrf_token", "")

        resp = admin_session.post("/admin/lawyers", data={
            "username": "drsilva",
            "display_name": "Dr. Silva",
            "temp_password": "temppass123",
            "csrf_token": csrf,
        })
        assert resp.status_code == 302

        lawyer = models.get_lawyer_by_username("drsilva")
        assert lawyer is not None
        assert lawyer["display_name"] == "Dr. Silva"
        assert lawyer["force_password_change"] == 1
        assert lawyer["active"] == 1

    def test_duplicate_username_rejected(self, admin_session):
        """Username duplicado deve ser rejeitado."""
        models.create_lawyer("drsilva", "Dr. Silva", "temppass123")

        with admin_session.session_transaction() as sess:
            csrf = sess.get("csrf_token", "")

        resp = admin_session.post("/admin/lawyers", data={
            "username": "drsilva",
            "display_name": "Another Silva",
            "temp_password": "temppass123",
            "csrf_token": csrf,
        }, follow_redirects=True)
        assert b"already exists" in resp.data.lower()

    def test_lawyer_creation_requires_admin(self, client, csrf_token):
        """Criacao de advogado sem login admin deve redirecionar."""
        resp = client.post("/admin/lawyers", data={
            "username": "drsilva",
            "display_name": "Dr. Silva",
            "temp_password": "temppass123",
            "csrf_token": csrf_token,
        })
        assert resp.status_code == 302
        assert "login" in resp.headers.get("Location", "").lower()

    def test_admin_can_deactivate_lawyer(self, admin_session):
        """Admin desativa advogado."""
        lawyer_id = models.create_lawyer("drsilva", "Dr. Silva", "temppass123")

        with admin_session.session_transaction() as sess:
            csrf = sess.get("csrf_token", "")

        resp = admin_session.post(f"/admin/lawyers/{lawyer_id}/toggle", data={
            "csrf_token": csrf,
        })
        assert resp.status_code == 302

        lawyer = models.get_lawyer_by_id(lawyer_id)
        assert lawyer["active"] == 0

    def test_admin_can_activate_lawyer(self, admin_session):
        """Admin reativa advogado."""
        lawyer_id = models.create_lawyer("drsilva", "Dr. Silva", "temppass123")
        models.deactivate_lawyer(lawyer_id)

        with admin_session.session_transaction() as sess:
            csrf = sess.get("csrf_token", "")

        resp = admin_session.post(f"/admin/lawyers/{lawyer_id}/toggle", data={
            "csrf_token": csrf,
        })
        assert resp.status_code == 302

        lawyer = models.get_lawyer_by_id(lawyer_id)
        assert lawyer["active"] == 1

    def test_admin_can_reset_lawyer_password(self, admin_session):
        """Admin reseta senha do advogado."""
        lawyer_id = models.create_lawyer("drsilva", "Dr. Silva", "temppass123")
        models.change_lawyer_password(lawyer_id, "permanent123")

        with admin_session.session_transaction() as sess:
            csrf = sess.get("csrf_token", "")

        resp = admin_session.post(f"/admin/lawyers/{lawyer_id}/reset-password", data={
            "temp_password": "newtemp1234",
            "csrf_token": csrf,
        })
        assert resp.status_code == 302

        lawyer = models.get_lawyer_by_id(lawyer_id)
        assert lawyer["force_password_change"] == 1


class TestLawyerLogin:
    def test_lawyer_login_page_returns_200(self, client):
        """Pagina de login do advogado retorna 200."""
        resp = client.get("/advogado/login")
        assert resp.status_code == 200

    def test_lawyer_login_correct_credentials(self, client, csrf_token):
        """Login com credenciais corretas redireciona para troca de senha."""
        models.create_lawyer("drsilva", "Dr. Silva", "temppass123")

        resp = client.post("/advogado/login", data={
            "username": "drsilva",
            "password": "temppass123",
            "csrf_token": csrf_token,
        })
        assert resp.status_code == 302
        assert "change-password" in resp.headers.get("Location", "")

    def test_lawyer_login_wrong_password(self, client, csrf_token):
        """Senha errada mostra erro."""
        models.create_lawyer("drsilva", "Dr. Silva", "temppass123")

        resp = client.post("/advogado/login", data={
            "username": "drsilva",
            "password": "wrongpassword",
            "csrf_token": csrf_token,
        }, follow_redirects=True)
        assert b"Invalid" in resp.data

    def test_lawyer_login_inactive_account(self, client, csrf_token):
        """Conta desativada nao pode logar."""
        lawyer_id = models.create_lawyer("drsilva", "Dr. Silva", "temppass123")
        models.deactivate_lawyer(lawyer_id)

        resp = client.post("/advogado/login", data={
            "username": "drsilva",
            "password": "temppass123",
            "csrf_token": csrf_token,
        }, follow_redirects=True)
        assert b"Invalid" in resp.data

    def test_lawyer_rate_limiting(self, client, csrf_token):
        """Rate limiting funciona para advogado."""
        models.create_lawyer("drsilva", "Dr. Silva", "temppass123")

        for i in range(6):
            resp = client.post("/advogado/login", data={
                "username": "drsilva",
                "password": "wrong",
                "csrf_token": csrf_token,
            }, follow_redirects=True)
        assert b"Too many" in resp.data or b"rate" in resp.data.lower()

    def test_lawyer_session_does_not_grant_admin(self, lawyer_session):
        """Sessao de advogado nao concede acesso admin."""
        resp = lawyer_session.get("/admin/")
        assert resp.status_code == 302
        assert "admin" in resp.headers.get("Location", "").lower()


class TestLawyerForcePasswordChange:
    def test_force_change_on_first_login(self, client, csrf_token):
        """Primeiro login forca troca de senha."""
        models.create_lawyer("drsilva", "Dr. Silva", "temppass123")

        resp = client.post("/advogado/login", data={
            "username": "drsilva",
            "password": "temppass123",
            "csrf_token": csrf_token,
        })
        assert resp.status_code == 302
        assert "change-password" in resp.headers.get("Location", "")

    def test_lawyer_routes_redirect_when_force_change(self, client, csrf_token):
        """Com force_change ativo, rotas do advogado redirecionam para troca."""
        models.create_lawyer("drsilva", "Dr. Silva", "temppass123")

        client.post("/advogado/login", data={
            "username": "drsilva",
            "password": "temppass123",
            "csrf_token": csrf_token,
        })
        resp = client.get("/advogado/")
        assert resp.status_code == 302
        assert "change-password" in resp.headers.get("Location", "")

    def test_change_password_success(self, client, csrf_token):
        """Troca de senha com dados validos funciona."""
        models.create_lawyer("drsilva", "Dr. Silva", "temppass123")

        client.post("/advogado/login", data={
            "username": "drsilva",
            "password": "temppass123",
            "csrf_token": csrf_token,
        })
        resp = client.post("/advogado/change-password", data={
            "new_password": "newsecure123",
            "confirm_password": "newsecure123",
            "csrf_token": csrf_token,
        })
        assert resp.status_code == 302

        lawyer = models.get_lawyer_by_username("drsilva")
        assert lawyer["force_password_change"] == 0

    def test_change_password_too_short(self, client, csrf_token):
        """Senha curta rejeitada."""
        models.create_lawyer("drsilva", "Dr. Silva", "temppass123")

        client.post("/advogado/login", data={
            "username": "drsilva",
            "password": "temppass123",
            "csrf_token": csrf_token,
        })
        resp = client.post("/advogado/change-password", data={
            "new_password": "short",
            "confirm_password": "short",
            "csrf_token": csrf_token,
        }, follow_redirects=True)
        assert b"8 characters" in resp.data or b"least 8" in resp.data

    def test_change_password_mismatch(self, client, csrf_token):
        """Senhas diferentes rejeitadas."""
        models.create_lawyer("drsilva", "Dr. Silva", "temppass123")

        client.post("/advogado/login", data={
            "username": "drsilva",
            "password": "temppass123",
            "csrf_token": csrf_token,
        })
        resp = client.post("/advogado/change-password", data={
            "new_password": "newsecure123",
            "confirm_password": "different456",
            "csrf_token": csrf_token,
        }, follow_redirects=True)
        assert b"match" in resp.data.lower()


class TestLawyerArticleCreation:
    def test_lawyer_can_create_article(self, lawyer_session):
        """Advogado cria artigo com published=0 e approval_status=pending."""
        with lawyer_session.session_transaction() as sess:
            csrf = sess.get("csrf_token", "")

        resp = lawyer_session.post("/advogado/articles/new", data={
            "title": "Lawyer Article",
            "body_md": "Legal content here",
            "csrf_token": csrf,
        })
        assert resp.status_code == 302

        article = models.get_article_by_slug("lawyer-article")
        assert article is not None
        assert article["published"] == 0
        assert article["approval_status"] == "pending"
        assert article["created_by"] == "lawyer"

    def test_lawyer_article_not_publicly_visible(self, lawyer_session, client):
        """Artigo do advogado nao aparece publicamente."""
        with lawyer_session.session_transaction() as sess:
            csrf = sess.get("csrf_token", "")

        lawyer_session.post("/advogado/articles/new", data={
            "title": "Hidden Article",
            "body_md": "Should not be public",
            "csrf_token": csrf,
        })

        resp = client.get("/updates")
        assert b"Hidden Article" not in resp.data

    def test_lawyer_can_edit_article(self, lawyer_session):
        """Advogado edita artigo."""
        slug = models.create_article("Original", "Original body", 0, 0, created_by="lawyer", approval_status="pending")
        article = models.get_article_by_slug(slug)

        with lawyer_session.session_transaction() as sess:
            csrf = sess.get("csrf_token", "")

        resp = lawyer_session.post(f"/advogado/articles/{article['id']}/edit", data={
            "title": "Edited By Lawyer",
            "body_md": "New content",
            "csrf_token": csrf,
        })
        assert resp.status_code == 302

        updated = models.get_article_by_id(article["id"])
        assert updated["title"] == "Edited By Lawyer"
        assert updated["published"] == 0

    def test_lawyer_edit_preserves_existing_pinned_flag(self, lawyer_session):
        """Edicao por advogado preserva pinned existente."""
        slug = models.create_article("Pinned Original", "Original body", 0, 1, created_by="lawyer", approval_status="pending")
        article = models.get_article_by_slug(slug)

        with lawyer_session.session_transaction() as sess:
            csrf = sess.get("csrf_token", "")

        resp = lawyer_session.post(f"/advogado/articles/{article['id']}/edit", data={
            "title": "Pinned Original Edited",
            "body_md": "Updated body",
            "csrf_token": csrf,
        })
        assert resp.status_code == 302

        updated = models.get_article_by_id(article["id"])
        assert updated["pinned"] == 1

    def test_lawyer_cannot_set_published(self, lawyer_session):
        """Mesmo com published no form, advogado nao publica."""
        with lawyer_session.session_transaction() as sess:
            csrf = sess.get("csrf_token", "")

        lawyer_session.post("/advogado/articles/new", data={
            "title": "Try Publish",
            "body_md": "Trying to publish",
            "published": "on",
            "csrf_token": csrf,
        })

        article = models.get_article_by_slug("try-publish")
        assert article["published"] == 0


class TestAdminApproval:
    def test_admin_can_approve_article(self, admin_session):
        """Admin aprova artigo."""
        slug = models.create_article("Pending Article", "Content", 0, 0, approval_status="pending")
        article = models.get_article_by_slug(slug)

        with admin_session.session_transaction() as sess:
            csrf = sess.get("csrf_token", "")

        resp = admin_session.post(f"/admin/articles/{article['id']}/approve", data={
            "csrf_token": csrf,
        })
        assert resp.status_code == 302

        approvals = models.get_article_approvals(article["id"])
        assert len(approvals) == 1
        assert approvals[0]["role"] == "admin"

    def test_admin_can_publish_with_both_approvals(self, admin_session):
        """Apos ambos aprovarem, admin publica."""
        slug = models.create_article("Both Approve", "Content", 0, 0, approval_status="pending")
        article = models.get_article_by_slug(slug)

        models.approve_article(article["id"], "Dr. Silva", "lawyer")
        models.approve_article(article["id"], "Admin", "admin")

        with admin_session.session_transaction() as sess:
            csrf = sess.get("csrf_token", "")

        resp = admin_session.post(f"/admin/articles/{article['id']}/publish", data={
            "csrf_token": csrf,
        })
        assert resp.status_code == 302

        updated = models.get_article_by_id(article["id"])
        assert updated["published"] == 1
        assert updated["approval_status"] == "published"
        assert "Admin" in updated["approved_by_display"]

    def test_admin_override_publish_without_lawyer(self, admin_session):
        """Admin publica sozinho (override)."""
        slug = models.create_article("Override Article", "Content", 0, 0, approval_status="pending")
        article = models.get_article_by_slug(slug)

        with admin_session.session_transaction() as sess:
            csrf = sess.get("csrf_token", "")

        resp = admin_session.post(f"/admin/articles/{article['id']}/publish", data={
            "csrf_token": csrf,
        })
        assert resp.status_code == 302

        updated = models.get_article_by_id(article["id"])
        assert updated["published"] == 1
        assert updated["approval_status"] == "published"


class TestLawyerApproval:
    def test_lawyer_can_approve_article(self, lawyer_session):
        """Advogado aprova artigo."""
        slug = models.create_article("Pending", "Content", 0, 0, approval_status="pending")
        article = models.get_article_by_slug(slug)

        with lawyer_session.session_transaction() as sess:
            csrf = sess.get("csrf_token", "")

        resp = lawyer_session.post(f"/advogado/articles/{article['id']}/approve", data={
            "csrf_token": csrf,
        })
        assert resp.status_code == 302

        approvals = models.get_article_approvals(article["id"])
        assert len(approvals) == 1
        assert approvals[0]["role"] == "lawyer"
        assert approvals[0]["approved_by"] == "Dr. Silva"

    def test_lawyer_cannot_publish_alone(self, lawyer_session):
        """Aprovacao do advogado NAO publica o artigo."""
        slug = models.create_article("No Publish", "Content", 0, 0, approval_status="pending")
        article = models.get_article_by_slug(slug)

        with lawyer_session.session_transaction() as sess:
            csrf = sess.get("csrf_token", "")

        lawyer_session.post(f"/advogado/articles/{article['id']}/approve", data={
            "csrf_token": csrf,
        })

        updated = models.get_article_by_id(article["id"])
        assert updated["published"] == 0

    def test_lawyer_can_revoke_approval(self, lawyer_session):
        """Advogado revoga aprovacao."""
        slug = models.create_article("Revoke Me", "Content", 0, 0, approval_status="pending")
        article = models.get_article_by_slug(slug)
        models.approve_article(article["id"], "Dr. Silva", "lawyer")

        with lawyer_session.session_transaction() as sess:
            csrf = sess.get("csrf_token", "")

        resp = lawyer_session.post(f"/advogado/articles/{article['id']}/revoke", data={
            "csrf_token": csrf,
        })
        assert resp.status_code == 302

        approvals = models.get_article_approvals(article["id"])
        assert len(approvals) == 0


class TestApprovalWorkflow:
    def test_full_workflow_lawyer_creates_both_approve(self, lawyer_session, admin_session):
        """Fluxo completo: advogado cria -> ambos aprovam -> admin publica -> visivel."""
        # Advogado cria artigo
        with lawyer_session.session_transaction() as sess:
            csrf = sess.get("csrf_token", "")

        lawyer_session.post("/advogado/articles/new", data={
            "title": "Full Workflow",
            "body_md": "Important legal update",
            "csrf_token": csrf,
        })

        article = models.get_article_by_slug("full-workflow")
        assert article["published"] == 0
        assert article["approval_status"] == "pending"

        # Advogado aprova
        lawyer_session.post(f"/advogado/articles/{article['id']}/approve", data={
            "csrf_token": csrf,
        })

        # Admin aprova
        with admin_session.session_transaction() as sess:
            csrf_admin = sess.get("csrf_token", "")

        admin_session.post(f"/admin/articles/{article['id']}/approve", data={
            "csrf_token": csrf_admin,
        })

        updated = models.get_article_by_id(article["id"])
        assert updated["approval_status"] == "approved"

        # Admin publica
        admin_session.post(f"/admin/articles/{article['id']}/publish", data={
            "csrf_token": csrf_admin,
        })

        updated = models.get_article_by_id(article["id"])
        assert updated["published"] == 1
        assert updated["approval_status"] == "published"
        assert "Dr. Silva" in updated["approved_by_display"]
        assert "Admin" in updated["approved_by_display"]

    def test_admin_creates_for_review_lawyer_approves(self, admin_session):
        """Admin cria para revisao -> advogado aprova -> admin publica."""
        with admin_session.session_transaction() as sess:
            csrf = sess.get("csrf_token", "")

        admin_session.post("/admin/articles/new", data={
            "title": "Admin Review Article",
            "body_md": "Admin wrote this",
            "publish_mode": "review",
            "csrf_token": csrf,
        })

        article = models.get_article_by_slug("admin-review-article")
        assert article["published"] == 0
        assert article["approval_status"] == "pending"

    def test_admin_override_workflow(self, admin_session):
        """Admin cria e publica direto (override)."""
        with admin_session.session_transaction() as sess:
            csrf = sess.get("csrf_token", "")

        admin_session.post("/admin/articles/new", data={
            "title": "Override Direct",
            "body_md": "Published immediately",
            "publish_mode": "override",
            "csrf_token": csrf,
        })

        article = models.get_article_by_slug("override-direct")
        assert article["published"] == 1
        assert article["approval_status"] == "published"
        assert "Admin" in article["approved_by_display"]

    def test_edit_clears_approvals(self, admin_session):
        """Edicao limpa aprovacoes existentes."""
        slug = models.create_article("Clear Test", "Original", 0, 0, approval_status="pending")
        article = models.get_article_by_slug(slug)
        models.approve_article(article["id"], "Dr. Silva", "lawyer")
        models.approve_article(article["id"], "Admin", "admin")

        approvals_before = models.get_article_approvals(article["id"])
        assert len(approvals_before) == 2

        with admin_session.session_transaction() as sess:
            csrf = sess.get("csrf_token", "")

        admin_session.post(f"/admin/articles/{article['id']}/edit", data={
            "title": "Clear Test Edited",
            "body_md": "Changed content",
            "publish_mode": "review",
            "csrf_token": csrf,
        })

        approvals_after = models.get_article_approvals(article["id"])
        assert len(approvals_after) == 0

        updated = models.get_article_by_id(article["id"])
        assert updated["approval_status"] == "pending"

    def test_unpublish_resets_status(self, admin_session):
        """Unpublish reseta status."""
        slug = models.create_article("Unpub Test", "Content", 1, 0, approval_status="published")
        article = models.get_article_by_slug(slug)

        with admin_session.session_transaction() as sess:
            csrf = sess.get("csrf_token", "")

        admin_session.post(f"/admin/articles/{article['id']}/unpublish", data={
            "csrf_token": csrf,
        })

        updated = models.get_article_by_id(article["id"])
        assert updated["published"] == 0
        assert updated["approval_status"] == "pending"


class TestLawyerAccessRestrictions:
    def test_lawyer_cannot_access_admin_settings(self, lawyer_session):
        """Advogado nao acessa settings admin."""
        resp = lawyer_session.get("/admin/settings")
        assert resp.status_code == 302
        assert "admin" in resp.headers.get("Location", "").lower()

    def test_lawyer_cannot_access_admin_dashboard(self, lawyer_session):
        """Advogado nao acessa dashboard admin."""
        resp = lawyer_session.get("/admin/")
        assert resp.status_code == 302

    def test_lawyer_cannot_refresh_balance(self, lawyer_session):
        """Advogado nao pode atualizar saldo."""
        with lawyer_session.session_transaction() as sess:
            csrf = sess.get("csrf_token", "")

        resp = lawyer_session.post("/admin/refresh-balance", data={
            "csrf_token": csrf,
        })
        assert resp.status_code == 302

    def test_lawyer_cannot_manage_media_links(self, lawyer_session):
        """Advogado nao acessa media links."""
        resp = lawyer_session.get("/admin/media-links")
        assert resp.status_code == 302

    def test_lawyer_cannot_delete_articles(self, lawyer_session):
        """Advogado nao tem rota de delete."""
        slug = models.create_article("No Delete", "Content", 0, 0)
        article = models.get_article_by_slug(slug)

        with lawyer_session.session_transaction() as sess:
            csrf = sess.get("csrf_token", "")

        resp = lawyer_session.post(f"/admin/articles/{article['id']}/delete", data={
            "csrf_token": csrf,
        })
        assert resp.status_code == 302
        # Article should still exist
        assert models.get_article_by_id(article["id"]) is not None

    def test_admin_cannot_access_lawyer_dashboard_without_lawyer_session(self, admin_session):
        """Admin sem sessao de advogado nao acessa /advogado/."""
        resp = admin_session.get("/advogado/")
        assert resp.status_code == 302
        assert "advogado" in resp.headers.get("Location", "").lower()


class TestPublicApprovalDisplay:
    def test_published_article_shows_approval_info(self, client):
        """Artigo publicado mostra quem aprovou."""
        slug = models.create_article("Approved Article", "Legal content", 1, 0, approval_status="published")
        article = models.get_article_by_slug(slug)
        models.approve_article(article["id"], "Dr. Silva", "lawyer")
        models.publish_article_with_approval(article["id"], "Admin")

        resp = client.get(f"/updates/{slug}")
        assert resp.status_code == 200
        assert b"Dr. Silva" in resp.data
        assert b"Admin" in resp.data

    def test_article_without_approval_display_renders_cleanly(self, client):
        """Artigo antigo sem dados de aprovacao renderiza normalmente."""
        slug = models.create_article("Old Article", "Old content", 1, 0)

        resp = client.get(f"/updates/{slug}")
        assert resp.status_code == 200
        assert b"Old Article" in resp.data

    def test_admin_override_shows_admin_only(self, client):
        """Override mostra so Admin."""
        slug = models.create_article("Override Only", "Override content", 0, 0, approval_status="pending")
        article = models.get_article_by_slug(slug)
        models.publish_article_with_approval(article["id"], "Admin")

        resp = client.get(f"/updates/{slug}")
        assert resp.status_code == 200
        assert b"Admin" in resp.data
