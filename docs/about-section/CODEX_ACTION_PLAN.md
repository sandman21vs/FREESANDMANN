# Profile / About Section — Codex Action Plan

This document contains step-by-step implementation instructions for adding a
generic "Profile & Background" feature to Bastion. Each step lists the exact
files to create or modify, the changes required, and acceptance criteria.

The feature allows any campaign owner to publish a public "Who am I?" page
with a short homepage teaser. It is optional, disabled by default, and
fully generic (no hardcoded names).

---

## Architecture overview

```
config.py          → new default keys (profile_*)
init_db.py         → new table: profile_links
model_config.py    → new translatable fields, validation
model_profile.py   → NEW: CRUD for profile_links table
service_profile.py → NEW: business logic for profile settings + links
routes_admin.py    → new route: /admin/profile (GET/POST)
routes_public.py   → new route: /about (GET)
templates/admin/profile.html        → NEW: admin form
templates/about.html                → NEW: public page
templates/components/profile_teaser.html → NEW: homepage block
templates/index.html                → include teaser
templates/base.html                 → nav link to /about
templates/base_admin.html           → sidebar link to Profile
translations/{pt,en,de}.json        → new UI strings
static/style.css                    → minimal styling
```

---

## Step 1 — Config defaults and DB schema

### 1a. `config.py`

Add to `DEFAULTS` dict (after the existing `liquid_address` entry):

```python
# Profile / About section
"profile_enabled": "0",
"profile_display_name": "",
"profile_heading": "",
"profile_summary_md": "",
"profile_long_bio_md": "",
"profile_commitment_md": "",
"profile_avatar_url": "",
```

Add the translatable loop at the bottom of config.py — extend the existing
loop or add a second one for profile fields:

```python
for field in (
    "profile_heading",
    "profile_summary_md",
    "profile_long_bio_md",
    "profile_commitment_md",
):
    DEFAULTS[f"{field}_en"] = ""
    DEFAULTS[f"{field}_de"] = ""
```

### 1b. `init_db.py`

Add a new table after `article_approvals`:

```python
conn.execute("""
    CREATE TABLE IF NOT EXISTS profile_links (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        title       TEXT NOT NULL,
        title_en    TEXT NOT NULL DEFAULT '',
        title_de    TEXT NOT NULL DEFAULT '',
        url         TEXT NOT NULL,
        category    TEXT NOT NULL DEFAULT 'other',
        description TEXT NOT NULL DEFAULT '',
        description_en TEXT NOT NULL DEFAULT '',
        description_de TEXT NOT NULL DEFAULT '',
        sort_order  INTEGER NOT NULL DEFAULT 0,
        featured    INTEGER NOT NULL DEFAULT 0,
        created_at  TEXT DEFAULT (datetime('now'))
    )
""")
```

Valid categories (enforce in validation, not DB constraint):
`podcast`, `github`, `project`, `crowdfunding`, `tutorial`, `talk`,
`community`, `press`, `other`.

### Acceptance criteria
- `python3 init_db.py` runs without error
- `profile_links` table exists
- `models.get_all_config()` returns all new `profile_*` keys with empty defaults

---

## Step 2 — Model layer

### 2a. `model_config.py`

Add profile fields to `TRANSLATABLE_SETTINGS_FIELDS`:

```python
TRANSLATABLE_SETTINGS_FIELDS = (
    "site_title",
    "site_description",
    "site_tagline",
    "goal_description",
    "deadline_text",
    "transparency_text",
    # Profile section
    "profile_heading",
    "profile_summary_md",
    "profile_long_bio_md",
    "profile_commitment_md",
)
```

Add profile text fields to `SETTINGS_TEXT_FIELDS`:

```python
# Add these to the tuple:
"profile_display_name",
"profile_heading",
"profile_summary_md",
"profile_long_bio_md",
"profile_commitment_md",
"profile_avatar_url",
```

Add `profile_avatar_url` to `SETTINGS_URL_FIELDS`:

```python
"profile_avatar_url": "Profile Avatar URL",
```

In `validate_settings_form`, handle the `profile_enabled` checkbox the same
way `coinos_enabled` is handled:

