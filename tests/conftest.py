import os
import sys

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

    PBKDF2 iterations sao reduzidas APENAS aqui para acelerar testes.
    Em producao, werkzeug usa o default (1_000_000 iterations).
    """
    db_path = str(tmp_path / "test.db")
    monkeypatch.setenv("DATABASE_PATH", db_path)
    monkeypatch.setattr("config.DATABASE_PATH", db_path)

    # Acelerar hashing de senha apenas em testes (producao nao e afetada)
    # Werkzeug >= 2.3 usa scrypt por padrao (n=32768), que e lento.
    # Substituimos por pbkdf2 com 1 iteracao APENAS no ambiente de teste.
    # monkeypatch reverte automaticamente apos cada teste.
    import werkzeug.security
    _original = werkzeug.security.generate_password_hash
    monkeypatch.setattr(
        werkzeug.security,
        "generate_password_hash",
        lambda pw, **kw: _original(pw, method="pbkdf2:sha256:1"),
    )

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
    import models
    models.set_config("setup_complete", "1")
    return app.test_client()


@pytest.fixture
def fresh_client(app):
    """Client com install fresca, antes do setup inicial ser concluido."""
    import models
    models.set_config("setup_complete", "0")
    return app.test_client()


@pytest.fixture
def admin_session(client):
    """
    Retorna um client ja logado como admin.
    Tambem troca a senha padrao para nao precisar lidar com force_change.
    """
    import models
    models.set_config("setup_complete", "1")
    # Trocar senha para evitar redirect de force_change
    models.change_password("testpassword123")

    # Fazer login
    resp = client.get("/admin/login")
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
    import models
    models.set_config("setup_complete", "1")
    client.get("/")
    with client.session_transaction() as sess:
        return sess.get("csrf_token", "")


@pytest.fixture
def lawyer_session(client):
    """
    Retorna um client ja logado como advogado.
    Cria conta, troca senha, e faz login.
    """
    import models
    models.set_config("setup_complete", "1")
    models.create_lawyer("drsilva", "Dr. Silva", "TempPass123!")
    lawyer = models.get_lawyer_by_username("drsilva")
    models.change_lawyer_password(lawyer["id"], "permanent_pass_123")

    resp = client.get("/advogado/login")
    with client.session_transaction() as sess:
        csrf = sess.get("csrf_token", "")

    client.post("/advogado/login", data={
        "username": "drsilva",
        "password": "permanent_pass_123",
        "csrf_token": csrf,
    })
    return client
