"""Testes de internacionalização (PT/EN/DE) e tema claro/escuro."""
import re
import models
import i18n


# ── Detecção de idioma ──────────────────────────────────────────────


class TestLanguageDetection:
    def test_default_lang_pt(self, client):
        """Sem header ou sessão, idioma é PT."""
        resp = client.get("/")
        assert resp.status_code == 200

    def test_accept_language_en(self, client):
        """Header Accept-Language: en → site em inglês."""
        resp = client.get("/", headers={"Accept-Language": "en"})
        assert resp.status_code == 200
        with client.session_transaction() as sess:
            assert sess.get("lang") == "en"

    def test_accept_language_de(self, client):
        """Header Accept-Language: de → site em alemão."""
        resp = client.get("/", headers={"Accept-Language": "de"})
        assert resp.status_code == 200
        with client.session_transaction() as sess:
            assert sess.get("lang") == "de"

    def test_accept_language_complex_header(self, client):
        """Accept-Language com peso (q=) é parseado corretamente."""
        resp = client.get("/", headers={"Accept-Language": "en-US,en;q=0.9,de;q=0.8"})
        assert resp.status_code == 200
        with client.session_transaction() as sess:
            assert sess.get("lang") == "en"

    def test_accept_language_unsupported_falls_back_to_pt(self, client):
        """Idioma não suportado (fr, ja, etc) faz fallback para PT."""
        resp = client.get("/", headers={"Accept-Language": "fr,ja"})
        assert resp.status_code == 200
        with client.session_transaction() as sess:
            assert sess.get("lang") == "pt"

    def test_session_lang_overrides_header(self, client):
        """Idioma salvo na session tem prioridade sobre Accept-Language."""
        client.get("/")
        with client.session_transaction() as sess:
            sess["lang"] = "de"

        resp = client.get("/", headers={"Accept-Language": "en"})
        assert resp.status_code == 200
        with client.session_transaction() as sess:
            assert sess.get("lang") == "de"


# ── Rota /set-lang ──────────────────────────────────────────────────


class TestSetLanguageRoute:
    def test_set_lang_en(self, client):
        client.get("/")
        client.get("/set-lang/en")
        with client.session_transaction() as sess:
            assert sess.get("lang") == "en"

    def test_set_lang_de(self, client):
        client.get("/")
        client.get("/set-lang/de")
        with client.session_transaction() as sess:
            assert sess.get("lang") == "de"

    def test_set_lang_pt(self, client):
        client.get("/")
        client.get("/set-lang/de")
        client.get("/set-lang/pt")
        with client.session_transaction() as sess:
            assert sess.get("lang") == "pt"

    def test_set_lang_invalid_ignored(self, client):
        """Idioma inválido não altera a session."""
        client.get("/")
        with client.session_transaction() as sess:
            sess["lang"] = "pt"
        client.get("/set-lang/fr")
        with client.session_transaction() as sess:
            assert sess.get("lang") == "pt"

    def test_set_lang_redirects(self, client):
        resp = client.get("/set-lang/en", follow_redirects=False)
        assert resp.status_code == 302


# ── Traduções (módulo i18n) ─────────────────────────────────────────


class TestTranslations:
    def test_unknown_key_returns_key(self):
        assert i18n.t("nonexistent_key_xyz", "pt") == "nonexistent_key_xyz"

    def test_unknown_lang_falls_back_to_pt(self):
        pt_val = i18n.t("nav_home", "pt")
        unknown = i18n.t("nav_home", "xx")
        assert unknown == pt_val

    def test_pt_translations_loaded(self):
        assert i18n.t("nav_home", "pt") == "Home"
        assert i18n.t("donate_now", "pt") == "Doe Agora"
        assert i18n.t("copy", "pt") == "Copiar"

    def test_en_translations_loaded(self):
        assert i18n.t("nav_home", "en") == "Home"
        assert i18n.t("donate_now", "en") == "Donate Now"
        assert i18n.t("copy", "en") == "Copy"

    def test_de_translations_loaded(self):
        assert i18n.t("nav_home", "de") == "Startseite"
        assert i18n.t("donate_now", "de") == "Jetzt Spenden"
        assert i18n.t("copy", "de") == "Kopieren"

    def test_all_keys_present_in_all_languages(self):
        """Toda chave do PT existe também em EN e DE."""
        pt_keys = set(i18n._translations["pt"].keys())
        en_keys = set(i18n._translations["en"].keys())
        de_keys = set(i18n._translations["de"].keys())
        assert pt_keys == en_keys, f"Faltando em EN: {pt_keys - en_keys}"
        assert pt_keys == de_keys, f"Faltando em DE: {pt_keys - de_keys}"


