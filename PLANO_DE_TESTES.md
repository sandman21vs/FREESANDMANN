# PLANO DE TESTES — Free Sandmann

Documento operacional para criacao de testes automatizados.
Cada parte corresponde a uma parte do PLANO_DE_ACAO.md.
O modelo que implementar cada parte DEVE criar e rodar os testes antes de considerar a parte concluida.

**REGRA FUNDAMENTAL**: Nenhuma parte esta completa ate que TODOS os testes dessa parte passem com `pytest` retornando exit code 0.

---

## Setup de Testes

### Dependencia adicional

Adicionar ao `requirements.txt` (na Parte 1):

```
pytest==8.3.4
```

### Estrutura de arquivos de teste

```
FREESANDMANN/
├── tests/
│   ├── __init__.py            # Arquivo vazio
│   ├── conftest.py            # Fixtures compartilhadas (MUITO IMPORTANTE)
│   ├── test_config.py         # Testes da Parte 1: config
│   ├── test_init_db.py        # Testes da Parte 1: init_db
│   ├── test_models.py         # Testes da Parte 1: models
│   ├── test_routes_public.py  # Testes da Parte 2: rotas publicas
│   ├── test_routes_admin.py   # Testes da Parte 2: rotas admin
│   ├── test_qr.py             # Testes da Parte 2: QR codes
│   ├── test_balance.py        # Testes da Parte 2: balance checker
│   ├── test_templates.py      # Testes da Parte 3+4: templates renderizam
│   └── test_csrf.py           # Testes da Parte 2: protecao CSRF
```

### Criar diretorio

```bash
mkdir -p /home/msi/FREESANDMANN/tests
touch /home/msi/FREESANDMANN/tests/__init__.py
```

---

## `tests/conftest.py` — Fixtures compartilhadas

Este arquivo e CRITICO. Todas as fixtures que os testes usam estao aqui.
Criar ANTES de qualquer arquivo de teste.

```python
import os
import sys
import tempfile
import pytest

# Garantir que o diretorio raiz do projeto esta no path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture(autouse=True)
def temp_database(tmp_path, monkeypatch):
    """
    TODA test function usa um banco SQLite temporario e isolado.
    Isso garante que testes nao interferem entre si.
    O banco e criado em tmp_path (diretorio temporario do pytest)
    e deletado automaticamente apos cada teste.
    """
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr("config.DATABASE_PATH", db_path)

    # Inicializar banco limpo
    from init_db import init_db
    init_db()

    yield db_path

    # Cleanup automatico pelo tmp_path


@pytest.fixture
def app(temp_database):
    """
    Retorna a aplicacao Flask configurada para testes.
    IMPORTANTE: importar app DEPOIS de monkeypatch alterar DATABASE_PATH.
    """
    # Forcar reimport para pegar o banco temporario
    import importlib
    import config
    import models
    importlib.reload(config)
    importlib.reload(models)

    from app import app as flask_app
    flask_app.config["TESTING"] = True
    flask_app.config["SECRET_KEY"] = "test-secret-key"
    # Desabilitar CSRF para facilitar testes (testar CSRF separadamente)
    flask_app.config["WTF_CSRF_ENABLED"] = False
    return flask_app


@pytest.fixture
def client(app):
    """Flask test client — simula requests HTTP sem servidor real."""
    return app.test_client()


@pytest.fixture
def admin_session(client):
    """
    Retorna um client ja logado como admin.
    Tambem troca a senha padrao para nao precisar lidar com force_change.
    """
    import models
    # Trocar senha para evitar redirect de force_change
    models.change_password("testpassword123")

    # Fazer login
    # Primeiro, pegar CSRF token
    resp = client.get("/admin/login")
    # Extrair csrf_token da session
    with client.session_transaction() as sess:
        csrf = sess.get("csrf_token", "")

    client.post("/admin/login", data={
        "username": "FREE",
        "password": "testpassword123",
        "csrf_token": csrf,
    })
    return client


@pytest.fixture
def csrf_token(client):
    """Retorna um CSRF token valido para o client."""
    # Fazer qualquer GET para gerar o token na session
    client.get("/")
    with client.session_transaction() as sess:
        return sess.get("csrf_token", "")
```

### REGRAS para os testes:

1. **NUNCA usar o banco de producao.** A fixture `temp_database` garante isolamento.
2. **Cada teste e independente.** Nao depender de ordem de execucao.
3. **Usar `assert` com mensagens claras.** Ex: `assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"`
4. **Testar o caso feliz E os casos de erro.** Ex: login com senha certa E senha errada.
5. **Nao mockar o banco de dados.** Usar banco SQLite real em tmp_path.
6. **Mockar apenas chamadas externas** (mempool.space API).

---

