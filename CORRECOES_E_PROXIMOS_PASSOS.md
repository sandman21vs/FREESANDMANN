# CORRECOES E PROXIMOS PASSOS

**Data**: 2026-03-26
**Estado**: App rodando em http://localhost:8000, 112 testes passando

---

## CORRECOES NECESSARIAS (bugs encontrados na auditoria)

### BUG 1 — `requirements.txt`: nome do pacote errado
- **Problema**: Estava `python-qrcode[pil]==8.0`, mas o pacote no PyPI se chama `qrcode`
- **Status**: JA CORRIGIDO nesta sessao
- **Arquivo**: `requirements.txt` linha 3
- **Impacto**: `pip install` falhava; Docker build tambem falharia

### BUG 2 — `datetime.utcnow()` deprecado
- **Problema**: Python 3.12+ emite `DeprecationWarning` para `datetime.utcnow()`
- **Arquivo**: `models.py` linhas 171 e 265
- **Correcao**: Trocar `datetime.utcnow()` por `datetime.now(datetime.UTC)`
- **Impacto**: Funcional por enquanto, mas vai quebrar em Python 3.14+

### BUG 3 — Banco de dados vem "sujo" dos testes do Sonnet
- **Problema**: O Sonnet rodou testes que mudaram a senha no banco de producao. Login com FREE/FREE falhava.
- **Status**: JA CORRIGIDO nesta sessao (banco recriado com `rm data/freesandmann.db && python init_db.py`)
- **Prevencao**: O conftest.py ja usa banco temporario, mas se alguem rodar `python app.py` durante os testes, o banco real pode ser afetado
- **Correcao permanente**: Adicionar ao `.env.example` um aviso, e no `init_db.py` verificar se ja existe banco antes de sobrescrever

### BUG 4 — Dockerfile usa pacote errado
- **Problema**: Se o requirements.txt foi commitado com `python-qrcode`, o Docker build tambem falha
- **Status**: JA CORRIGIDO (requirements.txt atualizado para `qrcode[pil]==8.0`)
- **Acao**: Fazer novo commit com a correcao

---

## PROBLEMAS DE UX ENCONTRADOS

### UX 1 — Secao "How to Donate" aparece vazia na homepage
- **Problema**: Sem enderecos BTC/Lightning configurados, a secao QR fica vazia (so aparece o titulo "How to Donate" sem conteudo)
- **Correcao**: Envolver a secao em `{% if cfg.get('btc_address') or cfg.get('lightning_address') %}` para esconder quando nao ha enderecos configurados, OU mostrar uma mensagem como "Donation addresses not yet configured"
- **Arquivo**: `templates/index.html` linhas 31-34

### UX 2 — Pagina de doacao vazia sem enderecos
- **Problema**: Mesma situacao na `/donate` — QR section vazia
- **Correcao**: Mostrar mensagem amigavel quando enderecos nao estao configurados
- **Arquivo**: `templates/donate.html`

### UX 3 — Transparencia renderiza texto cru (nao Markdown)
- **Problema**: O campo `transparency_text` aceita Markdown no admin, mas no `index.html` e renderizado como texto puro (`{{ cfg.get('transparency_text') }}`)
- **Correcao**: Usar `{{ cfg.get('transparency_text')|safe }}` se o texto ja vier renderizado, OU renderizar Markdown no template com um filtro custom. Melhor opcao: renderizar no `set_config` salvando HTML, ou criar filtro Jinja2 `|markdown`
- **Arquivo**: `templates/index.html` linha 24

### UX 4 — Sem mensagem de boas-vindas quando site esta vazio
- **Problema**: Homepage nova sem artigos, sem enderecos, sem nada configurado parece um site quebrado
- **Correcao**: Adicionar estado "empty" na homepage com instrucoes basicas: "Este site ainda esta sendo configurado. Acesse /admin/login para comecar."
- **Nota**: Essa mensagem so deve aparecer se NENHUM conteudo estiver configurado (sem artigos, sem enderecos)

---

## MELHORIAS PENDENTES (da ARCHITECTURE.md que nao foram implementadas)

### M1 — Web Share API nativa no mobile
- **Descrito em**: ARCHITECTURE.md secao "Compartilhamento facil"
- **Status**: Nao implementado. Botoes de share usam links diretos (Twitter, Telegram, WhatsApp)
- **Correcao**: Adicionar JS inline que detecta `navigator.share` e usa API nativa se disponivel, fallback para links diretos
- **Arquivo**: `templates/components/embed.html`

### M2 — Nav hamburger no mobile
- **Descrito em**: ARCHITECTURE.md secao "Mobile First"
- **Status**: Nao implementado. Nav usa layout padrao do Pico CSS
- **Correcao**: Pico CSS v2 nao tem hamburger nativo. Opcoes:
  - A) Adicionar ~15 linhas de JS/CSS para toggle hamburger
  - B) Simplificar nav no mobile para so "Logo + Donate" (esconder Home/Updates)
  - Recomendacao: Opcao B e mais simples e alinhada com o principio de simplicidade

