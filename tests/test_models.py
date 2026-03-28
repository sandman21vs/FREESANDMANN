"""Testes para models.py — CRUD completo de config, articles, media_links, auth."""
import models


# ── Config ───────────────────────────────────────────────────────────

class TestConfig:
    def test_get_config_existing(self, temp_database):
        """Deve retornar valor existente."""
        val = models.get_config("site_title")
        assert val == "Bastion"

    def test_get_config_missing(self, temp_database):
        """Deve retornar default para chave inexistente."""
        val = models.get_config("nonexistent_key", "fallback")
        assert val == "fallback"

    def test_set_config_new(self, temp_database):
        """Deve inserir nova chave."""
        models.set_config("test_key", "test_value")
        assert models.get_config("test_key") == "test_value"

    def test_set_config_update(self, temp_database):
        """Deve atualizar chave existente."""
        models.set_config("site_title", "New Title")
        assert models.get_config("site_title") == "New Title"

    def test_get_all_config(self, temp_database):
        """Deve retornar dicionario com todas as chaves."""
        cfg = models.get_all_config()
        assert isinstance(cfg, dict)
        assert "site_title" in cfg
        assert "btc_address" in cfg


# ── Auth ─────────────────────────────────────────────────────────────

class TestAuth:
    def test_verify_correct_password(self, temp_database):
        """Senha 'FREE' deve ser valida no estado inicial."""
        assert models.verify_password("FREE") is True

    def test_verify_wrong_password(self, temp_database):
        """Senha errada deve retornar False."""
        assert models.verify_password("wrong") is False

    def test_verify_empty_password(self, temp_database):
        """Senha vazia deve retornar False."""
        assert models.verify_password("") is False

    def test_must_change_password_initial(self, temp_database):
        """No estado inicial, deve exigir troca de senha."""
        assert models.must_change_password() is True

    def test_change_password(self, temp_database):
        """Apos trocar senha, nova senha deve funcionar e flag deve ser False."""
        models.change_password("newsecurepassword")
        assert models.verify_password("newsecurepassword") is True
        assert models.verify_password("FREE") is False
        assert models.must_change_password() is False

    def test_change_password_updates_flag(self, temp_database):
        """Trocar senha deve setar admin_force_password_change para '0'."""
        models.change_password("anotherpassword")
        assert models.get_config("admin_force_password_change") == "0"


# ── Articles ─────────────────────────────────────────────────────────