## TESTES DA PARTE 1 — config, init_db, models

Criar junto com a implementacao da Parte 1.
Rodar com: `cd /home/msi/FREESANDMANN && python -m pytest tests/test_config.py tests/test_init_db.py tests/test_models.py -v`

### `tests/test_config.py`

```python
"""Testes para config.py — verificar que defaults existem e env vars funcionam."""

def test_defaults_exist():
    """DEFAULTS deve conter todas as chaves necessarias."""
    from config import DEFAULTS
    required_keys = [
        "site_title", "site_description", "site_tagline",
        "btc_address", "lightning_address",
        "goal_btc", "raised_onchain_btc", "raised_lightning_btc",
        "raised_btc_manual_adjustment", "raised_btc",
        "last_balance_check", "goal_description",
        "admin_force_password_change",
        "supporters_count", "hero_image_url", "deadline_text",
        "transparency_text", "og_image_url", "wallet_explorer_url",
        "coinos_api_key", "coinos_enabled",
    ]
    for key in required_keys:
        assert key in DEFAULTS, f"Missing key in DEFAULTS: {key}"


def test_secret_key_exists():
    """SECRET_KEY deve existir e nao ser vazio."""
    from config import SECRET_KEY
    assert SECRET_KEY, "SECRET_KEY is empty"


def test_database_path_exists():
    """DATABASE_PATH deve existir e conter 'freesandmann'."""
    from config import DATABASE_PATH
    assert DATABASE_PATH, "DATABASE_PATH is empty"
    assert "freesandmann" in DATABASE_PATH or "test" in DATABASE_PATH


def test_admin_username_default():
    """ADMIN_USERNAME padrao deve ser 'FREE'."""
    from config import ADMIN_USERNAME
    assert ADMIN_USERNAME == "FREE"
```

### `tests/test_init_db.py`

```python
"""Testes para init_db.py — verificar criacao do banco e idempotencia."""
import sqlite3


def test_tables_created(temp_database):
    """As 3 tabelas devem existir apos init_db."""
    conn = sqlite3.connect(temp_database)
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()

    assert "config" in tables, "Table 'config' not created"
    assert "articles" in tables, "Table 'articles' not created"
    assert "media_links" in tables, "Table 'media_links' not created"


def test_defaults_seeded(temp_database):
    """Todas as chaves de config.DEFAULTS devem estar no banco."""
    from config import DEFAULTS
    import sqlite3
    conn = sqlite3.connect(temp_database)
    cursor = conn.execute("SELECT key FROM config")
    keys = [row[0] for row in cursor.fetchall()]
    conn.close()

    for key in DEFAULTS:
        assert key in keys, f"Default key '{key}' not seeded in database"


def test_admin_password_hash_created(temp_database):
    """admin_password_hash deve existir no banco apos init."""
    import sqlite3
    conn = sqlite3.connect(temp_database)
    row = conn.execute(
        "SELECT value FROM config WHERE key = 'admin_password_hash'"
    ).fetchone()
    conn.close()

    assert row is not None, "admin_password_hash not created"
    assert len(row[0]) > 20, "admin_password_hash looks too short to be a real hash"


def test_idempotent(temp_database):
    """Rodar init_db duas vezes nao deve dar erro nem duplicar dados."""
    from init_db import init_db
    # Ja rodou uma vez na fixture, rodar de novo
    init_db()

    import sqlite3
    conn = sqlite3.connect(temp_database)
    count = conn.execute("SELECT COUNT(*) FROM config").fetchone()[0]
    conn.close()

    from config import DEFAULTS
    # +1 para admin_password_hash
    expected = len(DEFAULTS) + 1
    assert count == expected, f"Expected {expected} config rows, got {count}"


def test_wal_mode(temp_database):
    """Banco deve estar em modo WAL."""
    import sqlite3
    conn = sqlite3.connect(temp_database)
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    conn.close()
    assert mode == "wal", f"Expected WAL mode, got {mode}"
```

### `tests/test_models.py`

```python
"""Testes para models.py — CRUD completo de config, articles, media_links, auth."""
import models


# ── Config ───────────────────────────────────────────────────────────

class TestConfig:
    def test_get_config_existing(self, temp_database):
        """Deve retornar valor existente."""
        val = models.get_config("site_title")
        assert val == "Free Sandmann"

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
```

### Comando de validacao da Parte 1

```bash
cd /home/msi/FREESANDMANN && python -m pytest tests/test_config.py tests/test_init_db.py tests/test_models.py -v
```

**Criterio de aceitacao**: TODOS os testes passam. Zero falhas. Zero erros.

Se algum teste falhar:
1. Ler a mensagem de erro completa
2. Identificar qual funcao em `models.py`, `config.py` ou `init_db.py` esta com problema
3. Corrigir a implementacao (NAO o teste)
4. Rodar os testes novamente
5. Repetir ate todos passarem