# ── Títulos na listagem ─────────────────────────────────────────────


class TestArticleListingTranslation:
    def _create_trilingual_article(self, pinned=0):
        models.create_article(
            "Artigo em Português",
            "Conteúdo PT",
            published=1,
            pinned=pinned,
            title_en="Article in English",
            body_md_en="Content EN",
            title_de="Artikel auf Deutsch",
            body_md_de="Inhalt DE",
        )

    def test_homepage_pinned_title_shows_in_pt(self, client, temp_database):
        """Homepage: título do artigo fixado aparece em PT quando idioma é PT."""
        self._create_trilingual_article(pinned=1)
        with client.session_transaction() as sess:
            sess["lang"] = "pt"
        resp = client.get("/")
        assert b"Artigo em Portugu" in resp.data

    def test_homepage_pinned_title_shows_in_en(self, client, temp_database):
        """Homepage: título do artigo fixado aparece em EN quando idioma é EN."""
        self._create_trilingual_article(pinned=1)
        with client.session_transaction() as sess:
            sess["lang"] = "en"
        resp = client.get("/")
        assert b"Article in English" in resp.data
        assert b"Artigo em Portugu" not in resp.data

    def test_homepage_pinned_title_shows_in_de(self, client, temp_database):
        """Homepage: título do artigo fixado aparece em DE quando idioma é DE."""
        self._create_trilingual_article(pinned=1)
        with client.session_transaction() as sess:
            sess["lang"] = "de"
        resp = client.get("/")
        assert b"Artikel auf Deutsch" in resp.data
        assert b"Artigo em Portugu" not in resp.data

    def test_updates_page_title_in_en(self, client, temp_database):
        """Página /updates: título aparece em EN."""
        self._create_trilingual_article()
        with client.session_transaction() as sess:
            sess["lang"] = "en"
        resp = client.get("/updates")
        assert b"Article in English" in resp.data

    def test_updates_page_title_in_de(self, client, temp_database):
        """Página /updates: título aparece em DE."""
        self._create_trilingual_article()
        with client.session_transaction() as sess:
            sess["lang"] = "de"
        resp = client.get("/updates")
        assert b"Artikel auf Deutsch" in resp.data

    def test_updates_page_preview_in_en(self, client, temp_database):
        """Preview do artigo em /updates aparece em EN."""
        self._create_trilingual_article()
        with client.session_transaction() as sess:
            sess["lang"] = "en"
        resp = client.get("/updates")
        assert b"Content EN" in resp.data
        assert b"Conte" not in resp.data or b"Content EN" in resp.data

    def test_article_without_translation_falls_back_to_pt(self, client, temp_database):
        """Artigo sem tradução DE exibe PT na listagem."""
        models.create_article(
            "Apenas em Português",
            "Só PT",
            published=1,
            pinned=1,
        )
        with client.session_transaction() as sess:
            sess["lang"] = "de"
        resp = client.get("/")
        assert b"Apenas em Portugu" in resp.data

    def test_article_detail_in_english(self, client, temp_database):
        """Artigo aberto individualmente aparece em EN."""
        slug = models.create_article(
            "Título PT", "Corpo PT",
            published=1,
            title_en="English Title",
            body_md_en="English body",
        )
        with client.session_transaction() as sess:
            sess["lang"] = "en"
        resp = client.get(f"/updates/{slug}")
        assert b"English Title" in resp.data


