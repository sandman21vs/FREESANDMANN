# Free Sandmann - Documentacao do Projeto

## Objetivo

Website de arrecadacao para defesa juridica. Simples, auto-hospedavel, open source.
Qualquer pessoa processada injustamente pode fazer fork e usar para o proprio caso.

---

## Stack Tecnologica

| Camada | Tecnologia | Motivo |
|--------|-----------|--------|
| Backend | Python 3.12 + Flask | Simples, sem dependencias pesadas |
| Banco de dados | SQLite | Zero config, um arquivo, backup facil |
| Templates | Jinja2 (incluso no Flask) | Server-side rendered, sem build step |
| CSS | Pico CSS (~10KB, CDN) | Responsivo sem classes, tema dark |
| QR Codes | python-qrcode + Pillow | Gera QR como PNG no servidor |
| Markdown | biblioteca `markdown` do Python | Admin escreve artigos em Markdown |
| Autenticacao | Flask sessions + werkzeug hashing | Sem dependencia externa |
| Servidor prod | gunicorn | Production-ready |
| Deploy | Docker + docker-compose | Um comando para subir |
| Proxy/SSL | Cloudflare Tunnel | TLS gratis, sem abrir portas |

**Zero JavaScript frameworks. Zero build steps. Zero node_modules.**

Unico JS: snippet inline para copiar endereco BTC e animacao da barra de progresso.

---

## Estrutura de Arquivos

```
FREESANDMANN/
├── app.py                     # Aplicacao Flask (todas as rotas)
├── models.py                  # Acesso ao SQLite (queries)
├── config.py                  # Config padrao + variaveis de ambiente
├── init_db.py                 # Inicializacao do banco de dados
├── requirements.txt           # Dependencias Python
├── Dockerfile                 # Build do container
├── docker-compose.yml         # Orquestracao + volume
├── .env.example               # Template de variaveis de ambiente
├── README.md                  # Instrucoes de setup e fork
├── ARCHITECTURE.md            # Este documento
│
├── static/
│   ├── style.css              # CSS customizado (sobre Pico CSS)
│   └── logo.png               # Logo do site (placeholder)
│
├── templates/
│   ├── base.html              # Layout master (nav, footer, Pico CSS)
│   ├── index.html             # Homepage: missao, progresso, QR codes
│   ├── donate.html            # Pagina de doacao dedicada
│   ├── articles.html          # Lista de artigos/updates
│   ├── article.html           # Artigo individual
│   ├── error.html             # Pagina de erro (404, 403)
│   │
│   ├── admin/
│   │   ├── login.html         # Login (pagina oculta)
│   │   ├── dashboard.html     # Painel: stats, resumo
│   │   ├── settings.html      # Config: BTC, meta, titulo
│   │   ├── articles.html      # CRUD de artigos
│   │   ├── article_form.html  # Formulario criar/editar artigo
│   │   ├── media_links.html   # Gerenciar links externos
│   │   └── change_password.html
│   │
│   └── components/
│       ├── progress_bar.html  # Macro Jinja2: barra de progresso
│       ├── qr_codes.html      # Macro Jinja2: display QR codes
│       └── embed.html         # Macro Jinja2: embed Twitter/YouTube
│
└── data/                      # Volume Docker (mount point)
    └── freesandmann.db        # Banco SQLite (criado em runtime)
```

**Total: ~20 arquivos. Sem build step, sem bundler.**

---

## Schema do Banco de Dados (SQLite)

### Tabela `config` (chave-valor)

