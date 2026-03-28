# FREESANDMANN

Plataforma self-hosted de arrecadacao via Bitcoin para defesa juridica.
Stack: Flask + Jinja2 + SQLite, deploy em producao com Docker.

## Idioma

- O usuario (Vinicius) se comunica em portugues brasileiro informal.
- Responda sempre em PT-BR, exceto em codigo, commits e docstrings (ingles).

## Convencoes de codigo

- Python 3, Flask app em `app.py`.
- Testes em `tests/` com pytest. Rodar: `pytest tests/ -v`
- Commits em ingles, formato conventional commits (`feat:`, `fix:`, `docs:`, etc.)
- Banco de dados SQLite local (`data/*.db`), nunca versionar.

## Arquitetura: roles e acesso

- **Admin** (Vinicius): acesso total, pode publicar sem aprovacao do advogado.
- **Advogado**: role restrito com rotas em `/advogado/`. Pode revisar e aprovar artigos,
  mas NAO tem acesso a wallet, Bitcoin ou configuracoes financeiras.
  Nao pode publicar sozinho — apenas aprovar.
- O admin mantem poder de override (liberdade de expressao).

## i18n

- Site bilingue PT/EN, deteccao automatica de idioma.
- Copia de campanha localizada nas configuracoes do admin.

## Ambiente de desenvolvimento

- Virtualenv: `python3 -m venv venv && source venv/bin/activate`
- Instalar deps: `pip install -r requirements.txt`
- Inicializar DB: `python3 init_db.py`
- Rodar app: `python3 app.py`
- Nos testes, password hashing usa custo reduzido para performance.
