# PLANO DE ACAO — Free Sandmann

Documento operacional dividido em partes independentes.
Cada parte pode ser executada por um modelo leve de forma isolada.
Leia ARCHITECTURE.md para contexto completo antes de comecar qualquer parte.

**Regras gerais para todas as partes:**
- Diretorio raiz do projeto: `/home/msi/FREESANDMANN/`
- Python 3.12, Flask, SQLite, Jinja2, Pico CSS
- Sem frameworks JS. Sem npm. Sem build step.
- Todos os arquivos usam UTF-8, sem BOM
- Sem emojis no codigo (somente no conteudo de usuario se necessario)
- Cada arquivo criado deve ser completo e funcional ao final da parte
- Consulte ARCHITECTURE.md para decisoes de design, schema, rotas e wireframes
- **TESTES SAO OBRIGATORIOS**: Leia PLANO_DE_TESTES.md. Cada parte tem testes correspondentes.
  O ciclo e: criar testes → implementar codigo → rodar testes → corrigir ate passar → avancar.
  NUNCA avance para a proxima parte com testes falhando.
- Adicionar `pytest==8.3.4` ao requirements.txt na Parte 1
- Criar `tests/conftest.py` (fixtures) ANTES de qualquer teste — ver PLANO_DE_TESTES.md

---

## PARTE 1 — Fundacao: config, banco de dados e models

**Objetivo**: Criar os 4 arquivos base que todo o resto depende.
**Arquivos a criar**: `requirements.txt`, `config.py`, `init_db.py`, `models.py`
**Dependencias**: Nenhuma (esta e a primeira parte)
**Criar diretorio**: `data/` (vazio, mount point para Docker)

### 1.1 — `requirements.txt`

Criar em `/home/msi/FREESANDMANN/requirements.txt`:

```
Flask==3.1.0
gunicorn==23.0.0
python-qrcode[pil]==8.0
Pillow==11.1.0
markdown==3.7
Werkzeug==3.1.3
```

### 1.2 — `config.py`

Criar em `/home/msi/FREESANDMANN/config.py`.

Responsabilidade: carregar variaveis de ambiente e definir valores padrao.

```python
import os

SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-production-please")
DATABASE_PATH = os.environ.get("DATABASE_PATH", os.path.join(os.path.dirname(__file__), "data", "freesandmann.db"))
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "FREE")
```

Dicionario `DEFAULTS` com TODAS as chaves do config que serao inseridas no banco na primeira inicializacao:

```python
DEFAULTS = {
    "site_title": "Free Sandmann",
    "site_description": "Help me fight injustice. I am being wrongfully accused and need your support to pay for legal defense.",
    "site_tagline": "Justice needs funding",
    "btc_address": "",
    "lightning_address": "",
    "goal_btc": "1.0",
    "raised_onchain_btc": "0.0",
    "raised_lightning_btc": "0.0",
    "raised_btc_manual_adjustment": "0.0",
    "raised_btc": "0.0",
    "last_balance_check": "",
    "goal_description": "Legal defense fund",
    "admin_force_password_change": "1",
    "supporters_count": "0",
    "hero_image_url": "",
    "deadline_text": "",
    "transparency_text": "",
    "og_image_url": "",
    "wallet_explorer_url": "",
    "coinos_api_key": "",
    "coinos_enabled": "0",
}
```

### 1.3 — `init_db.py`

Criar em `/home/msi/FREESANDMANN/init_db.py`.

Responsabilidade: criar tabelas e popular dados padrao. Deve ser **idempotente** (seguro rodar varias vezes).

Funcao `init_db()`:
1. Criar diretorio `data/` se nao existir (`os.makedirs`)
2. Conectar ao SQLite no caminho `DATABASE_PATH`
3. Habilitar `PRAGMA journal_mode=WAL`
4. Criar 3 tabelas com `CREATE TABLE IF NOT EXISTS`:

**Tabela `config`**:
```sql
CREATE TABLE IF NOT EXISTS config (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

**Tabela `articles`**:
```sql
CREATE TABLE IF NOT EXISTS articles (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    title      TEXT NOT NULL,
    slug       TEXT UNIQUE NOT NULL,
    body_md    TEXT NOT NULL,
    body_html  TEXT NOT NULL,
    published  INTEGER DEFAULT 1,
    pinned     INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);
