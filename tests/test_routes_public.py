"""Testes das rotas publicas — homepage, donate, updates, article."""


class TestHomepage:
    def test_index_returns_200(self, client):
        """Homepage deve retornar 200."""
        resp = client.get("/")
        assert resp.status_code == 200

    def test_index_contains_site_title(self, client):
        """Homepage deve conter o titulo do site."""
        resp = client.get("/")
        assert b"Bastion" in resp.data

    def test_index_contains_progress(self, client):
        """Homepage deve conter elementos da barra de progresso."""
        resp = client.get("/")
        assert b"BTC" in resp.data

    def test_index_contains_admin_footer_link(self, client):
        """Homepage deve expor um link sutil para o login admin."""
        resp = client.get("/")
        assert b'/admin/login' in resp.data


class TestDonate:
    def test_donate_returns_200(self, client):
        """Pagina de doacao deve retornar 200."""
        resp = client.get("/donate")
        assert resp.status_code == 200

    def test_donate_contains_bitcoin(self, client):
        """Pagina de doacao deve mencionar Bitcoin."""
        resp = client.get("/donate")
        assert b"Bitcoin" in resp.data or b"bitcoin" in resp.data


class TestHealth:
    def test_health_returns_ok_json(self, client):
        """Healthcheck deve responder JSON minimo com status ok."""
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.get_json() == {"status": "ok"}


class TestUpdates:
    def test_updates_returns_200(self, client):
        """Lista de artigos deve retornar 200."""
        resp = client.get("/updates")
        assert resp.status_code == 200

    def test_updates_empty(self, client):
        """Sem artigos, deve mostrar mensagem ou lista vazia sem erro."""
        resp = client.get("/updates")
        assert resp.status_code == 200

    def test_updates_shows_published_article(self, client):
        """Artigo publicado deve aparecer na lista."""
        import models
        models.create_article("Published Post", "Content here", published=1)
        resp = client.get("/updates")
        assert b"Published Post" in resp.data

    def test_updates_hides_draft(self, client):
        """Artigo em rascunho NAO deve aparecer na lista publica."""
        import models
        models.create_article("Secret Draft", "Hidden", published=0)
        resp = client.get("/updates")
        assert b"Secret Draft" not in resp.data


class TestArticleView:
    def test_article_returns_200(self, client):
        """Artigo existente deve retornar 200."""
        import models
        slug = models.create_article("My Article", "Content")
        resp = client.get(f"/updates/{slug}")
        assert resp.status_code == 200

    def test_article_contains_content(self, client):
        """Artigo deve conter o conteudo renderizado."""
        import models
        slug = models.create_article("My Article", "This is the body text")
        resp = client.get(f"/updates/{slug}")
        assert b"This is the body text" in resp.data

    def test_article_not_found(self, client):
        """Artigo inexistente deve retornar 404."""
        resp = client.get("/updates/nonexistent-slug")
        assert resp.status_code == 404


class TestErrorPages:
    def test_404_page(self, client):
        """Rota inexistente deve retornar 404."""
        resp = client.get("/this-page-does-not-exist")
        assert resp.status_code == 404