```python
profile_enabled = "1" if form_data.get("profile_enabled") else "0"
form_cfg["profile_enabled"] = profile_enabled
normalized["profile_enabled"] = profile_enabled
```

### 2b. `model_profile.py` (NEW file)

Simple CRUD for `profile_links`. Follow the same pattern as media_links in
the existing models but with more fields.

```python
"""Data access for the profile_links table."""

from db import get_db

VALID_CATEGORIES = (
    "podcast", "github", "project", "crowdfunding",
    "tutorial", "talk", "community", "press", "other",
)


def get_profile_links():
    """Return all profile links ordered by sort_order, then id."""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM profile_links ORDER BY sort_order, id"
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_featured_profile_links(limit=3):
    """Return featured links for homepage teaser."""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM profile_links WHERE featured = 1 "
        "ORDER BY sort_order, id LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_profile_links_grouped():
    """Return links grouped by category as {category: [links]}."""
    links = get_profile_links()
    grouped = {}
    for link in links:
        cat = link["category"]
        grouped.setdefault(cat, []).append(link)
    return grouped


def get_profile_link_by_id(link_id):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM profile_links WHERE id = ?", (link_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def add_profile_link(title, url, category="other", description="",
                     sort_order=0, featured=False,
                     title_en="", title_de="",
                     description_en="", description_de=""):
    conn = get_db()
    conn.execute(
        "INSERT INTO profile_links "
        "(title, url, category, description, sort_order, featured, "
        " title_en, title_de, description_en, description_de) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (title, url, category, description, sort_order,
         1 if featured else 0,
         title_en, title_de, description_en, description_de),
    )
    conn.commit()
    conn.close()


def update_profile_link(link_id, **kwargs):
    allowed = {
        "title", "url", "category", "description",
        "sort_order", "featured",
        "title_en", "title_de", "description_en", "description_de",
    }
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return
    if "featured" in fields:
        fields["featured"] = 1 if fields["featured"] else 0
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [link_id]
    conn = get_db()
    conn.execute(
        f"UPDATE profile_links SET {set_clause} WHERE id = ?", values
    )
    conn.commit()
    conn.close()


def delete_profile_link(link_id):
    conn = get_db()
    conn.execute("DELETE FROM profile_links WHERE id = ?", (link_id,))
    conn.commit()
    conn.close()
```

### 2c. `models.py`

Add imports from the new module so the rest of the app can use `models.*`:

```python
from model_profile import *  # noqa: F403
```

(Follow the same pattern already used for other model_*.py files.)

### Acceptance criteria
- All profile config fields validate and save correctly
- CRUD operations on profile_links work
- `get_featured_profile_links(3)` returns max 3 featured links
- `get_profile_links_grouped()` returns a dict keyed by category

---

## Step 3 — Service layer

### `service_profile.py` (NEW file)

Thin service with validation for profile link add/update and markdown
rendering for the public page.

