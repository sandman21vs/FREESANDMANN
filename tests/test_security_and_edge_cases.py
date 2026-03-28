"""Security and edge-case tests identified during Phase 2 review.

These tests cover gaps found in the existing suite:
1. XSS in markdown rendering (CRITICAL)
2. data: URI bypass in URL validation (SECURITY)
3. Webhook behavior without secret (SECURITY)
4. Lawyer editing admin-created articles (BUSINESS LOGIC)
5. Lawyer self-approval (BUSINESS LOGIC)
6. Checklist goal_btc boundary (UX)
7. Setup wizard edge cases (VALIDATION)
8. Draft article public access (SECURITY)
9. Health endpoint with DB verification (ROBUSTNESS)
"""

import models
from model_content import render_markdown


# ---------------------------------------------------------------------------
# 1. XSS in markdown rendering
# ---------------------------------------------------------------------------

class TestMarkdownXSS:
    """render_markdown() must not allow script injection.

    The markdown lib with extension 'extra' passes raw HTML through by
    default.  If these tests FAIL, the fix is to add HTML sanitization
    (e.g. bleach, nh3, or markdown extension 'mdx_bleach') to
    render_markdown() in model_content.py.
    """

    def test_script_tag_stripped(self, temp_database):
        """<script> tags must not appear in rendered output."""
        html = render_markdown('<script>alert("xss")</script>')
        assert "<script>" not in html.lower()

    def test_img_onerror_stripped(self, temp_database):
        """<img onerror=...> must be sanitized."""
        html = render_markdown('<img onerror="alert(1)" src=x>')
        assert "onerror" not in html.lower()

    def test_javascript_uri_in_link_stripped(self, temp_database):
        """[text](javascript:...) links must not produce javascript: hrefs."""
        html = render_markdown('[click](javascript:alert(1))')
        assert "javascript:" not in html.lower()

    def test_iframe_injection_stripped(self, temp_database):
        """Raw <iframe> tags must not pass through."""
        html = render_markdown('<iframe src="https://evil.example"></iframe>')
        assert "<iframe" not in html.lower()

    def test_event_handler_attributes_stripped(self, temp_database):
        """HTML event handlers (onload, onclick, etc.) must be removed."""
        html = render_markdown('<div onload="alert(1)">test</div>')
        assert "onload" not in html.lower()

    def test_svg_onload_stripped(self, temp_database):
        """<svg onload=...> must be sanitized."""
        html = render_markdown('<svg onload="alert(1)"></svg>')
        assert "onload" not in html.lower()

    def test_safe_markdown_preserved(self, temp_database):
        """Normal markdown (bold, links, lists) must still render correctly."""
        html = render_markdown("**bold** and [link](https://example.com)")
        assert "<strong>bold</strong>" in html
        assert 'href="https://example.com"' in html


# ---------------------------------------------------------------------------
# 2. data: URI bypass in URL validation
# ---------------------------------------------------------------------------

class TestURLValidation:
    """Admin settings URL fields must reject data: URIs."""

    def test_data_uri_rejected_hero_image(self, admin_session):
        """data: URI in hero_image_url must be rejected."""
        with admin_session.session_transaction() as sess:
            csrf = sess.get("csrf_token", "")

        resp = admin_session.post("/admin/settings", data={
            "site_title": "Test",
            "hero_image_url": "data:text/html,<script>alert(1)</script>",
            "csrf_token": csrf,
        }, follow_redirects=True)

        assert resp.status_code == 200
        assert b"must be a valid http(s) URL" in resp.data
        assert models.get_config("hero_image_url") == ""

    def test_data_uri_rejected_og_image(self, admin_session):
        """data: URI in og_image_url must be rejected."""
        with admin_session.session_transaction() as sess:
            csrf = sess.get("csrf_token", "")

        resp = admin_session.post("/admin/settings", data={
            "site_title": "Test",
            "og_image_url": "data:image/svg+xml,<svg onload=alert(1)>",
            "csrf_token": csrf,
        }, follow_redirects=True)

        assert resp.status_code == 200
        assert b"must be a valid http(s) URL" in resp.data
        assert models.get_config("og_image_url") == ""

    def test_valid_https_url_accepted(self, admin_session):
        """Normal https URL must still be accepted."""
        with admin_session.session_transaction() as sess:
            csrf = sess.get("csrf_token", "")

        resp = admin_session.post("/admin/settings", data={
            "site_title": "Test",
            "hero_image_url": "https://example.com/image.png",
            "csrf_token": csrf,
        })

        assert resp.status_code == 302
        assert models.get_config("hero_image_url") == "https://example.com/image.png"

    def test_relative_path_accepted(self, admin_session):
        """Site-relative paths like /static/img.png must be accepted."""
        with admin_session.session_transaction() as sess:
            csrf = sess.get("csrf_token", "")

        resp = admin_session.post("/admin/settings", data={
            "site_title": "Test",
            "hero_image_url": "/static/hero.png",
            "csrf_token": csrf,
        })

        assert resp.status_code == 302
        assert models.get_config("hero_image_url") == "/static/hero.png"