```

**Tabela `media_links`**:
```sql
CREATE TABLE IF NOT EXISTS media_links (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    title      TEXT NOT NULL,
    url        TEXT NOT NULL,
    link_type  TEXT NOT NULL DEFAULT 'article',
    created_at TEXT DEFAULT (datetime('now'))
);
```

5. Iterar sobre `config.DEFAULTS` e inserir com `INSERT OR IGNORE` (nao sobrescreve se ja existir)
6. Verificar se `admin_password_hash` existe no config. Se NAO existir, gerar hash de "FREE" com `werkzeug.security.generate_password_hash("FREE")` e inserir
7. Commit e close
8. Print mensagem de sucesso
9. `if __name__ == "__main__": init_db()`

### 1.4 — `models.py`

Criar em `/home/msi/FREESANDMANN/models.py`.

Responsabilidade: TODAS as queries SQL do projeto. Nenhum outro arquivo deve fazer SQL diretamente.

**Funcao helper**:
- `get_db()` — conectar ao SQLite, `row_factory = sqlite3.Row`, habilitar WAL, retornar conexao

**Funcoes de Config**:
- `get_config(key, default="")` — retorna valor de uma chave ou default
- `get_all_config()` — retorna dict com todas as chaves
- `set_config(key, value)` — INSERT OR UPDATE (usar `ON CONFLICT(key) DO UPDATE SET value = ?`)

**Funcoes de Auth**:
- `verify_password(password)` — le hash do config, retorna `check_password_hash(hash, password)`
- `change_password(new_password)` — gera novo hash, salva no config, seta `admin_force_password_change` para "0"
- `must_change_password()` — retorna `True` se `admin_force_password_change == "1"`

**Funcoes de Articles**:
- `_make_slug(title)` — converte titulo para slug URL-safe (lowercase, espacos viram hifens, remove caracteres especiais)
- `_render_markdown(text)` — converte Markdown para HTML usando `markdown.markdown(text, extensions=["extra", "nl2br", "sane_lists"])`, depois passa por `_auto_embed()`
- `_auto_embed(html)` — regex para auto-converter URLs:
  - YouTube (`youtube.com/watch?v=XXX` ou `youtu.be/XXX`) → iframe embed (usar `youtube-nocookie.com`)
  - Twitter/X (`twitter.com/user/status/XXX` ou `x.com/user/status/XXX`) → blockquote + widget JS
  - IMPORTANTE: nao converter URLs que ja estao dentro de atributos HTML (href="...", src="..."). Usar lookbehind negativo `(?<!["=])` no regex
- `get_articles(published_only=True)` — SELECT com ORDER BY `pinned DESC, created_at DESC`
- `get_article_by_slug(slug)` — SELECT WHERE slug
- `get_article_by_id(article_id)` — SELECT WHERE id
- `create_article(title, body_md, published=1, pinned=0)` — gera slug, renderiza HTML, INSERT. Se slug ja existir, adicionar timestamp ao slug
- `update_article(article_id, title, body_md, published=1, pinned=0)` — gera slug, renderiza HTML, UPDATE, seta `updated_at=datetime('now')`
- `delete_article(article_id)` — DELETE WHERE id

**Funcoes de Media Links**:
- `get_media_links()` — SELECT ORDER BY created_at DESC
- `add_media_link(title, url, link_type="article")` — INSERT
- `delete_media_link(link_id)` — DELETE WHERE id

**Funcao de Balance Check**:
- `check_onchain_balance()` — consulta mempool.space API:
  1. Ler `btc_address` do config. Se vazio, retornar sem fazer nada
  2. Fazer GET em `https://mempool.space/api/address/{address}` com `urllib.request.urlopen(url, timeout=10)`
  3. Parsear JSON, pegar `data["chain_stats"]["funded_txo_sum"]` (satoshis totais recebidos)
  4. Converter para BTC: `funded / 100_000_000`
  5. Atualizar `raised_onchain_btc` no config
  6. Recalcular total: `raised_btc = raised_onchain_btc + raised_lightning_btc + raised_btc_manual_adjustment`
  7. Atualizar `raised_btc` e `last_balance_check` (datetime ISO)
  8. Envolver tudo em try/except — se falhar, nao fazer nada (manter ultimo valor)
- `recalculate_raised_btc()` — funcao separada para recalcular o total a partir dos componentes (util quando admin atualiza valor manual)

### 1.5 — Criar diretorio `data/`

```bash
mkdir -p /home/msi/FREESANDMANN/data
```

### Validacao da Parte 1

Apos criar todos os arquivos, rodar:
```bash
cd /home/msi/FREESANDMANN
pip install -r requirements.txt
python init_db.py
python -c "import models; print(models.get_all_config())"
```

Deve imprimir um dicionario com todas as chaves do config e seus valores padrao.

---

## PARTE 2 — Aplicacao Flask: rotas publicas + QR + balance checker

**Objetivo**: Criar `app.py` com todas as rotas publicas, geracao de QR codes, e background task do balance checker.
**Arquivos a criar**: `app.py`
**Dependencias**: Parte 1 completa (config.py, init_db.py, models.py existem)

### 2.1 — Estrutura do `app.py`

Criar em `/home/msi/FREESANDMANN/app.py`.

**Imports necessarios**:
```python
import io
import os
import time
import functools
import threading
import json
from collections import defaultdict
from datetime import datetime

import qrcode
from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, abort, send_file,
)

import config
import models
from init_db import init_db
```

**Inicializacao**:
```python
app = Flask(__name__)
app.secret_key = config.SECRET_KEY

# Inicializar banco na startup
init_db()
```

### 2.2 — Rate Limiting (em memoria)

Implementar no topo do app.py, logo apos a inicializacao:

```python
_login_attempts = defaultdict(list)  # ip -> [timestamps]
MAX_ATTEMPTS = 5
LOCKOUT_SECONDS = 300
```

Duas funcoes:
- `_is_rate_limited(ip)` — filtra timestamps antigos (> LOCKOUT_SECONDS), retorna True se len >= MAX_ATTEMPTS
- `_record_attempt(ip)` — append timestamp atual

### 2.3 — Protecao CSRF

Dois `@app.before_request`:

1. **`csrf_protect()`**: Se metodo == POST, comparar `session["csrf_token"]` com `request.form.get("csrf_token")`. Se nao bater, `abort(403)`.
2. **`generate_csrf_token()`**: Se `csrf_token` nao existe na session, gerar com `os.urandom(16).hex()`.

### 2.4 — Decorator `login_required`

```python
def login_required(f):
    @functools.wraps(f)
    def wrapped(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("admin_login"))
        if models.must_change_password() and request.endpoint != "admin_change_password":
            flash("You must change your password before continuing.", "warning")
            return redirect(url_for("admin_change_password"))
        return f(*args, **kwargs)
    return wrapped
```

### 2.5 — Context Processor

```python
@app.context_processor
def inject_config():
    cfg = models.get_all_config()
    return {"cfg": cfg}
```

Isso torna `cfg` disponivel em TODOS os templates automaticamente.

### 2.6 — Rotas Publicas

**GET `/`** (index):
- Buscar artigos publicados: `models.get_articles(published_only=True)`
- Filtrar pinned: `[a for a in articles if a["pinned"]]`
- Buscar media links: `models.get_media_links()`
- Renderizar `index.html` passando `articles`, `pinned`, `media_links`

**GET `/donate`**:
- Renderizar `donate.html` (sem dados extras — cfg ja injetado pelo context processor)

**GET `/updates`**:
- Buscar artigos publicados
- Renderizar `articles.html` passando `articles`

**GET `/updates/<slug>`**:
- Buscar artigo por slug: `models.get_article_by_slug(slug)`
- Se nao encontrar, `abort(404)`
- Renderizar `article.html` passando `article`

**GET `/qr/<qr_type>`**:
- Se `qr_type == "btc"`: data = `f"bitcoin:{models.get_config('btc_address')}"`
- Se `qr_type == "lightning"`: data = `models.get_config("lightning_address")`
- Se outro valor ou data vazio: `abort(404)`
- Gerar QR: `qrcode.make(data, box_size=8, border=2)`
- Salvar em `io.BytesIO()`, format PNG
- Retornar com `send_file(buf, mimetype="image/png", max_age=3600)`

### 2.7 — Background Task: Balance Checker

Usar `threading.Timer` para rodar `models.check_onchain_balance()` a cada 3600 segundos:

```python
def _start_balance_checker():
    """Roda check_onchain_balance a cada 1 hora em background."""
    def _run():
        models.check_onchain_balance()
        # Reagendar
        t = threading.Timer(3600, _run)
        t.daemon = True
        t.start()
    # Primeira execucao apos 10 segundos (dar tempo do app inicializar)
    t = threading.Timer(10, _run)
    t.daemon = True
    t.start()

_start_balance_checker()
```

IMPORTANTE: threads daemon morrem quando o processo principal morre — nao ficam orfas.

### 2.8 — Rotas Admin

**GET/POST `/admin/login`**:
- Se ja logado (`session.get("admin")`), redirecionar para dashboard
- POST: verificar rate limit, validar username (`config.ADMIN_USERNAME`) e senha (`models.verify_password`)
- Se correto: `session["admin"] = True`, limpar attempts, redirecionar (para change_password se necessario, senao dashboard)
- Se errado: `_record_attempt(ip)`, flash erro
- GET: renderizar `admin/login.html`

**GET `/admin/logout`**:
- `session.pop("admin", None)`
- Redirecionar para index

**GET `/admin/`** (dashboard) — `@login_required`:
- Buscar artigos (todos): `models.get_articles(published_only=False)`
- Buscar media links: `models.get_media_links()`
- Renderizar `admin/dashboard.html`

**GET/POST `/admin/change-password`** — `@login_required`:
- POST: validar nova senha (minimo 8 chars, != "FREE", confirmacao bate)
- Se valido: `models.change_password(new_pw)`, flash sucesso, redirecionar dashboard
- Se invalido: flash erro
- GET: renderizar `admin/change_password.html`

**GET/POST `/admin/settings`** — `@login_required`:
- POST: ler campos do form e salvar cada um com `models.set_config()`:
  - Campos: `site_title`, `site_description`, `site_tagline`, `btc_address`, `lightning_address`, `goal_btc`, `raised_lightning_btc`, `raised_btc_manual_adjustment`, `goal_description`, `supporters_count`, `hero_image_url`, `deadline_text`, `transparency_text`, `og_image_url`, `wallet_explorer_url`
  - Apos salvar, chamar `models.recalculate_raised_btc()` para recalcular o total
- Flash sucesso, redirecionar para settings
- GET: renderizar `admin/settings.html`

**GET `/admin/articles`** — `@login_required`:
- Buscar todos artigos: `models.get_articles(published_only=False)`
- Renderizar `admin/articles.html`

**GET/POST `/admin/articles/new`** — `@login_required`:
- POST: ler title, body_md, published (checkbox), pinned (checkbox)
- Validar title nao vazio
- Criar: `models.create_article(title, body_md, published, pinned)`
- Flash sucesso, redirecionar para admin_articles
- GET: renderizar `admin/article_form.html` com `article=None`

**GET/POST `/admin/articles/<int:article_id>/edit`** — `@login_required`:
- Buscar artigo por id. Se nao existir, `abort(404)`
- POST: ler campos, validar, `models.update_article(...)`
- Flash sucesso, redirecionar para admin_articles
- GET: renderizar `admin/article_form.html` com `article=article`

**POST `/admin/articles/<int:article_id>/delete`** — `@login_required`:
- `models.delete_article(article_id)`
- Flash sucesso, redirecionar para admin_articles

**GET/POST `/admin/media-links`** — `@login_required`:
- POST: ler title, url, link_type. Validar nao vazios. `models.add_media_link(...)`
- Flash sucesso, redirecionar
- GET: buscar links, renderizar `admin/media_links.html`

**POST `/admin/media-links/<int:link_id>/delete`** — `@login_required`:
- `models.delete_media_link(link_id)`
- Flash sucesso, redirecionar

**POST `/admin/refresh-balance`** — `@login_required`:
- Chamar `models.check_onchain_balance()`
- Flash sucesso (ou erro se falhou)
- Redirecionar para dashboard

### 2.9 — Error Handlers

```python
@app.errorhandler(404)
def not_found(e):
    return render_template("error.html", code=404, message="Page not found"), 404

@app.errorhandler(403)
def forbidden(e):
    return render_template("error.html", code=403, message="Forbidden"), 403
```

### 2.10 — Bloco main

```python
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8000)
```

### Validacao da Parte 2

Nao da para testar sem templates (Parte 3), mas verificar que o arquivo importa sem erro:
```bash
cd /home/msi/FREESANDMANN
python -c "import app; print('OK — rotas:', [r.rule for r in app.app.url_map.iter_rules()])"
```

---

## PARTE 3 — Templates publicos (base + index + donate + articles + error)

**Objetivo**: Criar todos os templates HTML que o visitante ve.
**Arquivos a criar**: 7 arquivos em `templates/` e `templates/components/`
**Dependencias**: Partes 1 e 2 completas
**Criar diretorios**:
```bash
mkdir -p /home/msi/FREESANDMANN/templates/components
mkdir -p /home/msi/FREESANDMANN/templates/admin
```

### REGRAS DE DESIGN (aplicar em TODOS os templates):

1. **Pico CSS via CDN**: `<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.min.css">`
2. **Tema dark**: `<html data-theme="dark">`
3. **Idioma**: `<html lang="pt-BR">`
4. **CSS custom**: `<link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">`
5. **Variavel `cfg`** esta disponivel em TODOS os templates (injetado pelo context processor). Usar `cfg.get('chave', 'default')` ou `cfg['chave']`
6. **CSRF token**: todo `<form method="POST">` DEVE ter `<input type="hidden" name="csrf_token" value="{{ session.csrf_token }}">`
7. **Mobile first**: layout single-column por padrao, grid so em telas grandes
8. **Sem emojis no HTML**. Usar texto ou icones CSS/SVG simples

### 3.1 — `templates/components/progress_bar.html`

Macro Jinja2 para barra de progresso reutilizavel.

```html
{% macro progress_bar(raised, goal, supporters="0") %}
{% set raised_f = raised|float %}
{% set goal_f = goal|float %}
{% set pct = ((raised_f / goal_f * 100) if goal_f > 0 else 0)|round(1) %}
<div class="progress-section">
    <div class="progress-stats">
        <strong>{{ "%.4f"|format(raised_f) }} / {{ "%.4f"|format(goal_f) }} BTC</strong>
        <span>({{ pct }}%)</span>
    </div>
    <progress value="{{ pct }}" max="100">{{ pct }}%</progress>
    {% if supporters and supporters != "0" %}
    <small>{{ supporters }} supporters</small>
    {% endif %}
</div>
{% endmacro %}
```

### 3.2 — `templates/components/qr_codes.html`

Macro para exibir QR codes com botao de copiar e deep link.

```html
{% macro qr_section(btc_address, lightning_address, size="medium") %}
<div class="qr-grid">
    {% if btc_address %}
    <div class="qr-card">
        <h3>Bitcoin On-Chain</h3>
        <img src="{{ url_for('qr_code', qr_type='btc') }}" alt="Bitcoin QR Code" loading="lazy" class="qr-img qr-{{ size }}">
        <div class="address-box">
            <code class="address-text" id="btc-addr">{{ btc_address }}</code>
            <button onclick="copyAddr('btc-addr', this)" class="copy-btn" title="Copy address">Copy</button>
        </div>
        <a href="bitcoin:{{ btc_address }}" class="wallet-link">Open in Wallet</a>
    </div>
    {% endif %}

    {% if lightning_address %}
    <div class="qr-card">
        <h3>Lightning Network</h3>
        <img src="{{ url_for('qr_code', qr_type='lightning') }}" alt="Lightning QR Code" loading="lazy" class="qr-img qr-{{ size }}">
        <div class="address-box">
            <code class="address-text" id="ln-addr">{{ lightning_address }}</code>
            <button onclick="copyAddr('ln-addr', this)" class="copy-btn" title="Copy address">Copy</button>
        </div>
        <a href="lightning:{{ lightning_address }}" class="wallet-link">Open in Wallet</a>
    </div>
    {% endif %}
</div>

<script>
function copyAddr(id, btn) {
    const text = document.getElementById(id).textContent;
    navigator.clipboard.writeText(text).then(function() {
        const orig = btn.textContent;
        btn.textContent = 'Copied!';
        setTimeout(function() { btn.textContent = orig; }, 2000);
    });
}
</script>
{% endmacro %}
```

### 3.3 — `templates/components/embed.html`

Macro para share buttons.

```html
{% macro share_buttons(url, text) %}
<div class="share-section">
    <strong>Share:</strong>
    <a href="https://twitter.com/intent/tweet?text={{ text|urlencode }}&url={{ url|urlencode }}" target="_blank" rel="noopener" class="share-btn">Twitter</a>
    <a href="https://t.me/share/url?url={{ url|urlencode }}&text={{ text|urlencode }}" target="_blank" rel="noopener" class="share-btn">Telegram</a>
    <a href="https://wa.me/?text={{ (text ~ ' ' ~ url)|urlencode }}" target="_blank" rel="noopener" class="share-btn">WhatsApp</a>
    <button onclick="copyAddr('share-url', this)" class="share-btn copy-btn">Copy Link</button>
    <code id="share-url" style="display:none">{{ url }}</code>
</div>
{% endmacro %}
```

### 3.4 — `templates/base.html`

Layout master que TODOS os templates estendem com `{% extends "base.html" %}`.

Estrutura:
```html
<!DOCTYPE html>
<html lang="pt-BR" data-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}{{ cfg.get('site_title', 'Free Sandmann') }}{% endblock %}</title>
    <meta name="description" content="{{ cfg.get('site_description', '') }}">

    <!-- Open Graph -->
    <meta property="og:title" content="{{ cfg.get('site_title', 'Free Sandmann') }}">
    <meta property="og:description" content="{{ cfg.get('site_description', '') }}">
    {% if cfg.get('og_image_url') %}
    <meta property="og:image" content="{{ cfg.get('og_image_url') }}">
    {% endif %}
    <meta property="og:type" content="website">

    <!-- Pico CSS -->
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.min.css">
    <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
</head>
<body>
    <header class="container">
        <nav>
            <ul>
                <li><a href="{{ url_for('index') }}"><strong>{{ cfg.get('site_title', 'Free Sandmann') }}</strong></a></li>
            </ul>
            <ul>
                <li><a href="{{ url_for('index') }}">Home</a></li>
                <li><a href="{{ url_for('updates') }}">Updates</a></li>
                <li><a href="{{ url_for('donate') }}" role="button" class="donate-nav-btn">Donate</a></li>
            </ul>
        </nav>
    </header>

    <main class="container">
        <!-- Flash messages -->
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <article class="flash-msg flash-{{ category }}">{{ message }}</article>
                {% endfor %}
            {% endif %}
        {% endwith %}

        {% block content %}{% endblock %}
    </main>

    <footer class="container">
        <hr>
        <small>
            {{ cfg.get('site_title', 'Free Sandmann') }} — {{ cfg.get('site_tagline', '') }}<br>
            <a href="https://github.com/sandman21vs/FREESANDMANN" target="_blank">Open Source</a> — Self-host this site for your own legal defense.
        </small>
    </footer>

    <!-- Sticky donate button (mobile) -->
    <div class="sticky-donate">
        <a href="{{ url_for('donate') }}" class="sticky-donate-btn">Donate Now</a>
    </div>

    {% block scripts %}{% endblock %}
</body>
</html>
```

### 3.5 — `templates/index.html`

Homepage. Estende `base.html`. Segue o wireframe mobile do ARCHITECTURE.md.

Secoes de cima para baixo:
1. **Barra de progresso**: importar macro de `components/progress_bar.html` e chamar com `cfg['raised_btc']`, `cfg['goal_btc']`, `cfg['supporters_count']`
2. **Hero**: Se `cfg.get('hero_image_url')`, mostrar imagem. Mostrar `cfg['site_description']`. Se `cfg.get('deadline_text')`, mostrar com destaque (cor laranja). Botao CTA "Donate Now" linkando para `/donate`
3. **Transparencia**: Se `cfg.get('transparency_text')`, renderizar como secao. Markdown ja vem como texto simples (renderizar com `|safe` se vier HTML, ou mostrar como texto). Link para `cfg.get('wallet_explorer_url')` se existir
4. **QR codes**: importar macro de `components/qr_codes.html` e chamar com `cfg['btc_address']` e `cfg['lightning_address']`, size="medium"
5. **Artigos fixados**: loop `pinned`, mostrar titulo com link para `/updates/{{ a.slug }}`
6. **Media links**: loop `media_links`, mostrar titulo com link externo. Agrupar por `link_type` se quiser (video, tweet, article)
7. **Share buttons**: importar macro de `components/embed.html`

Importar macros com:
```jinja2
{% from "components/progress_bar.html" import progress_bar %}
{% from "components/qr_codes.html" import qr_section %}
{% from "components/embed.html" import share_buttons %}
```

### 3.6 — `templates/donate.html`

Pagina dedicada de doacao. Estende `base.html`.

Secoes:
1. Barra de progresso (macro)
2. QR codes com size="large" (macro)
3. Secao "First time donating Bitcoin?":
   - Passo 1: Download a wallet (Muun, Phoenix, Blue Wallet) — links reais
   - Passo 2: Scan the QR code or copy the address
   - Passo 3: Confirm the transaction

### 3.7 — `templates/articles.html`

Lista de artigos. Estende `base.html`.

- Titulo: "Updates"
- Loop artigos: cada um e um `<article>` com titulo (link para `/updates/{{ a.slug }}`), data formatada (`{{ a.created_at[:10] }}`), e preview do body (primeiros 200 caracteres do `body_md`, sem HTML)
- Se nao houver artigos: mensagem "No updates yet."

### 3.8 — `templates/article.html`

Artigo individual. Estende `base.html`.

- Bloco title: `{{ article.title }} — {{ cfg.get('site_title') }}`
- Titulo `<h1>`, data, body HTML (`{{ article.body_html|safe }}`)
- Share buttons (macro) com URL da pagina atual
- Link "Back to updates"

### 3.9 — `templates/error.html`

Pagina de erro generica. Estende `base.html`.

- Recebe `code` e `message`
- Mostra: `<h1>{{ code }}</h1>` e `<p>{{ message }}</p>`
- Link para homepage

### Validacao da Parte 3

```bash
cd /home/msi/FREESANDMANN
python -c "from app import app; client = app.test_client(); r = client.get('/'); print(r.status_code, len(r.data))"
```

Deve retornar `200` e o tamanho do HTML gerado.

---

## PARTE 4 — Templates admin

**Objetivo**: Criar todos os templates do painel administrativo.
**Arquivos a criar**: 7 arquivos em `templates/admin/`
**Dependencias**: Partes 1, 2 e 3 completas

### REGRAS ADMIN:

- Todos estendem `base.html`
- Todo form tem CSRF token: `<input type="hidden" name="csrf_token" value="{{ session.csrf_token }}">`
- Paginas admin nao sao linkadas em nenhum lugar publico
- Visual simples: formularios, tabelas, botoes — nao precisa ser bonito

### 4.1 — `templates/admin/login.html`

Estende `base.html`. Bloco content:
- `<h1>Admin Login</h1>`
- Form POST para `{{ url_for('admin_login') }}`:
  - Input text `username` (placeholder "Username")
  - Input password `password` (placeholder "Password")
  - CSRF token hidden
  - Botao submit "Login"
- Nada mais. Sem links para registro, esqueci senha, etc.

### 4.2 — `templates/admin/change_password.html`

Estende `base.html`. Bloco content:
- `<h1>Change Password</h1>`
- `<p>You must change the default password before continuing.</p>`
- Form POST para `{{ url_for('admin_change_password') }}`:
  - Input password `new_password` (placeholder "New password (min 8 characters)")
  - Input password `confirm_password` (placeholder "Confirm password")
  - CSRF token hidden
  - Botao submit "Change Password"

### 4.3 — `templates/admin/dashboard.html`

Estende `base.html`. Bloco content:
- `<h1>Dashboard</h1>`
- Card de stats:
  - Raised: `{{ cfg['raised_btc'] }} / {{ cfg['goal_btc'] }} BTC`
  - Breakdown: On-chain: `{{ cfg['raised_onchain_btc'] }}`, Lightning: `{{ cfg['raised_lightning_btc'] }}`, Manual adjustment: `{{ cfg['raised_btc_manual_adjustment'] }}`
  - Last balance check: `{{ cfg['last_balance_check'] or 'Never' }}`
  - Form POST para `{{ url_for('admin_refresh_balance') }}` com botao "Refresh Balance Now" + CSRF token
  - Supporters: `{{ cfg['supporters_count'] }}`
  - Articles: `{{ articles|length }}`
  - Media links: `{{ media_links|length }}`
- Links de navegacao:
  - `<a href="{{ url_for('admin_settings') }}">Settings</a>`
  - `<a href="{{ url_for('admin_articles') }}">Articles</a>`
  - `<a href="{{ url_for('admin_media_links') }}">Media Links</a>`
  - `<a href="{{ url_for('admin_change_password') }}">Change Password</a>`
  - `<a href="{{ url_for('admin_logout') }}">Logout</a>`

### 4.4 — `templates/admin/settings.html`

Estende `base.html`. Bloco content:
- `<h1>Site Settings</h1>`
- Form POST para `{{ url_for('admin_settings') }}`:
- Organizar em secoes (usar `<fieldset>` ou `<details>`):

**Secao "General"**:
  - `site_title` — input text, value `{{ cfg['site_title'] }}`
  - `site_description` — textarea, value `{{ cfg['site_description'] }}`
  - `site_tagline` — input text, value `{{ cfg['site_tagline'] }}`
  - `hero_image_url` — input text (URL), value `{{ cfg['hero_image_url'] }}`
  - `og_image_url` — input text (URL), value `{{ cfg['og_image_url'] }}`
  - `deadline_text` — input text, value `{{ cfg['deadline_text'] }}`

**Secao "Bitcoin"**:
  - `btc_address` — input text, value `{{ cfg['btc_address'] }}`
  - `lightning_address` — input text, value `{{ cfg['lightning_address'] }}`
  - `wallet_explorer_url` — input text (URL), value `{{ cfg['wallet_explorer_url'] }}`

**Secao "Fundraising"**:
  - `goal_btc` — input text, value `{{ cfg['goal_btc'] }}`
  - `goal_description` — input text, value `{{ cfg['goal_description'] }}`
  - `raised_lightning_btc` — input text, value `{{ cfg['raised_lightning_btc'] }}`
  - `raised_btc_manual_adjustment` — input text, value `{{ cfg['raised_btc_manual_adjustment'] }}`
  - `supporters_count` — input text, value `{{ cfg['supporters_count'] }}`
  - Mostrar texto informativo: "On-chain balance is updated automatically from mempool.space. Current: {{ cfg['raised_onchain_btc'] }} BTC"

**Secao "Transparency"**:
  - `transparency_text` — textarea grande, value `{{ cfg['transparency_text'] }}`. Hint: "Supports Markdown"

- CSRF token hidden
- Botao submit "Save Settings"
- Link voltar para dashboard

### 4.5 — `templates/admin/articles.html`

Estende `base.html`. Bloco content:
- `<h1>Articles</h1>`
- `<a href="{{ url_for('admin_article_new') }}">New Article</a>` (botao)
- Tabela com colunas: Title, Status, Pinned, Date, Actions
- Loop `articles`:
  - Title: texto
  - Status: "Published" ou "Draft" baseado em `a.published`
  - Pinned: "Yes" ou "No" baseado em `a.pinned`
  - Date: `{{ a.created_at[:10] }}`
  - Actions: link "Edit" (`admin_article_edit` com id) e form "Delete" (POST com CSRF token, botao pequeno)
- Se nao houver artigos: "No articles yet."
- Link voltar para dashboard

### 4.6 — `templates/admin/article_form.html`

Estende `base.html`. Bloco content:
- `<h1>{{ "Edit Article" if article else "New Article" }}</h1>`
- Form POST para `{{ url_for('admin_article_edit', article_id=article.id) if article else url_for('admin_article_new') }}`:
  - `title` — input text, value `{{ article.title if article else '' }}`
  - `body_md` — textarea grande (rows=20), value `{{ article.body_md if article else '' }}`. Hint: "Write in Markdown. YouTube and Twitter/X URLs are auto-embedded."
  - `published` — checkbox, checked se `article.published if article else True`
  - `pinned` — checkbox, checked se `article.pinned if article else False`
  - CSRF token hidden
  - Botao submit "{{ 'Update' if article else 'Create' }} Article"
- Link voltar para articles list

### 4.7 — `templates/admin/media_links.html`

Estende `base.html`. Bloco content:
- `<h1>Media Links</h1>`
- Form POST para `{{ url_for('admin_media_links') }}` (adicionar novo link):
  - `title` — input text, placeholder "Link title"
  - `url` — input text, placeholder "https://..."
  - `link_type` — select com opcoes: `article`, `video`, `tweet`
  - CSRF token hidden
  - Botao submit "Add Link"
- Tabela de links existentes: Title (com link externo), Type, Date, Action (Delete form com CSRF)
- Se nao houver links: "No media links yet."
- Link voltar para dashboard

### Validacao da Parte 4

```bash
cd /home/msi/FREESANDMANN
python -c "
from app import app
client = app.test_client()
# Pagina publica
r = client.get('/')
assert r.status_code == 200, f'Index failed: {r.status_code}'
# Login page
r = client.get('/admin/login')
assert r.status_code == 200, f'Login failed: {r.status_code}'
print('All admin templates OK')
"
```

---

## PARTE 5 — CSS customizado (style.css)

**Objetivo**: Criar o CSS que complementa Pico CSS com a identidade visual do projeto.
**Arquivos a criar**: `static/style.css`
**Dependencias**: Partes 1-4 completas (para poder testar visualmente)

### 5.1 — Variaveis de cor (CSS custom properties)

Definir no `:root` para sobrescrever Pico CSS e usar nas classes customizadas:

```css
:root {
    --btc-orange: #f7931a;
    --success-green: #2ea043;
    --danger-red: #da3633;
    --bg-dark: #0d1117;
    --bg-card: #161b22;
    --text-primary: #e6edf3;
    --text-secondary: #8b949e;
}
```

Sobrescrever variaveis do Pico CSS para tema dark:
```css
[data-theme="dark"] {
    --pico-background-color: var(--bg-dark);
    --pico-card-background-color: var(--bg-card);
    --pico-primary: var(--btc-orange);
    --pico-primary-hover: #e8860f;
}
```

### 5.2 — Tipografia

```css
body {
    font-size: 18px;
}
```

Nao definir font-family — Pico CSS ja usa system fonts.

### 5.3 — Barra de progresso

```css
.progress-section {
    margin-bottom: 1.5rem;
}

.progress-stats {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin-bottom: 0.5rem;
}

progress {
    width: 100%;
    height: 1.5rem;
}

progress::-webkit-progress-bar {
    background-color: var(--bg-card);
    border-radius: 0.5rem;
}

progress::-webkit-progress-value {
    background-color: var(--btc-orange);
    border-radius: 0.5rem;
}

progress::-moz-progress-bar {
    background-color: var(--btc-orange);
    border-radius: 0.5rem;
}
```

### 5.4 — QR codes grid

```css
/* Mobile: empilhado */
.qr-grid {
    display: grid;
    grid-template-columns: 1fr;
    gap: 2rem;
    margin: 2rem 0;
}

/* Desktop: lado a lado */
@media (min-width: 768px) {
    .qr-grid {
        grid-template-columns: 1fr 1fr;
    }
}

.qr-card {
    text-align: center;
    padding: 1.5rem;
    background: var(--bg-card);
    border-radius: 0.5rem;
}

.qr-img {
    display: block;
    margin: 1rem auto;
    border-radius: 0.5rem;
    background: white;
    padding: 0.5rem;
}

.qr-medium { max-width: 200px; }
.qr-large { max-width: 300px; }

/* Mobile: QR menor */
@media (max-width: 480px) {
    .qr-medium { max-width: 160px; }
    .qr-large { max-width: 240px; }
}
```

### 5.5 — Botao copiar e endereco

```css
.address-box {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin: 0.75rem 0;
    padding: 0.5rem;
    background: var(--bg-dark);
    border-radius: 0.25rem;
    overflow: hidden;
}

.address-text {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: 0.85rem;
}

.copy-btn {
    min-width: 48px;
    min-height: 48px;
    padding: 0.5rem 1rem;
    cursor: pointer;
    white-space: nowrap;
}

.wallet-link {
    display: inline-block;
    margin-top: 0.5rem;
}
```

### 5.6 — Sticky donate button (mobile)

```css
.sticky-donate {
    display: none;
}

@media (max-width: 768px) {
    .sticky-donate {
        display: block;
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        padding: 0.75rem 1rem;
        background: var(--bg-dark);
        border-top: 1px solid var(--bg-card);
        z-index: 100;
        text-align: center;
    }

    .sticky-donate-btn {
        display: block;
        width: 100%;
        padding: 1rem;
        background: var(--btc-orange);
        color: white;
        text-align: center;
        text-decoration: none;
        font-weight: bold;
        font-size: 1.1rem;
        border-radius: 0.5rem;
    }

    /* Padding no body para nao sobrepor conteudo */
    body {
        padding-bottom: 5rem;
    }
}
```

### 5.7 — Botao donate na nav

```css
.donate-nav-btn {
    background: var(--btc-orange) !important;
    color: white !important;
    border-color: var(--btc-orange) !important;
    font-weight: bold;
}
```

### 5.8 — Hero section

```css
.hero {
    text-align: center;
    padding: 2rem 0;
}

.hero img {
    max-width: 100%;
    max-height: 300px;
    object-fit: cover;
    border-radius: 0.5rem;
    margin-bottom: 1.5rem;
}

.hero .cta-btn {
    display: inline-block;
    padding: 1rem 2.5rem;
    background: var(--btc-orange);
    color: white;
    text-decoration: none;
    font-weight: bold;
    font-size: 1.2rem;
    border-radius: 0.5rem;
    margin-top: 1.5rem;
}

.deadline-text {
    color: var(--btc-orange);
    font-weight: bold;
    margin: 1rem 0;
}
```

### 5.9 — Share buttons

```css
.share-section {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    align-items: center;
    margin: 2rem 0;
    padding: 1rem;
    background: var(--bg-card);
    border-radius: 0.5rem;
}

.share-btn {
    padding: 0.5rem 1rem;
    border-radius: 0.25rem;
    text-decoration: none;
    font-size: 0.9rem;
    min-height: 48px;
    display: inline-flex;
    align-items: center;
}
```

### 5.10 — Flash messages

```css
.flash-msg {
    padding: 1rem;
    border-radius: 0.5rem;
    margin-bottom: 1rem;
}

.flash-success { border-left: 4px solid var(--success-green); }
.flash-error { border-left: 4px solid var(--danger-red); }
.flash-warning { border-left: 4px solid var(--btc-orange); }
```

### 5.11 — Embed containers

```css
.embed-container {
    position: relative;
    width: 100%;
    padding-bottom: 56.25%; /* 16:9 */
    height: 0;
    overflow: hidden;
    margin: 1.5rem 0;
    border-radius: 0.5rem;
}

.embed-container iframe {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
}
```

### 5.12 — Admin specific

```css
/* Tabela admin */
.admin-table {
    width: 100%;
    overflow-x: auto;
}

.admin-actions {
    display: flex;
    gap: 0.5rem;
}

.btn-danger {
    background: var(--danger-red);
    border-color: var(--danger-red);
    color: white;
}
```

### Validacao da Parte 5

Abrir no navegador: `http://localhost:8000`
Testar em viewport mobile (375px) e desktop (1280px).
Verificar:
- Barra de progresso aparece no topo
- QR codes empilham no mobile, lado a lado no desktop
- Botao sticky aparece so no mobile
- Enderecos truncam com ellipsis
- Botao copiar tem 48px minimo
- Cores corretas (dark theme, laranja nos CTAs)

---

## PARTE 6 — Docker e arquivos de deploy

**Objetivo**: Containerizar a aplicacao para deploy.
**Arquivos a criar**: `Dockerfile`, `docker-compose.yml`, `.env.example`, `.dockerignore`
**Dependencias**: Partes 1-5 completas

### 6.1 — `.dockerignore`

Criar em `/home/msi/FREESANDMANN/.dockerignore`:

```
__pycache__
*.pyc
.git
.gitignore
data/
*.db
.env
venv/
.venv/
*.md
!README.md
```

### 6.2 — `Dockerfile`

Criar em `/home/msi/FREESANDMANN/Dockerfile`:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Criar diretorio de dados
RUN mkdir -p /app/data

# Inicializar banco (sera sobrescrito pelo volume se ja existir)
RUN python init_db.py

EXPOSE 8000

CMD ["gunicorn", "-b", "0.0.0.0:8000", "-w", "2", "--timeout", "120", "app:app"]
```

### 6.3 — `docker-compose.yml`

Criar em `/home/msi/FREESANDMANN/docker-compose.yml`:

```yaml
services:
  web:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
    environment:
      - SECRET_KEY=${SECRET_KEY:-change-me-in-production}
      - DATABASE_PATH=/app/data/freesandmann.db
      - ADMIN_USERNAME=${ADMIN_USERNAME:-FREE}
    restart: unless-stopped
```

### 6.4 — `.env.example`

Criar em `/home/msi/FREESANDMANN/.env.example`:

```bash
# Required: change this to a random string
SECRET_KEY=your-random-secret-key-here

# Optional: change admin username (default: FREE)
ADMIN_USERNAME=FREE

# Optional: change database path (default: /app/data/freesandmann.db)
# DATABASE_PATH=/app/data/freesandmann.db
```

### Validacao da Parte 6

```bash
cd /home/msi/FREESANDMANN
docker compose build
docker compose up -d
# Esperar 5 segundos
curl -s http://localhost:8000 | head -20
docker compose down
```

---

## PARTE 7 — README e .gitignore

**Objetivo**: Documentacao para GitHub e gitignore.
**Arquivos a criar**: `README.md`, `.gitignore`
**Dependencias**: Partes 1-6 completas

### 7.1 — `.gitignore`

Criar em `/home/msi/FREESANDMANN/.gitignore`:

```
__pycache__/
*.pyc
*.pyo
data/*.db
.env
venv/
.venv/
*.egg-info/
dist/
build/
.DS_Store
```

### 7.2 — `README.md`

Criar em `/home/msi/FREESANDMANN/README.md`.

Estrutura do README:

**Titulo**: Free Sandmann — Self-hosted Legal Defense Fundraising Site

**Descricao**: 2-3 frases explicando o que e o projeto. Site de arrecadacao para defesa juridica com doacoes em Bitcoin (on-chain e Lightning).

**Screenshot/demo**: placeholder (pode adicionar depois)

**Features** (lista):
- Bitcoin on-chain and Lightning Network donations via QR codes
- Automatic on-chain balance tracking via mempool.space API
- Fundraising progress bar with real-time goal tracking
- Admin panel to manage articles, settings, and donation addresses
- Markdown support for articles with auto-embed for YouTube and Twitter
- Mobile-first responsive design
- Docker deployment ready
- Easy to fork and customize

**Quick Start**:
```bash
git clone https://github.com/sandman21vs/FREESANDMANN.git
cd freesandmann
cp .env.example .env
# Edit .env with your secret key
docker compose up -d
```

Then visit `http://localhost:8000`

**Admin Access**:
1. Navigate to `/admin/login`
2. Login with username `FREE` and password `FREE`
3. You will be required to change the password on first login
4. Configure your Bitcoin addresses and fundraising goal in Settings

**Deploy with Cloudflare Tunnel**:
```bash
# Install cloudflared
# Option 1: Quick tunnel
cloudflared tunnel --url http://localhost:8000

# Option 2: Named tunnel with custom domain
cloudflared tunnel create freesandmann
cloudflared tunnel route dns freesandmann yourdomain.com
cloudflared tunnel run freesandmann
```

**Customization**:
- Edit site settings via admin panel (no code changes needed)
- Replace `static/logo.png` for custom branding
- Modify `static/style.css` for visual changes
- All configuration is stored in SQLite — no config files to edit

**Fork for your own case**:
1. Fork this repo
2. Deploy with Docker
3. Login as admin
4. Set your Bitcoin address and tell your story
5. Share the link

**Tech Stack**: Flask, SQLite, Pico CSS, python-qrcode

**License**: MIT

### Validacao da Parte 7

```bash
cd /home/msi/FREESANDMANN
cat README.md | head -5  # verificar que existe
cat .gitignore | head -5  # verificar que existe
```

---

## PARTE 8 — Git init e primeiro commit

**Objetivo**: Inicializar repositorio Git e fazer o primeiro commit.
**Dependencias**: Partes 1-7 completas

### 8.1 — Comandos

```bash
cd /home/msi/FREESANDMANN
git init
git add .
git commit -m "Initial commit: Free Sandmann legal defense fundraising site

- Flask + SQLite + Pico CSS
- Bitcoin on-chain and Lightning donation QR codes
- Automatic balance tracking via mempool.space
- Admin panel with articles, settings, media links
- Mobile-first responsive design
- Docker deployment ready"
```

### Validacao

```bash
git log --oneline
git status
```

---

## CHECKLIST FINAL

Apos todas as partes, verificar:

- [ ] `python init_db.py` roda sem erro
- [ ] `python -c "import app"` roda sem erro
- [ ] `docker compose build` roda sem erro
- [ ] `docker compose up -d` sobe o container
- [ ] `http://localhost:8000` mostra a homepage
- [ ] `http://localhost:8000/donate` mostra pagina de doacao
- [ ] `http://localhost:8000/updates` mostra lista de artigos (vazia)
- [ ] `http://localhost:8000/admin/login` mostra formulario de login
- [ ] Login com FREE/FREE funciona e redireciona para troca de senha
- [ ] Apos trocar senha, dashboard funciona
- [ ] Criar artigo funciona
- [ ] Alterar settings funciona
- [ ] Adicionar media link funciona
- [ ] No mobile (375px): layout single-column, sticky donate button
- [ ] No desktop (1280px): QR codes lado a lado
- [ ] QR codes geram corretamente (apos configurar enderecos BTC)
- [ ] Balance checker roda em background (verificar logs)
- [ ] `docker compose down` para tudo