```python
"""Service helpers for profile / about section."""

import models
from app_hooks import render_safe_markdown


def add_profile_link_from_form(form_data):
    title = form_data.get("title", "").strip()
    url = form_data.get("url", "").strip()
    category = form_data.get("category", "other").strip()
    description = form_data.get("description", "").strip()
    sort_order_raw = form_data.get("sort_order", "0").strip()
    featured = bool(form_data.get("featured"))

    if not title or not url:
        return {"ok": False, "message": "Title and URL are required."}

    if category not in models.VALID_CATEGORIES:
        category = "other"

    try:
        sort_order = int(sort_order_raw)
    except (TypeError, ValueError):
        sort_order = 0

    models.add_profile_link(
        title=title,
        url=url,
        category=category,
        description=description,
        sort_order=sort_order,
        featured=featured,
        title_en=form_data.get("title_en", "").strip(),
        title_de=form_data.get("title_de", "").strip(),
        description_en=form_data.get("description_en", "").strip(),
        description_de=form_data.get("description_de", "").strip(),
    )
    return {"ok": True, "message": "Link added."}


def update_profile_link_from_form(link_id, form_data):
    link = models.get_profile_link_by_id(link_id)
    if not link:
        return {"ok": False, "status": "not_found"}

    title = form_data.get("title", "").strip()
    url = form_data.get("url", "").strip()
    if not title or not url:
        return {"ok": False, "message": "Title and URL are required."}

    category = form_data.get("category", link["category"]).strip()
    if category not in models.VALID_CATEGORIES:
        category = "other"

    sort_order_raw = form_data.get("sort_order", str(link["sort_order"])).strip()
    try:
        sort_order = int(sort_order_raw)
    except (TypeError, ValueError):
        sort_order = link["sort_order"]

    models.update_profile_link(
        link_id,
        title=title,
        url=url,
        category=category,
        description=form_data.get("description", "").strip(),
        sort_order=sort_order,
        featured=bool(form_data.get("featured")),
        title_en=form_data.get("title_en", "").strip(),
        title_de=form_data.get("title_de", "").strip(),
        description_en=form_data.get("description_en", "").strip(),
        description_de=form_data.get("description_de", "").strip(),
    )
    return {"ok": True, "message": "Link updated."}


def get_public_profile_context(lang="pt"):
    """Build context dict for the /about page."""
    cfg = models.get_all_config()

    if cfg.get("profile_enabled") != "1":
        return None

    suffix = f"_{lang}" if lang in ("en", "de") else ""

    def _localized(field):
        if suffix:
            val = cfg.get(f"{field}{suffix}", "").strip()
            if val:
                return val
        return cfg.get(field, "").strip()

    summary_md = _localized("profile_summary_md")
    bio_md = _localized("profile_long_bio_md")
    commitment_md = _localized("profile_commitment_md")

    links = models.get_profile_links()
    # Localize link titles/descriptions
    for link in links:
        if suffix:
            t = link.get(f"title{suffix}", "").strip()
            d = link.get(f"description{suffix}", "").strip()
            if t:
                link["title"] = t
            if d:
                link["description"] = d

    grouped = {}
    for link in links:
        grouped.setdefault(link["category"], []).append(link)

    featured = [l for l in links if l["featured"]][:3]

    return {
        "display_name": cfg.get("profile_display_name", ""),
        "heading": _localized("profile_heading"),
        "avatar_url": cfg.get("profile_avatar_url", ""),
        "summary_html": render_safe_markdown(summary_md) if summary_md else "",
        "bio_html": render_safe_markdown(bio_md) if bio_md else "",
        "commitment_html": render_safe_markdown(commitment_md) if commitment_md else "",
        "links_grouped": grouped,
        "featured_links": featured,
    }
```

> **Note:** `render_safe_markdown` should already exist in `app_hooks.py`.
> If it doesn't, check how `transparency_text` is rendered and use the same
> approach. The function should sanitize HTML output (no raw script tags).

### Acceptance criteria
- `get_public_profile_context("pt")` returns None when disabled
- Returns full dict with rendered HTML when enabled
- Link localization works (EN/DE titles override PT when present)

---

## Step 4 — Admin routes and template

### 4a. `routes_admin.py`

Add new imports at top:

```python
from service_profile import (
    add_profile_link_from_form,
    update_profile_link_from_form,
)
```

Add these routes inside `register_admin_routes(app)`, after the lawyers
section:

```python
@app.route("/admin/profile", methods=["GET", "POST"])
@login_required
def admin_profile():
    current_cfg = models.get_all_config()

    if request.method == "POST":
        action = request.form.get("action", "save_settings")

        if action == "add_link":
            result = add_profile_link_from_form(request.form)
            flash(result["message"], "success" if result["ok"] else "error")
            return redirect(url_for("admin_profile"))

        if action == "update_link":
            link_id = request.form.get("link_id", type=int)
            if link_id:
                result = update_profile_link_from_form(link_id, request.form)
                flash(result["message"], "success" if result["ok"] else "error")
            return redirect(url_for("admin_profile"))

        # Default: save profile settings (same pattern as admin_settings)
        result = process_admin_settings(request.form, current_cfg)
        if not result["ok"]:
            for error in result["errors"]:
                flash(error, "error")
            links = models.get_profile_links()
            return render_template(
                "admin/profile.html", cfg=result["cfg"], links=links
            ), 200
        flash("Profile settings saved.", "success")
        return redirect(url_for("admin_profile"))

    links = models.get_profile_links()
    return render_template("admin/profile.html", cfg=current_cfg, links=links)


@app.route("/admin/profile/links/<int:link_id>/delete", methods=["POST"])
@login_required
def admin_profile_link_delete(link_id):
    models.delete_profile_link(link_id)
    flash("Link deleted.", "success")
    return redirect(url_for("admin_profile"))
```