# ---------------------------------------------------------------------------
# 3. Webhook without secret
# ---------------------------------------------------------------------------

class TestWebhookSecurity:
    """Coinos webhook behavior when secret is empty vs configured."""

    def test_webhook_without_secret_triggers_balance_check(self, client, temp_database):
        """With empty webhook_secret, webhook should still process (no HMAC)."""
        models.set_config("coinos_enabled", "1")
        models.set_config("coinos_api_key", "fake-token")
        models.set_config("coinos_webhook_secret", "")

        resp = client.post("/donate/webhook/coinos",
                           json={"received": 50000},
                           content_type="application/json")
        # Should accept (no secret to check)
        assert resp.status_code == 200

    def test_webhook_with_wrong_secret_rejected(self, client, temp_database):
        """With webhook_secret configured, wrong secret must return 403."""
        models.set_config("coinos_enabled", "1")
        models.set_config("coinos_api_key", "fake-token")
        models.set_config("coinos_webhook_secret", "correct-secret")

        resp = client.post("/donate/webhook/coinos",
                           json={"received": 50000, "secret": "wrong-secret"},
                           content_type="application/json")
        assert resp.status_code == 403

    def test_webhook_with_correct_secret_accepted(self, client, temp_database):
        """With webhook_secret configured, correct secret must be accepted."""
        models.set_config("coinos_enabled", "1")
        models.set_config("coinos_api_key", "fake-token")
        models.set_config("coinos_webhook_secret", "correct-secret")

        resp = client.post("/donate/webhook/coinos",
                           json={"received": 50000, "secret": "correct-secret"},
                           content_type="application/json")
        assert resp.status_code == 200

    def test_webhook_negative_amount_rejected(self, client, temp_database):
        """Negative received amount must be rejected."""
        models.set_config("coinos_enabled", "1")
        models.set_config("coinos_api_key", "fake-token")
        models.set_config("coinos_webhook_secret", "")

        resp = client.post("/donate/webhook/coinos",
                           json={"received": -5000},
                           content_type="application/json")
        assert resp.status_code == 400

    def test_webhook_empty_body_rejected(self, client, temp_database):
        """Empty POST body must return 400."""
        resp = client.post("/donate/webhook/coinos",
                           data=b"",
                           content_type="application/json")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# 4. Lawyer editing admin-created articles
# ---------------------------------------------------------------------------

class TestLawyerArticlePermissions:
    """Verify lawyer access boundaries for articles created by other roles."""

    def test_lawyer_can_edit_own_article(self, lawyer_session):
        """Lawyer must be able to edit articles they created."""
        with lawyer_session.session_transaction() as sess:
            csrf = sess.get("csrf_token", "")

        # Create article as lawyer
        lawyer_session.post("/advogado/articles/new", data={
            "title": "Lawyer Article",
            "body_md": "Content",
            "csrf_token": csrf,
        })

        article = models.get_article_by_slug("lawyer-article")
        assert article is not None

        # Edit it
        resp = lawyer_session.post(f"/advogado/articles/{article['id']}/edit", data={
            "title": "Edited by Lawyer",
            "body_md": "New content",
            "csrf_token": csrf,
        })
        assert resp.status_code == 302

        updated = models.get_article_by_id(article["id"])
        assert updated["title"] == "Edited by Lawyer"

    def test_lawyer_can_access_admin_created_article_edit_page(self, lawyer_session):
        """Lawyer GET on edit page for admin-created article should return 200.

        The current code does not restrict by created_by.  This test
        documents the existing behavior so future changes are intentional.
        """
        slug = models.create_article("Admin Article", "Body", created_by="admin")
        article = models.get_article_by_slug(slug)

        resp = lawyer_session.get(f"/advogado/articles/{article['id']}/edit")
        # Document current behavior — if this should be restricted, change to 403
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 5. Lawyer self-approval
# ---------------------------------------------------------------------------

class TestLawyerSelfApproval:
    """Verify whether a lawyer can approve their own article."""

    def test_lawyer_can_approve_own_article(self, lawyer_session):
        """Document: lawyer CAN approve an article they created.

        This test documents current behavior.  If self-approval should
        be blocked, change this test to assert 403 and add the check.
        """
        with lawyer_session.session_transaction() as sess:
            csrf = sess.get("csrf_token", "")

        lawyer_session.post("/advogado/articles/new", data={
            "title": "Self Approve Test",
            "body_md": "Content",
            "csrf_token": csrf,
        })

        article = models.get_article_by_slug("self-approve-test")
        assert article is not None

        resp = lawyer_session.post(f"/advogado/articles/{article['id']}/approve", data={
            "csrf_token": csrf,
        })
        assert resp.status_code == 302

        approvals = models.get_article_approvals(article["id"])
        assert any(a["role"] == "lawyer" for a in approvals)


# ---------------------------------------------------------------------------
# 6. Checklist goal_btc boundary
# ---------------------------------------------------------------------------