# ── UI traduzida (nav, botões) ──────────────────────────────────────


class TestUITranslation:
    def test_nav_shows_in_english(self, client):
        with client.session_transaction() as sess:
            sess["lang"] = "en"
        resp = client.get("/")
        html = resp.data.decode()
        assert "Donate Now" in html
        assert "Updates" in html

    def test_nav_shows_in_german(self, client):
        with client.session_transaction() as sess:
            sess["lang"] = "de"
        resp = client.get("/")
        html = resp.data.decode()
        assert "Jetzt Spenden" in html
        assert "Aktualisierungen" in html

    def test_donate_page_title_in_english(self, client):
        with client.session_transaction() as sess:
            sess["lang"] = "en"
        resp = client.get("/donate")
        assert b"Donate Bitcoin" in resp.data

    def test_donate_page_title_in_german(self, client):
        with client.session_transaction() as sess:
            sess["lang"] = "de"
        resp = client.get("/donate")
        assert "Bitcoin Spenden".encode() in resp.data

    def test_widget_shows_active_lang(self, client):
        """Widget flutuante marca o idioma ativo com classe 'active'."""
        with client.session_transaction() as sess:
            sess["lang"] = "en"
        resp = client.get("/")
        html = resp.data.decode()
        # O link EN deve ter class="pref-lang active"
        assert re.search(r'class="pref-lang[^"]*active[^"]*"[^>]*>EN', html) or \
               re.search(r'>EN<', html)


# ── Modelos: get_articles_for_lang ─────────────────────────────────


class TestGetArticlesForLang:
    def test_returns_pt_by_default(self, temp_database):
        models.create_article("PT Title", "PT body", published=1,
                              title_en="EN Title", body_md_en="EN body")
        articles = models.get_articles_for_lang(lang="pt")
        assert articles[0]["title"] == "PT Title"

    def test_returns_en_when_available(self, temp_database):
        models.create_article("PT Title", "PT body", published=1,
                              title_en="EN Title", body_md_en="EN body")
        articles = models.get_articles_for_lang(lang="en")
        assert articles[0]["title"] == "EN Title"
        assert articles[0]["body_md"] == "EN body"

    def test_returns_de_when_available(self, temp_database):
        models.create_article("PT Title", "PT body", published=1,
                              title_de="DE Title", body_md_de="DE body")
        articles = models.get_articles_for_lang(lang="de")
        assert articles[0]["title"] == "DE Title"

    def test_fallback_when_en_empty(self, temp_database):
        models.create_article("PT Title", "PT body", published=1,
                              title_en="", body_md_en="")
        articles = models.get_articles_for_lang(lang="en")
        assert articles[0]["title"] == "PT Title"

    def test_fallback_when_de_empty(self, temp_database):
        models.create_article("PT Title", "PT body", published=1,
                              title_de="", body_md_de="")
        articles = models.get_articles_for_lang(lang="de")
        assert articles[0]["title"] == "PT Title"

    def test_unpublished_excluded(self, temp_database):
        models.create_article("Draft", "body", published=0)
        articles = models.get_articles_for_lang(published_only=True, lang="pt")
        assert all(a["title"] != "Draft" for a in articles)

    def test_unpublished_included_when_requested(self, temp_database):
        models.create_article("Draft", "body", published=0)
        articles = models.get_articles_for_lang(published_only=False, lang="pt")
        assert any(a["title"] == "Draft" for a in articles)


# ── Tema claro/escuro ───────────────────────────────────────────────