### 4b. `templates/admin/profile.html` (NEW file)

Create a new admin page following the same structure as `settings.html`.
Use `extends "base_admin.html"` and `page_header` macro.

Structure:

```
Section nav: #section-profile-settings | #section-profile-links

Fieldset "Profile Settings":
  - Enable checkbox (profile_enabled)
  - Display Name (text input)
  - Avatar URL (text input)
  - Heading (text, + EN/DE in <details>)
  - Short Summary (textarea, markdown, + EN/DE in <details>)
  - Long Biography (textarea, markdown, + EN/DE in <details>)
  - Public Commitment (textarea, markdown, + EN/DE in <details>)
  - Save button (action=save_settings)

Fieldset "Profile Links":
  - Table of existing links: title | url | category | featured | actions (edit/delete)
  - "Add Link" form below the table:
    title, url, category (select), description, sort_order, featured (checkbox)
    EN/DE translations in <details>
    Submit button (action=add_link)
```

Follow the same i18n pattern as settings.html (`<details class="bo-expandable">`
for EN and DE translations).

The category `<select>` should list all valid categories with human-readable
labels (Podcast, GitHub, Project, Crowdfunding, Tutorial, Talk, Community,
Press, Other).

### 4c. `templates/base_admin.html`

Add sidebar link. Insert after the Settings link:

```html
<li><a href="{{ url_for('admin_profile') }}" class="{% if request.endpoint in ('admin_profile', 'admin_profile_link_delete') %}active{% endif %}">Profile & About</a></li>
```

### Acceptance criteria
- `/admin/profile` renders with all fields
- Can enable/disable profile
- Can save all text fields with EN/DE translations
- Can add, edit, and delete profile links
- Sidebar shows "Profile & About" with active state

---

## Step 5 — Public routes and templates

### 5a. `routes_public.py`

Add import:

```python
from service_profile import get_public_profile_context
```

Add route after the `donate` route:

```python
@app.route("/about")
def about():
    lang = session.get("lang", "pt")
    profile = get_public_profile_context(lang)
    if not profile:
        abort(404)
    return render_template("about.html", profile=profile)
```

### 5b. `templates/about.html` (NEW file)

```html
{% extends "base.html" %}

{% block title %}{{ profile.heading or profile.display_name }} &mdash; {{ cfg.get('site_title', 'Bastion') }}{% endblock %}

{% block content %}
<article class="profile-page">
    <header class="profile-header">
        {% if profile.avatar_url %}
        <img src="{{ profile.avatar_url }}" alt="{{ profile.display_name }}"
             class="profile-avatar">
        {% endif %}
        <h1>{{ profile.heading or t('about_heading_default') }}</h1>
    </header>

    {% if profile.summary_html %}
    <section class="profile-summary">
        {{ profile.summary_html|safe }}
    </section>
    {% endif %}

    {% if profile.bio_html %}
    <section class="profile-bio">
        {{ profile.bio_html|safe }}
    </section>
    {% endif %}

    {% if profile.commitment_html %}
    <section class="profile-commitment">
        <h2>{{ t('profile_commitment_heading') }}</h2>
        {{ profile.commitment_html|safe }}
    </section>
    {% endif %}

    {% if profile.links_grouped %}
    <section class="profile-links">
        <h2>{{ t('profile_links_heading') }}</h2>
        {% for category, links in profile.links_grouped.items() %}
        <div class="profile-link-group">
            <h3>{{ t('profile_cat_' ~ category) }}</h3>
            <ul>
                {% for link in links %}
                <li>
                    <a href="{{ link.url }}" target="_blank" rel="noopener">
                        {{ link.title }}
                    </a>
                    {% if link.description %}
                    <small>{{ link.description }}</small>
                    {% endif %}
                </li>
                {% endfor %}
            </ul>
        </div>
        {% endfor %}
    </section>
    {% endif %}
</article>

<nav class="profile-back">
    <a href="{{ url_for('index') }}">&larr; {{ t('go_back_home') }}</a>
</nav>
{% endblock %}
```