```sql
CREATE TABLE config (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

Chaves pre-populadas:
- `site_title` — titulo do site
- `site_description` — descricao para SEO e homepage
- `site_tagline` — slogan curto
- `btc_address` — endereco Bitcoin on-chain
- `lightning_address` — endereco/invoice Lightning Network
- `goal_btc` — meta em BTC (ex: "2.5")
- `raised_onchain_btc` — saldo on-chain (atualizado automaticamente via mempool.space)
- `raised_lightning_btc` — saldo Lightning (manual agora, Coinos futuramente)
- `raised_btc_manual_adjustment` — ajuste manual do admin (ex: doacoes fora do sistema)
- `raised_btc` — total calculado (onchain + lightning + ajuste)
- `last_balance_check` — timestamp da ultima consulta ao mempool.space
- `goal_description` — descricao da meta
- `admin_password_hash` — hash da senha do admin
- `admin_force_password_change` — "1" ou "0"
- `coinos_api_key` — API key Coinos.io (vazio = desabilitado, futuro)
- `coinos_enabled` — "0" (default, futuro)

### Tabela `articles`

```sql
CREATE TABLE articles (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    title      TEXT NOT NULL,
    slug       TEXT UNIQUE NOT NULL,
    body_md    TEXT NOT NULL,          -- Fonte Markdown
    body_html  TEXT NOT NULL,          -- HTML pre-renderizado
    published  INTEGER DEFAULT 1,     -- 0=rascunho, 1=publicado
    pinned     INTEGER DEFAULT 0,     -- Mostrar na homepage
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);
```

### Tabela `media_links`

```sql
CREATE TABLE media_links (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    title      TEXT NOT NULL,
    url        TEXT NOT NULL,
    link_type  TEXT NOT NULL DEFAULT 'article', -- article, video, tweet
    created_at TEXT DEFAULT (datetime('now'))
);
```

**Nao existe tabela `users`.** Ha exatamente 1 admin. Username fixo (env var), senha no `config`.

---

## Rotas

### Rotas Publicas

| Metodo | Path | Descricao |
|--------|------|-----------|
| GET | `/` | Homepage: artigos fixados, barra de progresso, QR codes, links de midia |
| GET | `/donate` | Pagina dedicada de doacao (QR grandes, instrucoes) |
| GET | `/updates` | Lista de artigos publicados |
| GET | `/updates/<slug>` | Artigo individual |
| GET | `/qr/btc` | Retorna imagem PNG do QR code Bitcoin on-chain |
| GET | `/qr/lightning` | Retorna imagem PNG do QR code Lightning |

### Rotas Admin (todas sob `/admin`)

| Metodo | Path | Descricao |
|--------|------|-----------|
| GET/POST | `/admin/login` | Login (URL NAO linkada em nenhuma pagina publica) |
| GET | `/admin/logout` | Deslogar |
| GET | `/admin/` | Dashboard com stats |
| GET/POST | `/admin/settings` | Editar enderecos BTC, meta, titulo, descricao |
| GET | `/admin/articles` | Listar todos artigos (rascunhos + publicados) |
| GET/POST | `/admin/articles/new` | Criar artigo |
| GET/POST | `/admin/articles/<id>/edit` | Editar artigo |
| POST | `/admin/articles/<id>/delete` | Deletar artigo |
| GET/POST | `/admin/media-links` | Gerenciar links externos (add) |
| POST | `/admin/media-links/<id>/delete` | Deletar link |
| GET/POST | `/admin/change-password` | Trocar senha |

**Total: 15 rotas.** Tudo cabe em um unico `app.py`.

---

## Fluxo de Autenticacao

1. Credenciais padrao: username `FREE`, senha `FREE`
2. `init_db.py` gera hash da senha "FREE" e armazena no `config`
3. Flag `admin_force_password_change` = `"1"`
4. Login seta `session['admin'] = True`
5. Se flag = "1", TODAS as rotas admin redirecionam para `/admin/change-password`
6. Apos trocar senha, flag vira "0"
7. Senha nova minimo 8 caracteres, nao pode ser "FREE"
8. Rate limiting: 5 tentativas por IP, lockout de 5 minutos

---

## Geracao de QR Codes

- Rota `/qr/btc` gera QR com URI `bitcoin:<endereco>`
- Rota `/qr/lightning` gera QR com o endereco/invoice Lightning
- Gerado no servidor com `python-qrcode`, retorna `image/png`
- Cache header de 1 hora
- Templates usam `<img src="/qr/btc">` — limpo, sem base64 inline

---

## Rastreamento de Doacoes e Barra de Progresso

### On-chain (automatico)

O endereco BTC on-chain e unico e fixo. O servidor consulta automaticamente o saldo:

- **API**: `mempool.space` (publica, sem autenticacao, sem rate limit agressivo)
  - Endpoint: `GET https://mempool.space/api/address/<endereco>`
  - Retorna `chain_stats.funded_txo_sum` (total recebido em satoshis)
- **Frequencia**: 1x por hora via thread background (APScheduler ou simples `threading.Timer`)
- **Fluxo**:
  1. Thread background roda a cada 60 minutos
  2. Faz GET na API do mempool.space
  3. Converte satoshis para BTC (`funded_txo_sum / 100_000_000`)
  4. Atualiza `raised_onchain_btc` no config
  5. `raised_btc` = `raised_onchain_btc` + `raised_lightning_btc`