class TestChecklistBoundary:
    """Dashboard checklist edge cases."""

    def test_checklist_goal_1btc_marked_not_done(self, admin_session):
        """goal_btc == '1.0' (the default) should show as not configured."""
        models.set_config("goal_btc", "1.0")
        resp = admin_session.get("/admin/")

        assert resp.status_code == 200
        assert b"Fundraising goal defined" in resp.data
        # The checklist item should NOT be marked done
        # (it links to settings, meaning it's still a pending task)
        assert b"/admin/settings#section-fundraising" in resp.data

    def test_checklist_goal_custom_marked_done(self, admin_session):
        """goal_btc != default should show as configured."""
        models.set_config("goal_btc", "2.5")
        resp = admin_session.get("/admin/")

        assert resp.status_code == 200
        # Should not contain the "complete this step" link for fundraising
        assert b"/admin/settings#section-fundraising" not in resp.data


# ---------------------------------------------------------------------------
# 7. Setup wizard edge cases
# ---------------------------------------------------------------------------

class TestSetupWizardEdgeCases:
    """Validation edge cases not covered in main wizard tests."""

    def _wizard_csrf(self, client):
        client.get("/admin/setup")
        with client.session_transaction() as sess:
            return sess.get("csrf_token", "")

    def test_wizard_goal_zero_rejected(self, client):
        """goal_btc = 0 must be rejected."""
        csrf = self._wizard_csrf(client)
        resp = client.post("/admin/setup", data={
            "admin_password": "securepass123",
            "admin_password_confirm": "securepass123",
            "site_title": "Test Campaign",
            "goal_btc": "0",
            "csrf_token": csrf,
        }, follow_redirects=True)

        assert resp.status_code == 200
        assert b"positive number" in resp.data.lower()

    def test_wizard_goal_negative_rejected(self, client):
        """goal_btc = -5 must be rejected."""
        csrf = self._wizard_csrf(client)
        resp = client.post("/admin/setup", data={
            "admin_password": "securepass123",
            "admin_password_confirm": "securepass123",
            "site_title": "Test Campaign",
            "goal_btc": "-5",
            "csrf_token": csrf,
        }, follow_redirects=True)

        assert resp.status_code == 200
        assert b"positive number" in resp.data.lower()

    def test_wizard_goal_empty_uses_default(self, client):
        """Empty goal_btc should succeed (uses existing default '1.0')."""
        csrf = self._wizard_csrf(client)
        resp = client.post("/admin/setup", data={
            "admin_password": "securepass123",
            "admin_password_confirm": "securepass123",
            "site_title": "Test Campaign",
            "goal_btc": "",
            "csrf_token": csrf,
        })

        assert resp.status_code == 302
        assert models.get_config("setup_complete") == "1"
        # Default should remain unchanged
        assert models.get_config("goal_btc") == "1.0"

    def test_wizard_whitespace_title_rejected(self, client):
        """Title with only spaces must be rejected."""
        csrf = self._wizard_csrf(client)
        resp = client.post("/admin/setup", data={
            "admin_password": "securepass123",
            "admin_password_confirm": "securepass123",
            "site_title": "   ",
            "goal_btc": "1.0",
            "csrf_token": csrf,
        }, follow_redirects=True)

        assert resp.status_code == 200
        assert b"Site title is required" in resp.data


# ---------------------------------------------------------------------------
# 8. Draft article public access
# ---------------------------------------------------------------------------

class TestDraftArticlePublicAccess:
    """Unpublished articles must not be accessible on the public site."""

    def test_draft_article_returns_404(self, client, temp_database):
        """GET /updates/<slug> for a draft article must return 404."""
        models.create_article("Secret Draft", "Hidden content", published=0, pinned=0)
        article = models.get_article_by_slug("secret-draft")
        assert article is not None
        assert article["published"] == 0

        resp = client.get("/updates/secret-draft")
        assert resp.status_code == 404

    def test_published_article_returns_200(self, client, temp_database):
        """GET /updates/<slug> for a published article must return 200."""
        models.create_article("Public Update", "Visible content")
        resp = client.get("/updates/public-update")
        assert resp.status_code == 200

    def test_draft_not_in_updates_list(self, client, temp_database):
        """Draft articles must not appear in the /updates listing."""
        models.create_article("Public One", "Body")
        models.create_article("Hidden Draft", "Body", published=0, pinned=0)

        resp = client.get("/updates")
        assert resp.status_code == 200
        assert b"Public One" in resp.data
        assert b"Hidden Draft" not in resp.data


# ---------------------------------------------------------------------------
# 9. Health endpoint
# ---------------------------------------------------------------------------

class TestHealthEndpoint:
    """The /health endpoint must confirm the app is running."""

    def test_health_returns_ok(self, client, temp_database):
        """GET /health must return 200 with status ok."""
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"

    def test_health_returns_json_content_type(self, client, temp_database):
        """Health response must have application/json content type."""
        resp = client.get("/health")
        assert "application/json" in resp.content_type