### 5c. `templates/components/profile_teaser.html` (NEW file)

Homepage teaser block. Called from index.html.

```html
{% macro profile_teaser(profile) %}
{% if profile %}
<section class="profile-teaser">
    <h2>{{ profile.heading or t('about_heading_default') }}</h2>
    {% if profile.avatar_url %}
    <img src="{{ profile.avatar_url }}" alt="{{ profile.display_name }}"
         class="profile-teaser-avatar">
    {% endif %}
    {% if profile.summary_html %}
    <div class="profile-teaser-text">
        {{ profile.summary_html|safe }}
    </div>
    {% endif %}
    {% if profile.featured_links %}
    <ul class="profile-teaser-links">
        {% for link in profile.featured_links %}
        <li>
            <a href="{{ link.url }}" target="_blank" rel="noopener">{{ link.title }}</a>
        </li>
        {% endfor %}
    </ul>
    {% endif %}
    <a href="{{ url_for('about') }}" class="profile-cta">{{ t('profile_learn_more') }}</a>
</section>
{% endif %}
{% endmacro %}
```

### 5d. `templates/index.html`

Add import at top:

```html
{% from "components/profile_teaser.html" import profile_teaser with context %}
```

Insert the teaser block AFTER the hero section and BEFORE transparency:

```html
{{ profile_teaser(profile) }}
```

### 5e. `routes_public.py` — update `index()` route

Pass profile context to the homepage:

```python
@app.route("/")
def index():
    lang = session.get("lang", "pt")
    articles = models.get_articles_for_lang(published_only=True, lang=lang)
    pinned = [a for a in articles if a["pinned"]]
    media_links = models.get_media_links()
    profile = get_public_profile_context(lang)
    return render_template(
        "index.html",
        articles=articles, pinned=pinned,
        media_links=media_links, profile=profile,
    )
```

### 5f. `templates/base.html` — add nav link

Add "About" link in the navigation, conditionally shown when profile is
enabled. Insert after Updates and before Donate:

```html
{% if cfg.get('profile_enabled') == '1' %}
<li><a href="{{ url_for('about') }}">{{ t('nav_about') }}</a></li>
{% endif %}
```

Add in BOTH places: the desktop `nav-links` and the footer nav list.

### Acceptance criteria
- `/about` returns 404 when `profile_enabled` is `"0"`
- `/about` renders full profile when enabled
- Homepage shows teaser with summary + up to 3 featured links
- "About" link appears in nav and footer only when enabled
- All text respects current language (PT/EN/DE)

---

## Step 6 — Translations

Add these keys to ALL THREE translation files:

### `translations/pt.json`

```json
"nav_about": "Sobre",
"about_heading_default": "Quem sou eu?",
"profile_commitment_heading": "Compromissos e Valores",
"profile_links_heading": "Onde Verificar",
"profile_learn_more": "Saiba mais sobre mim",
"profile_cat_podcast": "Podcasts e Entrevistas",
"profile_cat_github": "GitHub e Projetos",
"profile_cat_project": "Projetos e Iniciativas",
"profile_cat_crowdfunding": "Financiamento Coletivo",
"profile_cat_tutorial": "Tutoriais e Educação",
"profile_cat_talk": "Palestras e Eventos",
"profile_cat_community": "Comunidade",
"profile_cat_press": "Imprensa",
"profile_cat_other": "Outros"
```

### `translations/en.json`

```json
"nav_about": "About",
"about_heading_default": "Who am I?",
"profile_commitment_heading": "Commitments & Values",
"profile_links_heading": "Where to Verify",
"profile_learn_more": "Learn more about me",
"profile_cat_podcast": "Podcasts & Interviews",
"profile_cat_github": "GitHub & Projects",
"profile_cat_project": "Projects & Initiatives",
"profile_cat_crowdfunding": "Crowdfunding",
"profile_cat_tutorial": "Tutorials & Education",
"profile_cat_talk": "Talks & Events",
"profile_cat_community": "Community",
"profile_cat_press": "Press",
"profile_cat_other": "Other"
```