### M3 — Contagem automatica de transacoes como "supporters"
- **Descrito em**: ARCHITECTURE.md secao "Numero de apoiadores"
- **Status**: Campo existe (manual), mas nao atualiza automaticamente
- **Correcao futura**: Na funcao `check_onchain_balance()`, alem do saldo, contar `data["chain_stats"]["tx_count"]` da API mempool.space e atualizar `supporters_count` automaticamente
- **Arquivo**: `models.py` funcao `check_onchain_balance()`

### M4 — Favicon
- **Status**: Nao existe. Navegador mostra icone padrao
- **Correcao**: Gerar favicon simples (Bitcoin laranja ou letra "F") e adicionar `<link rel="icon">` no `base.html`
- **Arquivo**: `static/favicon.ico` ou `static/favicon.svg` + `templates/base.html`

### M5 — Logo placeholder
- **Descrito em**: ARCHITECTURE.md estrutura de arquivos (`static/logo.png`)
- **Status**: Arquivo nao existe
- **Correcao**: Criar ou adicionar placeholder. Nao e critico — o titulo texto funciona bem

---

## PROXIMOS PASSOS (em ordem de prioridade)

### Prioridade 1 — Correcoes criticas (fazer agora)

```
[ ] Corrigir datetime.utcnow() → datetime.now(datetime.UTC) em models.py
[ ] Esconder secao QR na homepage/donate quando enderecos estao vazios
[ ] Renderizar transparency_text como Markdown (nao texto cru)
[ ] Commit com todas as correcoes
```

### Prioridade 2 — Configurar seu site (fazer agora, no admin)

```
[ ] Acessar http://localhost:8000/admin/login
[ ] Login: FREE / FREE
[ ] Trocar senha (obrigatorio, minimo 8 caracteres)
[ ] Em Settings:
    [ ] Mudar titulo do site (ex: "Free Sandmann" ou seu nome)
    [ ] Escrever descricao (explicar sua situacao)
    [ ] Colocar endereco BTC on-chain
    [ ] Colocar endereco Lightning (se tiver)
    [ ] Definir meta em BTC
    [ ] Escrever texto de transparencia (custos do advogado)
    [ ] Definir deadline se aplicavel
[ ] Criar primeiro artigo explicando o caso
[ ] Adicionar media links (Twitter threads, videos, artigos)
```

### Prioridade 3 — Docker e deploy

```
[ ] Testar Docker build: docker compose build
[ ] Testar Docker run: docker compose up -d
[ ] Verificar http://localhost:8000 no container
[ ] Configurar .env com SECRET_KEY forte (gerar com: python -c "import os; print(os.urandom(32).hex())")
[ ] Configurar Cloudflare Tunnel para freesandmann.sandlabs.store
[ ] Testar acesso externo
```

### Prioridade 4 — Melhorias visuais

```
[ ] Adicionar favicon
[ ] Implementar hamburger menu ou simplificar nav mobile
[ ] Adicionar Web Share API nativa
[ ] Testar em celular real (ou Chrome DevTools mobile viewport)
[ ] Ajustar estilos se necessario apos ver no celular
```

### Prioridade 5 — GitHub

```
[ ] Criar repositorio no GitHub: freesandmann/freesandmann
[ ] Atualizar link no footer (base.html) para URL real do repo
[ ] Push: git remote add origin <url> && git push -u origin main
[ ] Verificar que README.md aparece bonito no GitHub
[ ] Adicionar topic tags: bitcoin, fundraising, legal-defense, self-hosted
```

### Prioridade 6 — Futuro (apos lançamento)

```
[ ] Integrar API Coinos.io para Lightning automatico
[ ] Contador automatico de supporters via tx_count da mempool.space
[ ] Sistema de notificacao (Telegram bot) quando receber doacao
[ ] Traducao PT/EN (site bilingue)
[ ] Pagina de FAQ
[ ] SSL certificate pinning no Cloudflare
```

---

## COMANDOS UTEIS

```bash
# Iniciar app local
source venv/bin/activate && python app.py

# Rodar testes
source venv/bin/activate && python -m pytest tests/ -v

# Resetar banco (senha volta para FREE/FREE)
rm data/freesandmann.db && source venv/bin/activate && python init_db.py

# Gerar SECRET_KEY forte
python -c "import os; print(os.urandom(32).hex())"

# Docker
docker compose build
docker compose up -d
docker compose logs -f
docker compose down

# Ver estado do banco
source venv/bin/activate && python -c "import models; print(models.get_all_config())"
```