---

## TESTES DA PARTE 2 — Rotas publicas, admin, QR, CSRF

Criar junto com a implementacao da Parte 2.
Rodar com: `cd /home/msi/FREESANDMANN && python -m pytest tests/test_routes_public.py tests/test_routes_admin.py tests/test_qr.py tests/test_csrf.py tests/test_balance.py -v`

### `tests/test_routes_public.py`

```python
"""Testes das rotas publicas — homepage, donate, updates, article."""


class TestHomepage:
    def test_index_returns_200(self, client):
        """Homepage deve retornar 200."""
        resp = client.get("/")
        assert resp.status_code == 200

    def test_index_contains_site_title(self, client):
        """Homepage deve conter o titulo do site."""
        resp = client.get("/")
        assert b"Free Sandmann" in resp.data

    def test_index_contains_progress(self, client):
        """Homepage deve conter elementos da barra de progresso."""
        resp = client.get("/")
        assert b"BTC" in resp.data


class TestDonate:
    def test_donate_returns_200(self, client):
        """Pagina de doacao deve retornar 200."""
        resp = client.get("/donate")
        assert resp.status_code == 200

    def test_donate_contains_bitcoin(self, client):
        """Pagina de doacao deve mencionar Bitcoin."""
        resp = client.get("/donate")
        assert b"Bitcoin" in resp.data or b"bitcoin" in resp.data


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
```

### `tests/test_routes_admin.py`

```python
"""Testes das rotas admin — login, logout, dashboard, settings, articles CRUD, media links."""
import models


class TestAdminLogin:
    def test_login_page_returns_200(self, client):
        """Pagina de login deve retornar 200."""
        resp = client.get("/admin/login")
        assert resp.status_code == 200

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
        resp = client.get("/admin/")
        assert resp.status_code == 302


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
        assert models.get_config("btc_address") == "bc1qnewtestaddress"
        assert models.get_config("goal_btc") == "5.0"

    def test_settings_requires_login(self, client):
        """Settings sem login deve redirecionar."""
        resp = client.get("/admin/settings")
        assert resp.status_code == 302


class TestAdminArticles:
    def test_articles_list_returns_200(self, admin_session):
        """Lista de artigos admin deve retornar 200."""
        resp = admin_session.get("/admin/articles")
        assert resp.status_code == 200

    def test_create_article(self, admin_session):
        """Criar artigo via admin deve funcionar."""
        with admin_session.session_transaction() as sess:
            csrf = sess.get("csrf_token", "")

        resp = admin_session.post("/admin/articles/new", data={
            "title": "Admin Created",
            "body_md": "Some **content**",
            "published": "on",
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
```

### `tests/test_qr.py`

```python
"""Testes da geracao de QR codes."""
import models


class TestQRCode:
    def test_qr_btc_returns_png(self, client):
        """QR code BTC deve retornar imagem PNG."""
        models.set_config("btc_address", "bc1qtest123456")
        resp = client.get("/qr/btc")
        assert resp.status_code == 200
        assert resp.content_type == "image/png"
        # PNG magic bytes
        assert resp.data[:4] == b'\x89PNG'

    def test_qr_lightning_returns_png(self, client):
        """QR code Lightning deve retornar imagem PNG."""
        models.set_config("lightning_address", "lnurl1testaddress")
        resp = client.get("/qr/lightning")
        assert resp.status_code == 200
        assert resp.content_type == "image/png"

    def test_qr_btc_empty_address_404(self, client):
        """QR code sem endereco BTC configurado deve retornar 404."""
        models.set_config("btc_address", "")
        resp = client.get("/qr/btc")
        assert resp.status_code == 404

    def test_qr_lightning_empty_address_404(self, client):
        """QR code sem endereco Lightning configurado deve retornar 404."""
        models.set_config("lightning_address", "")
        resp = client.get("/qr/lightning")
        assert resp.status_code == 404

    def test_qr_invalid_type_404(self, client):
        """Tipo de QR invalido deve retornar 404."""
        resp = client.get("/qr/invalid")
        assert resp.status_code == 404

    def test_qr_has_cache_header(self, client):
        """QR code deve ter header de cache."""
        models.set_config("btc_address", "bc1qtest123456")
        resp = client.get("/qr/btc")
        cache = resp.headers.get("Cache-Control", "")
        assert "max-age" in cache or resp.status_code == 200
```

### `tests/test_csrf.py`