### `translations/de.json`

```json
"nav_about": "Über mich",
"about_heading_default": "Wer bin ich?",
"profile_commitment_heading": "Verpflichtungen & Werte",
"profile_links_heading": "Wo prüfen",
"profile_learn_more": "Mehr über mich erfahren",
"profile_cat_podcast": "Podcasts & Interviews",
"profile_cat_github": "GitHub & Projekte",
"profile_cat_project": "Projekte & Initiativen",
"profile_cat_crowdfunding": "Crowdfunding",
"profile_cat_tutorial": "Tutorials & Bildung",
"profile_cat_talk": "Vorträge & Events",
"profile_cat_community": "Community",
"profile_cat_press": "Presse",
"profile_cat_other": "Sonstiges"
```

---

## Step 7 — Minimal CSS

Add to `static/style.css`:

```css
/* Profile / About page */
.profile-avatar,
.profile-teaser-avatar {
    border-radius: 50%;
    max-width: 120px;
}
.profile-header {
    text-align: center;
    margin-bottom: 2rem;
}
.profile-link-group { margin-bottom: 1.5rem; }
.profile-link-group ul { list-style: none; padding: 0; }
.profile-link-group li { margin-bottom: 0.5rem; }
.profile-link-group small { display: block; opacity: 0.7; }
.profile-teaser { text-align: center; }
.profile-teaser-links { list-style: none; padding: 0; display: flex; gap: 1rem; justify-content: center; flex-wrap: wrap; }
.profile-cta { display: inline-block; margin-top: 1rem; }
```

---

## Step 8 — Tests

Create `tests/test_profile.py` with:

1. **test_about_404_when_disabled** — GET `/about` returns 404 when
   `profile_enabled` is `"0"`.
2. **test_about_renders_when_enabled** — Set `profile_enabled=1`,
   `profile_display_name`, `profile_summary_md`, GET `/about` returns 200
   with display name in response.
3. **test_homepage_teaser_hidden_when_disabled** — GET `/` does not contain
   `profile-teaser` class.
4. **test_homepage_teaser_shown_when_enabled** — Enable profile, GET `/`
   contains `profile-teaser`.
5. **test_admin_profile_requires_login** — GET `/admin/profile` redirects
   to login.
6. **test_admin_can_save_profile_settings** — POST save settings, verify
   config persisted.
7. **test_admin_can_add_profile_link** — POST add link, verify in DB.
8. **test_admin_can_delete_profile_link** — POST delete, verify removed.
9. **test_profile_links_grouped** — Add links with different categories,
   verify grouping.
10. **test_profile_localization** — Set EN translations, request with
    `lang=en`, verify EN text appears.

Follow existing test patterns in `tests/`.

---

## Implementation order (recommended)

1. Steps 1-2 (config + models) — no UI changes, just data layer
2. Step 3 (service) — business logic, testable independently
3. Step 8 (tests) — write tests before templates to validate logic
4. Step 4 (admin routes + template) — admin can now manage profile
5. Steps 5-6 (public routes + templates + translations) — public can see it
6. Step 7 (CSS) — polish

---

## Important notes for Codex

- **Do NOT hardcode any personal names** — use `profile_display_name` from config everywhere.
- **Follow existing patterns exactly** — look at how `settings.html` handles checkboxes, text fields, and `<details>` for i18n.
- **CSRF** — all POST forms must include `<input type="hidden" name="csrf_token" value="{{ session.csrf_token }}">`.
- **Markdown rendering** — use the same safe renderer used for `transparency_text`. Check `app_hooks.py` for `render_safe_markdown` or equivalent.
- **The admin profile page is a SEPARATE page from settings** — do NOT add profile fields to the existing settings form. Keep them on `/admin/profile`.
- **The profile settings form submits to `/admin/profile`** and is processed by `process_admin_settings` (same function). This works because it just saves any config key it finds in the form. The profile-specific fields are already registered in `SETTINGS_TEXT_FIELDS`.
- **Keep templates simple** — no JavaScript required. Pure server-rendered HTML.
- **Run `pytest tests/ -v`** after implementation to verify nothing breaks.