class TestArticles:
    def test_create_article(self, temp_database):
        """Criar artigo deve retornar slug e artigo deve ser encontravel."""
        slug = models.create_article("Test Article", "This is **bold**")
        assert slug == "test-article"

        article = models.get_article_by_slug("test-article")
        assert article is not None
        assert article["title"] == "Test Article"
        assert article["body_md"] == "This is **bold**"
        assert "<strong>bold</strong>" in article["body_html"]
        assert article["published"] == 1
        assert article["pinned"] == 0

    def test_create_article_slug_collision(self, temp_database):
        """Slugs duplicados devem receber sufixo para evitar colisao."""
        slug1 = models.create_article("My Post", "Content 1")
        slug2 = models.create_article("My Post", "Content 2")
        assert slug1 != slug2
        assert slug1 == "my-post"
        # slug2 deve ter sufixo (timestamp)
        assert slug2.startswith("my-post-")

    def test_create_article_draft(self, temp_database):
        """Artigo com published=0 nao deve aparecer na lista publica."""
        models.create_article("Draft", "Secret", published=0)
        public = models.get_articles(published_only=True)
        all_articles = models.get_articles(published_only=False)

        public_titles = [a["title"] for a in public]
        all_titles = [a["title"] for a in all_articles]

        assert "Draft" not in public_titles
        assert "Draft" in all_titles

    def test_create_article_pinned(self, temp_database):
        """Artigos pinned devem aparecer primeiro na lista."""
        models.create_article("Normal", "Content")
        models.create_article("Pinned", "Content", pinned=1)

        articles = models.get_articles(published_only=True)
        assert articles[0]["title"] == "Pinned"

    def test_update_article(self, temp_database):
        """Atualizar artigo deve mudar titulo, body e slug."""
        slug = models.create_article("Original", "Old content")
        article = models.get_article_by_slug(slug)

        models.update_article(article["id"], "Updated Title", "New content")

        updated = models.get_article_by_id(article["id"])
        assert updated["title"] == "Updated Title"
        assert updated["body_md"] == "New content"
        assert updated["slug"] == "updated-title"

    def test_delete_article(self, temp_database):
        """Deletar artigo deve remove-lo do banco."""
        slug = models.create_article("To Delete", "Bye")
        article = models.get_article_by_slug(slug)

        models.delete_article(article["id"])
        assert models.get_article_by_id(article["id"]) is None

    def test_get_article_nonexistent(self, temp_database):
        """Buscar artigo inexistente deve retornar None."""
        assert models.get_article_by_slug("nope") is None
        assert models.get_article_by_id(99999) is None

    def test_markdown_rendering(self, temp_database):
        """Markdown deve ser renderizado para HTML corretamente."""
        slug = models.create_article("MD Test", "# Heading\n\n- item 1\n- item 2")
        article = models.get_article_by_slug(slug)
        assert "<h1>" in article["body_html"] or "Heading" in article["body_html"]
        assert "<li>" in article["body_html"]

    def test_youtube_auto_embed(self, temp_database):
        """URLs do YouTube devem virar iframe embed."""
        slug = models.create_article(
            "Video Post",
            "Watch this: https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        )
        article = models.get_article_by_slug(slug)
        assert "youtube-nocookie.com/embed/dQw4w9WgXcQ" in article["body_html"]
        assert "<iframe" in article["body_html"]

    def test_twitter_auto_embed(self, temp_database):
        """URLs do Twitter/X devem virar embed blockquote."""
        slug = models.create_article(
            "Tweet Post",
            "See this: https://twitter.com/user/status/1234567890"
        )
        article = models.get_article_by_slug(slug)
        assert "twitter-tweet" in article["body_html"]
        assert "1234567890" in article["body_html"]

    def test_auto_embed_ignores_href(self, temp_database):
        """URLs dentro de href nao devem ser convertidas em embed."""
        slug = models.create_article(
            "Link Post",
            '<a href="https://www.youtube.com/watch?v=dQw4w9WgXcQ">link</a>'
        )
        article = models.get_article_by_slug(slug)
        # O href deve continuar intacto, nao virar iframe
        assert 'href="https://www.youtube.com/watch?v=dQw4w9WgXcQ"' in article["body_html"]

    def test_slug_special_characters(self, temp_database):
        """Slug deve lidar com caracteres especiais sem quebrar."""
        slug = models.create_article("Titulo com Acentuacao! @#$%", "Content")
        assert slug  # nao deve ser vazio
        # Slug deve conter apenas letras, numeros e hifens
        import re
        assert re.match(r'^[a-z0-9-]+$', slug), f"Invalid slug: {slug}"


# ── Media Links ──────────────────────────────────────────────────────

class TestMediaLinks:
    def test_add_media_link(self, temp_database):
        """Adicionar link deve funcionar e aparecer na lista."""
        models.add_media_link("My Video", "https://youtube.com/xyz", "video")
        links = models.get_media_links()
        assert len(links) == 1
        assert links[0]["title"] == "My Video"
        assert links[0]["link_type"] == "video"

    def test_delete_media_link(self, temp_database):
        """Deletar link deve remove-lo da lista."""
        models.add_media_link("To Delete", "https://example.com", "article")
        links = models.get_media_links()
        models.delete_media_link(links[0]["id"])
        assert len(models.get_media_links()) == 0

    def test_media_links_ordered_by_date(self, temp_database):
        """Links devem vir ordenados por data decrescente (mais novo primeiro)."""
        models.add_media_link("First", "https://a.com")
        models.add_media_link("Second", "https://b.com")
        links = models.get_media_links()
        # O mais recente deve vir primeiro
        assert links[0]["title"] == "Second"


# ── Balance Check ────────────────────────────────────────────────────

class TestBalanceCheck:
    def test_recalculate_raised_btc(self, temp_database):
        """Recalcular total deve somar on-chain + lightning + ajuste."""
        models.set_config("raised_onchain_btc", "1.5")
        models.set_config("raised_lightning_btc", "0.3")
        models.set_config("raised_btc_manual_adjustment", "0.2")
        models.recalculate_raised_btc()
        total = float(models.get_config("raised_btc"))
        assert abs(total - 2.0) < 0.0001, f"Expected 2.0, got {total}"

    def test_check_onchain_balance_no_address(self, temp_database):
        """Se nao tiver endereco BTC, nao deve fazer nada nem dar erro."""
        models.set_config("btc_address", "")
        # Nao deve lancar excecao
        models.check_onchain_balance()

    def test_check_onchain_balance_api_failure(self, temp_database, monkeypatch):
        """Se a API falhar, deve manter o ultimo valor."""
        models.set_config("btc_address", "bc1qtest123")
        models.set_config("raised_onchain_btc", "0.5")

        # Mockar urllib para falhar
        import urllib.request
        def mock_urlopen(*args, **kwargs):
            raise ConnectionError("Simulated failure")
        monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

        models.check_onchain_balance()
        # Valor deve permanecer inalterado
        assert models.get_config("raised_onchain_btc") == "0.5"

    def test_check_onchain_balance_success(self, temp_database, monkeypatch):
        """Se a API retornar dados validos, deve atualizar o saldo."""
        import json
        import io
        import urllib.request

        models.set_config("btc_address", "bc1qtest123")

        # Mockar resposta da API mempool.space
        mock_response_data = json.dumps({
            "chain_stats": {
                "funded_txo_sum": 150000000,  # 1.5 BTC em satoshis
                "spent_txo_sum": 0
            },
            "mempool_stats": {
                "funded_txo_sum": 0,
                "spent_txo_sum": 0
            }
        }).encode()

        class MockResponse:
            def read(self):
                return mock_response_data
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass

        def mock_urlopen(*args, **kwargs):
            return MockResponse()

        monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

        models.check_onchain_balance()
        onchain = float(models.get_config("raised_onchain_btc"))
        assert abs(onchain - 1.5) < 0.0001, f"Expected 1.5, got {onchain}"

        # Total tambem deve ser atualizado
        total = float(models.get_config("raised_btc"))
        assert total >= 1.5

    def test_check_onchain_balance_includes_mempool(self, temp_database, monkeypatch):
        """Saldo deve incluir transacoes nao confirmadas (mempool)."""
        import json
        import urllib.request

        models.set_config("btc_address", "bc1qtest123")

        mock_response_data = json.dumps({
            "chain_stats": {
                "funded_txo_sum": 100000000,  # 1.0 BTC confirmado
                "spent_txo_sum": 0
            },
            "mempool_stats": {
                "funded_txo_sum": 50000000,  # 0.5 BTC na mempool
                "spent_txo_sum": 0
            }
        }).encode()

        class MockResponse:
            def read(self):
                return mock_response_data
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass

        def mock_urlopen(*args, **kwargs):
            return MockResponse()

        monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

        models.check_onchain_balance()
        onchain = float(models.get_config("raised_onchain_btc"))
        # Deve ser 1.0 + 0.5 = 1.5 BTC (confirmado + mempool)
        assert abs(onchain - 1.5) < 0.0001, f"Expected 1.5 (confirmed+mempool), got {onchain}"
