# BASTION

Projeto Bastion: plataforma self-hosted de arrecadacao via Bitcoin para defesa juridica.
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

- Site trilingue: PT (default), EN, DE.
- Deteccao: `session['lang']` → `Accept-Language` → fallback `en`.
- Campos localizados: `{field}_en`, `{field}_de` (artigos e config de campanha).
- Strings de UI em `translations/{pt,en,de}.json`.
- Copia de campanha localizada nas configuracoes do admin.

## Padrao arquitetural

- Camadas: `routes_*.py` (handlers finos) → `service_*.py` (logica) → `model_*.py` (dados/SQL).
- `app_auth.py`: decorators de autenticacao admin/advogado.
- `app_hooks.py`: request hooks (CSRF, idioma) e context processors.
- `app_background.py`: thread de manutencao (balance checker via mempool.space).
- `coinos_client.py`: client da API Coinos (Lightning/Liquid/onchain).
- Detalhes completos em `ARCHITECTURE.md`.

## Integracoes externas

- **Coinos.io**: invoices Lightning e Liquid, webhook de pagamento, onchain opcional.
  Config via admin: `coinos_api_key`, `coinos_enabled`, `coinos_webhook_secret`.
- **mempool.space**: balance check onchain automatico a cada 5 min.
- **Liquid Network**: suporte opcional (`liquid_enabled`, `liquid_address`).

## Deploy

- Producao: `docker compose up -d` (porta host 4040 → container 8000).
- Gunicorn com `preload_app=True`, background loop no master process.
- Volume persistente para `data/` (SQLite).
- Proxy/SSL: Cloudflare Tunnel (sem portas abertas).
- Env vars de producao: `SECRET_KEY`, `DATABASE_PATH`, `ADMIN_USERNAME`.

## Seguranca

- CSRF em todos os POSTs (exceto webhook Coinos).
- Rate limit por IP no login (5 tentativas → lockout 5 min), SQLite-backed.
- Senha admin/advogado: werkzeug PBKDF2. Force password change no primeiro login.

## Ambiente de desenvolvimento

- Virtualenv: `python3 -m venv venv && source venv/bin/activate`
- Instalar deps: `pip install -r requirements.txt`
- Inicializar DB: `python3 init_db.py`
- Rodar app: `python3 app.py`
- Nos testes, password hashing usa custo reduzido para performance.