- **Fallback**: Se a API falhar, mantem o ultimo valor. Admin pode corrigir manualmente
- **Cache**: Resultado cacheado em memoria entre consultas
- **Sem dependencia extra**: usa `urllib.request` (stdlib) — nao precisa de `requests`

### Lightning (futuro — Coinos.io API)

Por enquanto, Lightning fica com atualizacao manual pelo admin.

**Plano futuro** (quando priorizar):
- Integrar com API da Coinos.io para receber pagamentos Lightning
- Coinos fornece webhook ou polling para verificar pagamentos recebidos
- Saldo Lightning atualizado automaticamente via `raised_lightning_btc`
- Admin configura API key da Coinos no painel de settings

**Config keys relacionadas**:
- `coinos_api_key` — API key da Coinos (vazio = desabilitado)
- `coinos_enabled` — "0" ou "1" (default "0")

Enquanto Coinos nao estiver integrado, admin atualiza `raised_lightning_btc` manualmente.

### Barra de Progresso

- `raised_btc` = `raised_onchain_btc` + `raised_lightning_btc` (calculado automaticamente)
- Admin tambem pode definir `raised_btc_manual_adjustment` para correcoes
- Calcula porcentagem server-side
- Renderiza como `<progress>` HTML (Pico CSS estiliza automaticamente)
- Mostra: "0.73 / 2.5 BTC (29.2%) — 47 apoiadores"
- No admin dashboard: mostra breakdown (on-chain vs lightning vs ajuste manual)

---

## Auto-Embed de Midia

Artigos escritos em Markdown suportam HTML raw. Alem disso, pos-processamento automatico:

- **YouTube**: URLs `youtube.com/watch?v=XXX` ou `youtu.be/XXX` viram iframe embed
- **Twitter/X**: URLs `twitter.com/user/status/XXX` ou `x.com/user/status/XXX` viram embed blockquote com widget JS
- Implementado com regex simples (~20 linhas de codigo)

Admin tambem pode adicionar links externos (Twitter, YouTube, artigos) via tabela `media_links`, que aparecem na homepage.

---

## Background Task: Balance Checker

```python
# Pseudocodigo — roda em thread separada a cada 60 min
import urllib.request, json

def check_onchain_balance():
    address = get_config("btc_address")
    if not address:
        return
    url = f"https://mempool.space/api/address/{address}"
    try:
        resp = urllib.request.urlopen(url, timeout=10)
        data = json.loads(resp.read())
        funded = data["chain_stats"]["funded_txo_sum"]   # satoshis recebidos
        spent  = data["chain_stats"]["spent_txo_sum"]    # satoshis gastos
        balance_sats = funded  # total recebido (nao saldo atual — queremos total arrecadado)
        balance_btc = balance_sats / 100_000_000
        set_config("raised_onchain_btc", str(round(balance_btc, 8)))
        # Recalcular total
        lightning = float(get_config("raised_lightning_btc", "0"))
        adjustment = float(get_config("raised_btc_manual_adjustment", "0"))
        total = balance_btc + lightning + adjustment
        set_config("raised_btc", str(round(total, 8)))
        set_config("last_balance_check", datetime.utcnow().isoformat())
    except Exception:
        pass  # manter ultimo valor, logar erro
```

- Usa `threading.Timer` para agendar (sem dependencia extra como APScheduler)
- Roda na inicializacao do app e repete a cada 3600 segundos
- Admin pode forcar refresh manual via botao no dashboard

---

## Seguranca

- **Admin oculto**: `/admin/login` nao aparece em nenhum link publico
- **CSRF**: Token hidden em cada formulario, validado no POST
- **Rate limiting**: Contador em memoria (IP -> tentativas), lockout apos 5 falhas
- **Content Security Policy**: Headers permitindo YouTube/Twitter embeds
- **WAL mode**: SQLite em modo WAL para melhor performance de leitura
- **Hashing**: werkzeug `generate_password_hash` / `check_password_hash` (PBKDF2)

---

## Docker

### Dockerfile

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN python init_db.py
EXPOSE 8000
CMD ["gunicorn", "-b", "0.0.0.0:8000", "-w", "2", "app:app"]
```

### docker-compose.yml

```yaml
services:
  web:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
    environment:
      - SECRET_KEY=change-me-in-production
    restart: unless-stopped
```

### Deploy com Cloudflare Tunnel

```bash
# Opcao 1: Quick tunnel (teste)
cloudflared tunnel --url http://localhost:8000

