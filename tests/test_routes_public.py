"""Testes das rotas publicas — homepage, donate, updates, article."""


class TestBootstrapGate:
    def test_first_visit_redirects_to_setup(self, fresh_client):
        """Homepage deve redirecionar ao setup enquanto a instalacao nao foi inicializada."""
        resp = fresh_client.get("/")
        assert resp.status_code == 302
        assert "/admin/setup" in resp.headers.get("Location", "")

    def test_donate_redirects_to_setup(self, fresh_client):
        """Pagina de doacao deve ficar bloqueada ate o setup ser concluido."""
        resp = fresh_client.get("/donate")
        assert resp.status_code == 302
        assert "/admin/setup" in resp.headers.get("Location", "")

    def test_updates_redirects_to_setup(self, fresh_client):
        """Lista publica de updates nao deve abrir antes do setup."""
        resp = fresh_client.get("/updates")
        assert resp.status_code == 302
        assert "/admin/setup" in resp.headers.get("Location", "")

    def test_health_stays_available_during_bootstrap(self, fresh_client):
        """Healthcheck deve continuar acessivel durante o bootstrap."""
        resp = fresh_client.get("/health")
        assert resp.status_code == 200
        assert resp.get_json() == {"status": "ok"}

    def test_static_assets_stay_available_during_bootstrap(self, fresh_client):
        """Arquivos estaticos devem continuar acessiveis para renderizar o wizard."""
        resp = fresh_client.get("/static/style.css")
        assert resp.status_code == 200
        assert b"--btc-orange" in resp.data

    def test_language_switch_is_allowed_during_bootstrap(self, fresh_client):
        """Troca de idioma precisa continuar funcionando no setup wizard."""
        resp = fresh_client.get(
            "/set-lang/en",
            headers={"Referer": "http://localhost/admin/setup"},
        )
        assert resp.status_code == 302
        assert "/admin/setup" in resp.headers.get("Location", "")

        with fresh_client.session_transaction() as sess:
            assert sess.get("lang") == "en"


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
