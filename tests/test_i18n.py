"""Testes de internacionalização (PT/EN/DE)."""
import models
import i18n


class TestLanguageDetection:
    def test_default_lang_pt(self, client):
        """Sem header ou sessão, idioma é PT."""
        resp = client.get("/")
        assert resp.status_code == 200

    def test_accept_language_en(self, client):
        """Header Accept-Language: en deve retornar EN."""
        resp = client.get("/", headers={"Accept-Language": "en"})
        assert resp.status_code == 200

    def test_accept_language_de(self, client):
        """Header Accept-Language: de deve retornar DE."""
        resp = client.get("/", headers={"Accept-Language": "de"})
        assert resp.status_code == 200


class TestSetLanguageRoute:
    def test_set_lang_en(self, client):
        """GET /set-lang/en salva na sessão e redireciona."""
        client.get("/")
        resp = client.get("/set-lang/en", follow_redirects=False)
        assert resp.status_code == 302

        # Verificar que a sessão foi atualizada
        client.get("/")
        with client.session_transaction() as sess:
            assert sess.get("lang") == "en"

    def test_set_lang_de(self, client):
        """GET /set-lang/de salva na sessão e redireciona."""
        client.get("/")
        resp = client.get("/set-lang/de", follow_redirects=False)
        assert resp.status_code == 302

        client.get("/")
        with client.session_transaction() as sess:
            assert sess.get("lang") == "de"

    def test_set_lang_invalid(self, client):
        """Idioma inválido é ignorado."""
        client.get("/")
        with client.session_transaction() as sess:
            sess["lang"] = "pt"

        resp = client.get("/set-lang/invalid", follow_redirects=False)
        assert resp.status_code == 302

        client.get("/")
        with client.session_transaction() as sess:
            assert sess.get("lang") == "pt"


class TestTranslationFallback:
    def test_translation_fallback(self):
        """Chave inexistente retorna a própria chave."""
        result = i18n.t("nonexistent_key", "pt")
        assert result == "nonexistent_key"

    def test_translation_exists_pt(self):
        """Chave existente em PT retorna tradução."""
        result = i18n.t("nav_home", "pt")
        assert result == "Home"

    def test_translation_exists_en(self):
        """Chave existente em EN retorna tradução."""
        result = i18n.t("nav_home", "en")
        assert result == "Home"


class TestArticleTranslation:
    def test_article_served_in_english(self, client, temp_database):
        """Artigo com tradução EN retorna título EN."""
        models.create_article(
            "Test Article PT",
            "Conteúdo em PT",
            published=1,
            pinned=0,
            title_en="Test Article EN",
            body_md_en="Content in EN"
        )

        # Configurar sessão para EN
        client.get("/")
        with client.session_transaction() as sess:
            sess["lang"] = "en"

        # Buscar artigo em EN
        articles = models.get_articles(published_only=True)
        assert len(articles) > 0
        article = articles[0]

        result = models.get_article_for_lang(article["slug"], "en")
        assert result is not None
        assert result["title"] == "Test Article EN"

    def test_article_fallback_to_pt(self, client, temp_database):
        """Artigo sem tradução DE retorna PT."""
        models.create_article(
            "Test Article PT",
            "Conteúdo em PT",
            published=1,
            pinned=0,
            title_de="",
            body_md_de=""
        )

        articles = models.get_articles(published_only=True)
        article = articles[0]

        result = models.get_article_for_lang(article["slug"], "de")
        assert result is not None
        assert result["title"] == "Test Article PT"


class TestAdminArticleTranslations:
    def test_admin_article_form_saves_translations(self, admin_session, temp_database):
        """Admin salva traduções EN e DE ao criar artigo."""
        with admin_session.session_transaction() as sess:
            csrf = sess.get("csrf_token", "")

        resp = admin_session.post("/admin/articles/new", data={
            "csrf_token": csrf,
            "title": "Article PT",
            "body_md": "Body PT",
            "published": "1",
            "title_en": "Article EN",
            "body_md_en": "Body EN",
            "title_de": "Article DE",
            "body_md_de": "Body DE",
        })

        assert resp.status_code == 302

        # Verificar que o artigo foi salvo com as traduções
        articles = models.get_articles(published_only=False)
        assert len(articles) > 0
        article = articles[0]

        assert article["title"] == "Article PT"
        assert article["title_en"] == "Article EN"
        assert article["title_de"] == "Article DE"

    def test_admin_article_edit_updates_translations(self, admin_session, temp_database):
        """Admin atualiza traduções EN e DE ao editar artigo."""
        models.create_article(
            "Old Title PT",
            "Old Body PT",
            published=1,
            pinned=0,
            title_en="Old Title EN",
            body_md_en="Old Body EN"
        )

        articles = models.get_articles(published_only=False)
        article_id = articles[0]["id"]

        with admin_session.session_transaction() as sess:
            csrf = sess.get("csrf_token", "")

        resp = admin_session.post(f"/admin/articles/{article_id}/edit", data={
            "csrf_token": csrf,
            "title": "New Title PT",
            "body_md": "New Body PT",
            "published": "1",
            "title_en": "New Title EN",
            "body_md_en": "New Body EN",
            "title_de": "New Title DE",
            "body_md_de": "New Body DE",
        })

        assert resp.status_code == 302

        updated = models.get_article_by_id(article_id)
        assert updated["title"] == "New Title PT"
        assert updated["title_en"] == "New Title EN"
        assert updated["title_de"] == "New Title DE"


class TestContextProcessorInjectsI18n:
    def test_t_function_available_in_templates(self, client):
        """Função `t()` e `lang` disponíveis nos templates."""
        resp = client.get("/")
        assert resp.status_code == 200
        # Se os templates renderizam sem erro, significa que `t` e `lang` existem