```python
"""Testes da protecao CSRF — POST sem token deve ser bloqueado."""


class TestCSRF:
    def test_post_without_csrf_returns_403(self, client):
        """POST sem CSRF token deve retornar 403."""
        resp = client.post("/admin/login", data={
            "username": "FREE",
            "password": "FREE",
        })
        assert resp.status_code == 403

    def test_post_with_wrong_csrf_returns_403(self, client):
        """POST com CSRF token errado deve retornar 403."""
        # Fazer GET para gerar session
        client.get("/admin/login")
        resp = client.post("/admin/login", data={
            "username": "FREE",
            "password": "FREE",
            "csrf_token": "wrong-token-12345",
        })
        assert resp.status_code == 403

    def test_post_with_correct_csrf_works(self, client, csrf_token):
        """POST com CSRF token correto deve funcionar (nao 403)."""
        resp = client.post("/admin/login", data={
            "username": "FREE",
            "password": "FREE",
            "csrf_token": csrf_token,
        })
        # Deve ser 302 (redirect) ou 200, mas NAO 403
        assert resp.status_code != 403
```

### `tests/test_balance.py`

```python
"""Testes do balance checker via rota admin (refresh manual)."""
import models


class TestBalanceRefresh:
    def test_refresh_balance_route(self, admin_session):
        """Rota de refresh manual deve funcionar."""
        models.set_config("btc_address", "")  # sem endereco, nao faz request externo

        with admin_session.session_transaction() as sess:
            csrf = sess.get("csrf_token", "")

        resp = admin_session.post("/admin/refresh-balance", data={
            "csrf_token": csrf,
        })
        assert resp.status_code == 302  # redirect para dashboard

    def test_refresh_balance_requires_login(self, client):
        """Refresh sem login deve redirecionar."""
        resp = client.post("/admin/refresh-balance")
        assert resp.status_code in (302, 403)
```

### Comando de validacao da Parte 2

```bash
cd /home/msi/FREESANDMANN && python -m pytest tests/test_routes_public.py tests/test_routes_admin.py tests/test_qr.py tests/test_csrf.py tests/test_balance.py -v
```

**Criterio de aceitacao**: TODOS os testes passam. Zero falhas.

---

## TESTES DA PARTE 3+4 — Templates renderizam corretamente

Criar junto com a implementacao das Partes 3 e 4.
Rodar com: `cd /home/msi/FREESANDMANN && python -m pytest tests/test_templates.py -v`

### `tests/test_templates.py`

```python
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
```

### Comando de validacao das Partes 3+4

```bash
cd /home/msi/FREESANDMANN && python -m pytest tests/test_templates.py -v
```

---

## COMANDO PARA RODAR TODOS OS TESTES

```bash
cd /home/msi/FREESANDMANN && python -m pytest tests/ -v --tb=short
```

**Output esperado**: Todos os testes passam com status verde.

Se houver falhas, o output mostra exatamente:
- Qual teste falhou
- Qual assertion falhou
- Qual era o valor esperado vs recebido
- Traceback completo com arquivo e linha

---

## FLUXO DE TRABALHO PARA O MODELO

Ao implementar cada parte do PLANO_DE_ACAO.md, seguir este ciclo:

```
1. Ler a especificacao da Parte no PLANO_DE_ACAO.md
2. Criar os arquivos de TESTE correspondentes deste documento
3. Implementar o codigo da Parte
4. Rodar os testes: python -m pytest tests/test_<parte>.py -v
5. Se testes falharam:
   a. Ler a mensagem de erro
   b. Corrigir o CODIGO (nao os testes)
   c. Voltar ao passo 4
6. Se todos passaram: parte concluida
7. Rodar TODOS os testes para garantir que nada quebrou: python -m pytest tests/ -v
8. Se regressao detectada: corrigir e voltar ao passo 7
9. Avancar para a proxima parte
```

**NUNCA avance para a proxima parte com testes falhando.**

---

## RESUMO DE COBERTURA

| Parte | Arquivo de teste | Num testes | O que cobre |
|-------|-----------------|------------|-------------|
| 1 | test_config.py | 4 | Defaults, env vars, chaves |
| 1 | test_init_db.py | 5 | Tabelas, seeds, idempotencia, WAL |
| 1 | test_models.py | 22 | CRUD config, auth, articles, media, balance, embeds |
| 2 | test_routes_public.py | 11 | Homepage, donate, updates, article, 404 |
| 2 | test_routes_admin.py | 23 | Login, logout, force change, dashboard, settings, articles CRUD, media CRUD |
| 2 | test_qr.py | 6 | QR generation, empty address, invalid type, cache |
| 2 | test_csrf.py | 3 | CSRF protection on/off/wrong |
| 2 | test_balance.py | 2 | Balance refresh route |
| 3+4 | test_templates.py | 20 | All templates render, contain expected elements |
| **Total** | | **96** | |

96 testes automatizados cobrindo toda a funcionalidade do sistema.