# Opcao 2: Tunnel nomeado (producao com dominio)
cloudflared tunnel create freesandmann
cloudflared tunnel route dns freesandmann freesandmann.sandlabs.store
cloudflared tunnel run freesandmann
```

---

## Variaveis de Ambiente

| Variavel | Default | Descricao |
|----------|---------|-----------|
| `SECRET_KEY` | `change-me-in-production` | Chave secreta do Flask |
| `DATABASE_PATH` | `data/freesandmann.db` | Caminho do banco SQLite |
| `ADMIN_USERNAME` | `FREE` | Username do admin |

Todas as outras configs sao editaveis pelo painel admin (titulo, BTC, meta, etc).

---

## Guia de Fork/Customizacao

Para alguem usar este site para o proprio caso:

1. Fork o repositorio
2. Troque `logo.png` e `style.css` para sua identidade visual
3. Edite defaults em `config.py` se quiser (opcional, tudo editavel pelo admin)
4. Suba com `docker compose up -d`
5. Acesse `/admin/login`, troque a senha, comece a postar artigos

**Nenhuma mudanca de codigo necessaria para uso basico.**

---

## Ordem de Implementacao

1. `config.py` + `init_db.py` + `models.py` — fundacao do banco
2. `app.py` rotas publicas (`/`, `/donate`, `/updates`, `/qr/<type>`)
3. `templates/base.html` + templates publicos — site renderizando
4. `app.py` rotas admin (login, settings, CRUD artigos, troca senha)
5. `templates/admin/` — templates admin
6. `static/style.css` — estilizacao final
7. `Dockerfile` + `docker-compose.yml` — containerizacao
8. `README.md` — documentacao para GitHub
9. Teste end-to-end completo no Docker

---

## Dependencias Python

```
Flask==3.1.0
gunicorn==23.0.0
python-qrcode[pil]==8.0
Pillow==11.1.0
markdown==3.7
Werkzeug==3.1.3
```

**6 dependencias. Sem frameworks JS, sem npm, sem webpack.**

---

## Recomendacoes: Identidade Visual, Conversao e Mobile

### Principio Geral
O site precisa transmitir **urgencia + credibilidade + simplicidade**.
A pessoa que acessa (provavelmente pelo celular, vindo de um link no Twitter/Telegram)
tem que entender em 5 segundos: quem e voce, o que aconteceu, como ajudar.

---

### Mobile First (prioridade maxima)

O Pico CSS ja e responsivo, mas vamos alem:

- **Layout single-column** no mobile. Nada lado a lado que quebre em tela pequena
- **QR codes empilhados verticalmente** no celular (lado a lado so em desktop)
- **Botao "Doar" fixo** no rodape do mobile (sticky bottom bar) — sempre visivel ao rolar
- **Enderecos BTC com botao "Copiar"** grande e facil de tocar (tap target minimo 48px)
- **Fontes grandes**: body minimo 18px no mobile, titulos 28px+
- **Barra de progresso** no topo, visivel sem scroll
- **Nav hamburger** no mobile — so logo + botao doar visivel, menu abre ao tocar
- **QR codes com tamanho adaptativo**: menores no celular (cabem na tela), maiores no desktop
- Testar em viewport 375px (iPhone SE) como referencia minima

---

### Identidade Visual para Maximizar Doacoes

**Esquema de cores (tema dark)**:
- Fundo: preto/cinza muito escuro (#0d1117) — serio, sobreo
- Texto: branco suave (#e6edf3) — boa leitura
- Cor de destaque: **laranja Bitcoin** (#f7931a) — para botoes de doacao, barra de progresso, CTA
- Cor secundaria: verde (#2ea043) — para indicar progresso/sucesso
- Vermelho sutil (#da3633) — para urgencia sem ser agressivo

**Tipografia**:
- Usar system fonts (sem carregar fontes externas = mais rapido no celular)
- `-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`
- Titulos bold, corpo regular

**Logo/Branding**:
- Nome grande e claro no topo: "FREE SANDMANN"
- Pode ter um icone simples (corrente quebrada, escudo, balanca da justica)
- Nao precisa ser elaborado — clareza > design sofisticado

---

### Elementos que Aumentam Conversao de Doacoes

1. **Hero com foto pessoal** (opcional, admin pode subir via settings)
   - Rostos humanos geram empatia e confianca
   - Se nao quiser foto, usar iniciais grandes ou avatar estiizado

2. **Barra de progresso proeminente**
   - No TOPO da pagina, antes de qualquer texto
   - Mostrar: "0.73 / 2.5 BTC arrecadados (29%)"
   - Cor laranja preenchendo, fundo cinza
   - Efeito psicologico: as pessoas querem completar barras

3. **Numero de apoiadores** (opcional)
   - Adicionar campo `supporters_count` no config
   - Admin atualiza manualmente
   - "47 pessoas ja apoiaram" — prova social

4. **Urgencia e timeline**
   - Secao "Proximos passos" ou "Prazos" na homepage
   - Ex: "Audiencia marcada para 15/04 — precisamos do advogado ate la"
   - Deadline visivel cria urgencia real

5. **CTA (Call to Action) claro e repetido**
   - Botao "Doar agora" no hero, no meio da pagina, e no final
   - No mobile: botao sticky no rodape (sempre visivel)
   - Cor laranja (#f7931a), texto branco, cantos arredondados
   - Texto do botao: "Ajude Agora" ou "Doar Bitcoin" (direto, sem rodeios)

6. **Secao "Por que preciso de ajuda"**
   - Resumo em 3-4 bullet points curtos (nao paragrafos longos)
   - Timeline visual dos eventos (opcional)
   - Links para documentos/evidencias
   - Tom: factual, nao vitimista — gera mais credibilidade

7. **Secao de transparencia**
   - "Para onde vai o dinheiro": discriminar custos (advogado, custas, etc)
   - Barra de progresso por categoria (se quiser detalhar)
   - Link para wallet publica (para quem quiser verificar on-chain)

8. **Compartilhamento facil**
   - Botoes "Compartilhar no Twitter/Telegram/WhatsApp" em cada artigo e na homepage
   - Pre-preenchidos com texto + link do site
   - No mobile, usar Web Share API (menu nativo de compartilhar do celular)

---

### Melhorias de Usabilidade

1. **Copiar endereco com um toque**
   - Ao lado de cada endereco BTC/Lightning, botao "Copiar"
   - Feedback visual: "Copiado!" por 2 segundos
   - Icone de clipboard, nao so texto

2. **Deep link para wallets**
   - Link `bitcoin:<endereco>` que abre a wallet do usuario automaticamente
   - Link `lightning:<invoice>` para Lightning wallets
   - No mobile, isso abre o app de carteira direto

3. **Instrucoes para iniciantes**
   - Secao "Primeira vez doando Bitcoin?" na pagina de doacao
   - 3 passos simples com icones
   - Link para wallets recomendadas (Muun, Coinos, Blue Wallet)

4. **Pagina carregando rapido**
   - Pico CSS via CDN (cacheado)
   - QR codes com lazy loading (`loading="lazy"`)
   - Nenhuma fonte externa, nenhum JS pesado
   - Meta: < 1 segundo para First Contentful Paint

5. **SEO basico**
   - Meta tags Open Graph (para preview bonito ao compartilhar no Twitter/Telegram)
   - `og:title`, `og:description`, `og:image` (preview do site)
   - Admin pode configurar imagem OG via settings

---

### Mudancas no Schema (adicionais)

Adicionar ao `config`:
- `hero_image_url` — URL de foto pessoal ou banner (opcional)
- `supporters_count` — numero de apoiadores (atualizado manualmente)
- `deadline_text` — texto de urgencia/prazo (ex: "Audiencia em 15/04")
- `transparency_text` — descricao de para onde vai o dinheiro (Markdown)
- `og_image_url` — imagem para preview ao compartilhar em redes sociais
- `wallet_explorer_url` — link para explorer on-chain (transparencia)

Esses sao apenas chaves novas na tabela `config` (key-value), nao precisam de migracao.

---

### Estrutura Visual Revisada

#### Homepage (mobile, de cima pra baixo)

```
┌─────────────────────────┐
│  FREE SANDMANN     [≡]  │  ← logo + hamburger menu
├─────────────────────────┤
│  ██████████░░░░  29%    │  ← barra de progresso
│  0.73 / 2.5 BTC        │
│  47 apoiadores          │
├─────────────────────────┤
│                         │
│  [Foto ou Banner]       │  ← hero image (opcional)
│                         │
│  Estou sendo acusado    │
│  injustamente de ...    │
│  Preciso de ajuda para  │
│  pagar minha defesa.    │
│                         │
│  [ AJUDE AGORA 🟠 ]    │  ← CTA principal
│                         │
├─────────────────────────┤
│  POR QUE PRECISO        │
│  • Ponto 1              │
│  • Ponto 2              │
│  • Ponto 3              │
│  → Leia mais            │
├─────────────────────────┤
│  TRANSPARENCIA          │
│  Advogado: 1.5 BTC      │
│  Custas: 0.5 BTC        │
│  Outros: 0.5 BTC        │
│  [Ver wallet publica]   │
├─────────────────────────┤
│  COMO DOAR              │
│  ┌─────────┐            │
│  │ QR BTC  │            │
│  └─────────┘            │
│  bc1q... [Copiar]       │
│                         │
│  ┌─────────┐            │
│  │ QR LN   │            │
│  └─────────┘            │
│  lnurl... [Copiar]      │
├─────────────────────────┤
│  ATUALIZACOES           │
│  → Artigo fixado 1      │
│  → Artigo fixado 2      │
│  [Ver todos →]          │
├─────────────────────────┤
│  MIDIA E COBERTURA      │
│  🎥 Video 1             │
│  🐦 Tweet 1             │
│  📰 Artigo 1            │
├─────────────────────────┤
│  Compartilhar:          │
│  [Twitter] [Telegram]   │
│  [WhatsApp] [Copiar]    │
├─────────────────────────┤
│  footer + github link   │
└─────────────────────────┘
┌─────────────────────────┐
│    [ DOAR AGORA  🟠 ]   │  ← sticky bottom bar (sempre visivel)
└─────────────────────────┘
```

#### Homepage (desktop, layout expandido)

```
┌──────────────────────────────────────────────────────┐
│  FREE SANDMANN          Home  Updates  [Doar Agora]  │
├──────────────────────────────────────────────────────┤
│  ████████████████░░░░░░░░░░  29%  •  0.73/2.5 BTC   │
├──────────────────────────────────────────────────────┤
│                                                      │
│  ┌──────────────────┐  ┌──────────────────────────┐  │
│  │                  │  │                          │  │
│  │  [Foto/Banner]   │  │  Estou sendo acusado...  │  │
│  │                  │  │                          │  │
│  │                  │  │  [ AJUDE AGORA  🟠 ]     │  │
│  └──────────────────┘  └──────────────────────────┘  │
│                                                      │
├───────────────────────┬──────────────────────────────┤
│  POR QUE PRECISO      │  COMO DOAR                   │
│  • Ponto 1            │  ┌─────┐  ┌─────┐           │
│  • Ponto 2            │  │ BTC │  │ LN  │           │
│  • Ponto 3            │  └─────┘  └─────┘           │
│                       │  bc1q... [Copiar]            │
│  TRANSPARENCIA        │  lnurl.. [Copiar]            │
│  Advogado: 1.5 BTC    │                              │
│  Custas: 0.5 BTC      │                              │
├───────────────────────┴──────────────────────────────┤
│  ATUALIZACOES          │  MIDIA E COBERTURA          │
│  → Artigo 1            │  🎥 Video 1                 │
│  → Artigo 2            │  🐦 Tweet 1                 │
│  [Ver todos →]         │  📰 Artigo 1                │
├──────────────────────────────────────────────────────┤
│  Compartilhar: [Twitter] [Telegram] [WhatsApp]       │
├──────────────────────────────────────────────────────┤
│  footer + github link                                │
└──────────────────────────────────────────────────────┘
```

---

### Pagina de Doacao (mobile)

```
┌─────────────────────────┐
│  FREE SANDMANN     [≡]  │
├─────────────────────────┤
│  ██████████░░░░  29%    │
│  0.73 / 2.5 BTC        │
├─────────────────────────┤
│                         │
│  BITCOIN ON-CHAIN       │
│  ┌─────────────┐       │
│  │             │       │
│  │   QR CODE   │       │
│  │   (grande)  │       │
│  │             │       │
│  └─────────────┘       │
│  bc1qxy2kgdyg...       │
│  [ Copiar Endereco ]   │
│  [ Abrir Wallet → ]    │
│                         │
├─────────────────────────┤
│                         │
│  LIGHTNING NETWORK      │
│  ┌─────────────┐       │
│  │             │       │
│  │   QR CODE   │       │
│  │   (grande)  │       │
│  │             │       │
│  └─────────────┘       │
│  lnurl1dp68gurn...      │
│  [ Copiar Endereco ]   │
│  [ Abrir Wallet → ]    │
│                         │
├─────────────────────────┤
│  PRIMEIRA VEZ?          │
│  1. Baixe uma wallet    │
│     (Muun, Coinos)     │
│  2. Escaneie o QR code  │
│  3. Confirme o envio    │
├─────────────────────────┤
│  footer                 │
└─────────────────────────┘
```