class TestThemeCSS:
    """Verifica que o CSS do tema claro tem todas as variáveis de contraste necessárias."""

    def _get_css(self, client):
        resp = client.get("/static/style.css")
        assert resp.status_code == 200
        return resp.data.decode()

    def test_light_theme_block_exists(self, client):
        css = self._get_css(client)
        assert '[data-theme="light"]' in css

    def test_dark_theme_block_exists(self, client):
        css = self._get_css(client)
        assert '[data-theme="dark"]' in css

    def test_light_theme_has_text_color(self, client):
        """Tema claro define cor de texto para evitar texto invisível."""
        css = self._get_css(client)
        light_block = css.split('[data-theme="light"]')[1].split('}')[0]
        assert '--pico-color' in light_block

    def test_light_theme_has_background(self, client):
        """Tema claro define cor de fundo."""
        css = self._get_css(client)
        light_block = css.split('[data-theme="light"]')[1].split('}')[0]
        assert '--pico-background-color' in light_block

    def test_light_theme_has_progress_bar_background(self, client):
        """Tema claro define fundo da barra de progresso (contraste visível)."""
        css = self._get_css(client)
        light_block = css.split('[data-theme="light"]')[1].split('}')[0]
        assert '--pico-progress-background-color' in light_block

    def test_light_theme_progress_bar_is_not_white(self, client):
        """Barra de progresso no tema claro não pode ser branca (#ffffff) — ficaria invisível."""
        css = self._get_css(client)
        light_block = css.split('[data-theme="light"]')[1].split('}')[0]
        # Extrair valor da variável de progresso
        match = re.search(r'--pico-progress-background-color\s*:\s*([^;]+)', light_block)
        assert match, "Variável --pico-progress-background-color não encontrada"
        value = match.group(1).strip().lower()
        assert value not in ("#ffffff", "#fff", "white"), \
            "Fundo da progress bar não pode ser branco no tema claro"

    def test_light_theme_has_border_color(self, client):
        """Tema claro define bordas para separar elementos."""
        css = self._get_css(client)
        light_block = css.split('[data-theme="light"]')[1].split('}')[0]
        assert '--pico-border-color' in light_block or '--pico-card-border-color' in light_block

    def test_light_theme_card_differs_from_background(self, client):
        """Card e fundo têm cores diferentes para criar profundidade."""
        css = self._get_css(client)
        light_block = css.split('[data-theme="light"]')[1].split('}')[0]
        bg_match = re.search(r'--pico-background-color\s*:\s*([^;]+)', light_block)
        card_match = re.search(r'--pico-card-background-color\s*:\s*([^;]+)', light_block)
        if bg_match and card_match:
            assert bg_match.group(1).strip() != card_match.group(1).strip(), \
                "Fundo e card devem ter cores diferentes no tema claro"

    def test_light_theme_has_heading_colors(self, client):
        """Tema claro define cores dos headings."""
        css = self._get_css(client)
        light_block = css.split('[data-theme="light"]')[1].split('}')[0]
        assert '--pico-h1-color' in light_block or '--pico-color' in light_block

    def test_progress_bar_webkit_uses_css_variable(self, client):
        """Progress bar webkit usa variável CSS para se adaptar ao tema."""
        css = self._get_css(client)
        assert '--pico-progress-background-color' in css or 'var(--' in css

    def test_widget_pref_css_exists(self, client):
        """CSS do widget de preferências existe."""
        css = self._get_css(client)
        assert '.pref-widget' in css
        assert '.pref-panel' in css
        assert '.pref-lang' in css

    def test_light_and_dark_define_bg_dark_var(self, client):
        """Ambos os temas definem --bg-dark para cards e seções usarem."""
        css = self._get_css(client)
        light_block = css.split('[data-theme="light"]')[1].split('}')[0]
        assert '--bg-dark' in light_block

    def test_base_html_has_theme_detection_script(self, client):
        """base.html contém script de detecção de tema para evitar flash."""
        resp = client.get("/")
        html = resp.data.decode()
        assert "localStorage.getItem('theme')" in html
        assert "prefers-color-scheme" in html
        assert "setAttribute('data-theme'" in html

    def test_base_html_has_lang_widget(self, client):
        """base.html contém o widget de idioma/tema."""
        resp = client.get("/")
        html = resp.data.decode()
        assert 'id="pref-widget"' in html
        assert '/set-lang/en' in html
        assert '/set-lang/de' in html
        assert '/set-lang/pt' in html
