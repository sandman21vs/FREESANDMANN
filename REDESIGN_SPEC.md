# Backoffice Redesign Specification

> **Temporary file.** Remove from repo after implementation is complete.

This document is the implementation spec for the admin + lawyer backoffice redesign.
It was produced by an Opus-level architectural review of the full codebase.
Implement each phase in order. Do NOT skip phases. Commit after each phase.

---

## Guiding principles

- Dark-first, premium feel. Inspired by Umbrel Bitcoin Node UI (not a copy).
- Visual hierarchy through opacity/weight, not color overload.
- `--btc-orange` remains the primary accent. Role accent differs (orange=admin, blue=lawyer).
- Keep the stack: Flask + Jinja2 + Pico CSS base + custom CSS. No JS frameworks.
- Every change must work in both light and dark themes.
- Every change must remain responsive (mobile sidebar collapses to horizontal nav).
- Avoid generic dashboard/template look. This is a Bitcoin legal defense campaign tool.

---

## Phase 0 — Foundation (design tokens, macros, i18n system)

### 0A. Design tokens in `static/style.css`

Add these CSS custom properties inside `:root` (keep existing vars, add new ones):

```css
:root {
    /* existing vars stay unchanged */

    /* New spacing tokens */
    --space-xs: 0.25rem;
    --space-sm: 0.5rem;
    --space-md: 1rem;
    --space-lg: 1.5rem;
    --space-xl: 2rem;
    --space-2xl: 3rem;

    /* New radius tokens */
    --radius-sm: 6px;
    --radius-md: 10px;
    --radius-lg: 14px;
    --radius-pill: 999px;

    /* New surface tokens (dark theme values, override in [data-theme="light"]) */
    --surface-0: var(--bg-dark);
    --surface-1: var(--bg-card);
    --surface-2: #1c2129;

    /* New border tokens */
    --border-subtle: rgba(255,255,255,0.08);
    --border-hover: rgba(255,255,255,0.16);

    /* New text opacity tokens */
    --text-tertiary: #6e7681;

    /* Role accents */
    --role-accent: var(--btc-orange);  /* default=admin */
    --role-accent-lawyer: #1f6feb;
}

[data-theme="light"] {
    /* add to existing light block */
    --surface-2: #f0f0f0;
    --border-subtle: rgba(0,0,0,0.08);
    --border-hover: rgba(0,0,0,0.16);
    --text-tertiary: #8b949e;
}
```

Also update `.bo-card` to use the new tokens:

```css
.bo-card {
    background: var(--surface-1);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-lg);
    padding: var(--space-lg);
    margin-bottom: var(--space-md);
    transition: border-color 0.2s ease;
}
.bo-card:hover {
    border-color: var(--border-hover);
}
```

### 0B. New Jinja macros in `templates/components/bo_components.html`

Add these macros BELOW the existing ones (do not delete `stat_card`, `status_badge`, `page_header`):

```jinja
{% macro text_field(name, label, value="", hint="", readonly=false, input_type="text", placeholder="") %}
<div class="bo-field">
    <label class="bo-field-label" for="field-{{ name }}">{{ label }}</label>
    {% if hint %}<small class="bo-field-hint">{{ hint }}</small>{% endif %}
    {% if input_type == "textarea" %}
    <textarea name="{{ name }}" id="field-{{ name }}" {% if readonly %}readonly class="bo-field-readonly"{% endif %} {% if placeholder %}placeholder="{{ placeholder }}"{% endif %}>{{ value }}</textarea>
    {% else %}
    <input type="{{ input_type }}" name="{{ name }}" id="field-{{ name }}" value="{{ value }}" {% if readonly %}readonly class="bo-field-readonly"{% endif %} {% if placeholder %}placeholder="{{ placeholder }}"{% endif %}>
    {% endif %}
</div>
{% endmacro %}

{% macro toggle_field(name, label, checked=false, hint="", disabled=false) %}
<div class="bo-toggle-row">
    <label class="bo-toggle">
        <input type="checkbox" name="{{ name }}" value="1" {% if checked %}checked{% endif %} {% if disabled %}disabled{% endif %}>
        <span class="bo-toggle-track"><span class="bo-toggle-thumb"></span></span>
    </label>
    <div class="bo-toggle-text">
        <span class="bo-toggle-label">{{ label }}</span>
        {% if hint %}<small class="bo-field-hint">{{ hint }}</small>{% endif %}
    </div>
</div>
{% endmacro %}

{% macro section_title(title, subtitle="") %}
<div class="bo-section-title">
    <h3>{{ title }}</h3>
    {% if subtitle %}<p>{{ subtitle }}</p>{% endif %}
</div>
{% endmacro %}

{% macro empty_state(title, description="", action_url="", action_label="") %}
<div class="bo-empty-state">
    <h3>{{ title }}</h3>
    {% if description %}<p>{{ description }}</p>{% endif %}
    {% if action_url and action_label %}
    <a href="{{ action_url }}" role="button" class="secondary">{{ action_label }}</a>
    {% endif %}
</div>
{% endmacro %}

{% macro save_bar(message="Review your changes and save when ready.") %}
<div class="bo-card bo-sticky-save" id="save-bar">
    <span class="bo-muted" id="save-bar-text">{{ message }}</span>
    <button type="submit" id="save-bar-btn">Save Settings</button>
</div>
{% endmacro %}
```

### 0C. i18n authoring system — macros

Add to `templates/components/bo_components.html`:

```jinja
{% macro i18n_bar(translatable_count=0, values_en=[], values_de=[]) %}
{% set en_filled = values_en | select("truthy") | list | length %}
{% set de_filled = values_de | select("truthy") | list | length %}
<div class="i18n-bar" id="i18n-bar">
    <button type="button" class="i18n-lang-btn active" data-lang="pt">PT (principal)</button>
    <button type="button" class="i18n-lang-btn" data-lang="en">EN <span class="i18n-coverage">{{ en_filled }}/{{ translatable_count }}</span></button>
    <button type="button" class="i18n-lang-btn" data-lang="de">DE <span class="i18n-coverage">{{ de_filled }}/{{ translatable_count }}</span></button>
</div>
{% endmacro %}

{% macro i18n_text_field(name, label, value_pt="", value_en="", value_de="", hint="", input_type="text", placeholder="", rows=6) %}
<div class="i18n-group">
    {# PT mode: normal editable field #}
    <div class="i18n-field" data-lang="pt">
        <label class="bo-field-label" for="field-{{ name }}">{{ label }}</label>
        {% if hint %}<small class="bo-field-hint">{{ hint }}</small>{% endif %}
        {% if input_type == "textarea" %}
        <textarea name="{{ name }}" id="field-{{ name }}" rows="{{ rows }}" {% if placeholder %}placeholder="{{ placeholder }}"{% endif %}>{{ value_pt }}</textarea>
        {% else %}
        <input type="text" name="{{ name }}" id="field-{{ name }}" value="{{ value_pt }}" {% if placeholder %}placeholder="{{ placeholder }}"{% endif %}>
        {% endif %}
    </div>
    {# EN mode: PT reference + editable EN #}
    <div class="i18n-field" data-lang="en">
        <label class="bo-field-label">{{ label }} (EN)</label>
        <div class="i18n-ref">PT: {{ value_pt[:120] if value_pt else '(empty)' }}</div>
        {% if input_type == "textarea" %}
        <textarea name="{{ name }}_en" rows="{{ rows }}">{{ value_en }}</textarea>
        {% else %}
        <input type="text" name="{{ name }}_en" value="{{ value_en }}">
        {% endif %}
    </div>
    {# DE mode: PT reference + editable DE #}
    <div class="i18n-field" data-lang="de">
        <label class="bo-field-label">{{ label }} (DE)</label>
        <div class="i18n-ref">PT: {{ value_pt[:120] if value_pt else '(empty)' }}</div>
        {% if input_type == "textarea" %}
        <textarea name="{{ name }}_de" rows="{{ rows }}">{{ value_de }}</textarea>
        {% else %}
        <input type="text" name="{{ name }}_de" value="{{ value_de }}">
        {% endif %}
    </div>
</div>
{% endmacro %}
```

### 0D. i18n CSS in `static/style.css`

Add to the backoffice section:

```css
/* ============================
   i18n authoring
   ============================ */
.i18n-bar {
    display: flex;
    gap: var(--space-xs);
    margin-bottom: var(--space-lg);
    padding: var(--space-sm) var(--space-md);
    background: var(--surface-1);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
}

.i18n-lang-btn {
    padding: var(--space-xs) var(--space-md);
    border-radius: var(--radius-pill);
    border: 1px solid transparent;
    background: transparent;
    color: var(--text-secondary);
    cursor: pointer;
    font-size: 0.88rem;
    font-weight: 600;
    transition: all 0.2s ease;
}

.i18n-lang-btn:hover {
    color: var(--text-primary);
    background: var(--surface-0);
}

.i18n-lang-btn.active {
    background: var(--btc-orange);
    color: white;
    border-color: var(--btc-orange);
}

.i18n-coverage {
    font-weight: 400;
    font-size: 0.78rem;
    opacity: 0.7;
}

/* Hide all i18n fields by default, show only active lang */
.i18n-field { display: none; }
.i18n-field[data-lang="pt"] { display: block; }

.i18n-mode-en .i18n-field[data-lang="pt"] { display: none; }
.i18n-mode-en .i18n-field[data-lang="en"] { display: block; }

.i18n-mode-de .i18n-field[data-lang="pt"] { display: none; }
.i18n-mode-de .i18n-field[data-lang="de"] { display: block; }

.i18n-ref {
    font-size: 0.85rem;
    color: var(--text-tertiary);
    padding: var(--space-xs) var(--space-sm);
    background: var(--surface-0);
    border-radius: var(--radius-sm);
    margin-bottom: var(--space-sm);
    border-left: 3px solid var(--border-subtle);
    white-space: pre-line;
    max-height: 4.5em;
    overflow: hidden;
}
```

### 0E. New form field CSS in `static/style.css`

```css
/* ============================
   Form fields (backoffice)
   ============================ */
.bo-field {
    margin-bottom: var(--space-lg);
}

.bo-field-label {
    display: block;
    font-weight: 600;
    font-size: 0.92rem;
    margin-bottom: var(--space-xs);
}

.bo-field-hint {
    display: block;
    color: var(--text-secondary);
    font-size: 0.82rem;
    margin-bottom: var(--space-sm);
}

.bo-field-readonly {
    opacity: 0.6;
    cursor: not-allowed;
    background: var(--surface-0) !important;
}

/* Toggle switch */
.bo-toggle-row {
    display: flex;
    align-items: flex-start;
    gap: var(--space-md);
    margin-bottom: var(--space-lg);
    padding: var(--space-md);
    background: var(--surface-1);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
}

.bo-toggle {
    position: relative;
    flex-shrink: 0;
    cursor: pointer;
    margin: 0;
}

.bo-toggle input {
    position: absolute;
    opacity: 0;
    width: 0;
    height: 0;
}

.bo-toggle-track {
    display: block;
    width: 44px;
    height: 24px;
    background: var(--text-tertiary);
    border-radius: 12px;
    transition: background 0.2s ease;
    position: relative;
}

.bo-toggle input:checked + .bo-toggle-track {
    background: var(--btc-orange);
}

.bo-toggle-thumb {
    position: absolute;
    top: 2px;
    left: 2px;
    width: 20px;
    height: 20px;
    background: white;
    border-radius: 50%;
    transition: transform 0.2s ease;
    box-shadow: 0 1px 3px rgba(0,0,0,0.3);
}

.bo-toggle input:checked + .bo-toggle-track .bo-toggle-thumb {
    transform: translateX(20px);
}

.bo-toggle-text {
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
}

.bo-toggle-label {
    font-weight: 600;
    font-size: 0.95rem;
}

/* Section titles inside forms */
.bo-section-title {
    margin-top: var(--space-xl);
    margin-bottom: var(--space-md);
    padding-bottom: var(--space-sm);
    border-bottom: 1px solid var(--border-subtle);
}

.bo-section-title h3 {
    margin: 0;
    font-size: 1.1rem;
}

.bo-section-title p {
    margin: var(--space-xs) 0 0;
    color: var(--text-secondary);
    font-size: 0.88rem;
}
```

### 0F. i18n JavaScript

Add to the end of `static/app.js` (inside the IIFE, before the closing `})();`):

```javascript
function initI18nBar() {
    var bar = document.getElementById("i18n-bar");
    if (!bar) return;

    var form = bar.closest("form") || bar.parentElement;
    var buttons = bar.querySelectorAll(".i18n-lang-btn");

    buttons.forEach(function(btn) {
        btn.addEventListener("click", function() {
            var lang = btn.dataset.lang;

            // Update button states
            buttons.forEach(function(b) { b.classList.remove("active"); });
            btn.classList.add("active");

            // Switch form mode
            form.classList.remove("i18n-mode-en", "i18n-mode-de");
            if (lang !== "pt") {
                form.classList.add("i18n-mode-" + lang);
            }
        });
    });
}

function initSaveBarDirtyState() {
    var form = document.querySelector(".bo-settings-form");
    if (!form) return;

    var saveText = document.getElementById("save-bar-text");
    var saveBtn = document.getElementById("save-bar-btn");
    if (!saveText || !saveBtn) return;

    var initial = new FormData(form);
    var initialMap = {};
    initial.forEach(function(value, key) { initialMap[key] = value; });

    function checkDirty() {
        var current = new FormData(form);
        var dirty = false;
        current.forEach(function(value, key) {
            if (key === "csrf_token") return;
            if (initialMap[key] !== value) dirty = true;
        });
        // Check removed keys (unchecked checkboxes)
        Object.keys(initialMap).forEach(function(key) {
            if (key === "csrf_token") return;
            if (!current.has(key)) dirty = true;
        });

        if (dirty) {
            saveText.textContent = "You have unsaved changes.";
            saveText.style.color = "var(--btc-orange)";
            saveBtn.disabled = false;
        } else {
            saveText.textContent = "No changes.";
            saveText.style.color = "";
            saveBtn.disabled = true;
        }
    }

    form.addEventListener("input", checkDirty);
    form.addEventListener("change", checkDirty);
    // Initial state
    checkDirty();
}
```

And add calls to both functions at the bottom alongside existing init calls:

```javascript
initI18nBar();
initSaveBarDirtyState();
```

### 0G. Translation coverage badge macro

Add to `templates/components/bo_components.html`:

```jinja
{% macro i18n_badge(title_en, body_en, title_de, body_de) %}
<span class="bo-i18n-badges">
    <span class="bo-badge {% if title_en and body_en %}bo-badge-approved{% else %}bo-badge-draft{% endif %}">EN {% if title_en and body_en %}&#10003;{% else %}&#10007;{% endif %}</span>
    <span class="bo-badge {% if title_de and body_de %}bo-badge-approved{% else %}bo-badge-draft{% endif %}">DE {% if title_de and body_de %}&#10003;{% else %}&#10007;{% endif %}</span>
</span>
{% endmacro %}
```

---

## Phase 1 — Settings page redesign

### File: `templates/admin/settings.html`

Replace the entire content. The new structure uses **JS tabs** (no page reload), the **i18n bar**, and the new macros.

Tab structure:
1. **General** — site_title, site_description, site_tagline, hero_image_url, og_image_url, deadline_text
2. **Bitcoin & Payments** — btc_address, lightning_address, wallet_explorer_url, Coinos toggle+fields, Liquid toggle+fields
3. **Campaign** — goal_btc, goal_description, raised amounts (readonly), manual_adjustment, supporters_count
4. **Advanced** — transparency_text

Key rules:
- The i18n bar goes INSIDE the `<form>`, above the tabs.
- Translatable fields use `i18n_text_field()`. Non-translatable fields use `text_field()`.
- Coinos sub-fields are inside a `<div class="bo-toggle-sub" data-depends="coinos_enabled">` that JS shows/hides based on toggle state.
- Same for Liquid sub-fields with `data-depends="liquid_enabled"`.
- Readonly fields (raised_onchain_btc, raised_lightning_btc when Coinos on, btc_address when Coinos onchain) use `text_field()` with `readonly=true`.
- The sticky save bar uses the `save_bar()` macro.
- Each tab is a `<div class="bo-tab-panel" data-tab="general">` etc., shown/hidden via JS.

Add this tab JS to `static/app.js`:

```javascript
function initSettingsTabs() {
    var tabButtons = document.querySelectorAll(".bo-tab[data-tab-target]");
    var tabPanels = document.querySelectorAll(".bo-tab-panel");
    if (!tabButtons.length) return;

    tabButtons.forEach(function(btn) {
        btn.addEventListener("click", function(e) {
            e.preventDefault();
            var target = btn.dataset.tabTarget;

            tabButtons.forEach(function(b) { b.classList.remove("bo-tab-active"); });
            btn.classList.add("bo-tab-active");

            tabPanels.forEach(function(p) {
                p.style.display = p.dataset.tab === target ? "block" : "none";
            });
        });
    });
}

function initToggleDependents() {
    document.querySelectorAll(".bo-toggle-row input[type='checkbox']").forEach(function(toggle) {
        var name = toggle.name;
        var deps = document.querySelectorAll('[data-depends="' + name + '"]');
        if (!deps.length) return;

        function update() {
            deps.forEach(function(dep) {
                dep.style.display = toggle.checked ? "block" : "none";
            });
        }

        toggle.addEventListener("change", update);
        update();
    });
}
```

Add calls: `initSettingsTabs();` and `initToggleDependents();`

### Translatable fields in settings and their tabs

| Field | Tab | Translatable? |
|---|---|---|
| site_title | General | YES |
| site_description | General | YES |
| site_tagline | General | YES |
| hero_image_url | General | no |
| og_image_url | General | no |
| deadline_text | General | YES |
| btc_address | Bitcoin & Payments | no |
| lightning_address | Bitcoin & Payments | no |
| wallet_explorer_url | Bitcoin & Payments | no |
| coinos_enabled | Bitcoin & Payments | no |
| coinos_onchain | Bitcoin & Payments | no |
| coinos_api_key | Bitcoin & Payments | no |
| coinos_webhook_secret | Bitcoin & Payments | no |
| liquid_enabled | Bitcoin & Payments | no |
| liquid_address | Bitcoin & Payments | no |
| goal_btc | Campaign | no |
| goal_description | Campaign | YES |
| raised_lightning_btc | Campaign | no (readonly) |
| raised_btc_manual_adjustment | Campaign | no |
| supporters_count | Campaign | no |
| transparency_text | Advanced | YES |

The `i18n_bar()` macro needs `translatable_count=6` for settings (6 translatable fields).

Pass `values_en` and `values_de` as lists of the corresponding `_en` / `_de` values so the coverage counter works.

---

## Phase 1.5 — Article form i18n

### File: `templates/components/article_form_fields.html`

Replace the `<details>` blocks with the i18n system:

1. Add `i18n_bar(translatable_count=2, ...)` at the top of the macro, after the CSRF token.
2. Replace the `title` input + `title_en`/`title_de` details with `i18n_text_field("title", "Title", ...)`.
3. Replace `body_md` textarea + `body_md_en`/`body_md_de` details with `i18n_text_field("body_md", "Body (Markdown)", ..., input_type="textarea", rows=20)`.
4. Publish mode, pinned checkbox — wrap in a `<div class="i18n-field" data-lang="pt">` AND also in `data-lang="en"` and `data-lang="de"` so they are always visible. OR better: put them OUTSIDE any i18n-field div so they're always shown. They are not translatable.

### Article listing badge

In `templates/admin/articles.html` and `templates/advogado/dashboard.html`, add the `i18n_badge()` macro call next to each article's status badge to show EN/DE translation coverage.

Import: `{% from "components/bo_components.html" import i18n_badge %}`

---

## Phase 2 — Shell (topbar + sidebar)

### `templates/base_admin.html` and `templates/base_lawyer.html`

Topbar changes:
- Reduce height to 56px (change `min-height: 4rem` to `3.5rem` in CSS).
- Add role badge next to title: `<span class="bo-role-badge bo-role-admin">Admin</span>` (or `bo-role-lawyer` in lawyer base).
- Theme toggle becomes an icon button (use text `☀` / `🌙` or just keep the text toggle but make it smaller).

Sidebar changes:
- Change active state from `background: var(--btc-orange)` to `border-left: 3px solid var(--role-accent); background: color-mix(in srgb, var(--role-accent) 10%, transparent);`.
- In `base_lawyer.html`, add `<style>:root { --role-accent: var(--role-accent-lawyer); }</style>` in `<head>` to override accent color.
- Reduce sidebar width from 240px to 220px.

CSS additions:

```css
.bo-role-badge {
    display: inline-flex;
    align-items: center;
    padding: 0.15rem 0.5rem;
    border-radius: var(--radius-pill);
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

.bo-role-admin {
    background: color-mix(in srgb, var(--btc-orange) 20%, transparent);
    color: var(--btc-orange);
}

.bo-role-lawyer {
    background: color-mix(in srgb, var(--role-accent-lawyer) 20%, transparent);
    color: var(--role-accent-lawyer);
}
```

---

## Phase 3 — Admin dashboard

### File: `templates/admin/dashboard.html`

Replace the current layout with:

1. **Campaign Progress card** (hero card, full width):
   - Shows `raised_btc / goal_btc` with a progress bar (reuse/adapt `progress_bar.html` component).
   - Balance breakdown (on-chain, lightning, manual adjustment) as sub-rows.
   - Supporters count and last balance check.
   - "Refresh Balance" button inside the card.

2. **Two-column grid** below the hero card:
   - Left: **Review Queue** card — count of pending + list of up to 5 pending article titles with links. CTA "Review all".
   - Right: **Content** card — counts (articles by status, media links, active lawyers).

3. **System Status** card (full width, compact):
   - One row showing Coinos status (enabled/disabled), Liquid status, Mempool last check.
   - Use colored dots: green = active, gray = disabled.

Remove the generic stat cards (`bo-stats` grid). The information now lives in context.

The backend (`routes_admin.py` or `service_admin.py`) may already pass `pending_count`, `alerts`, `articles`, `media_links`, `active_lawyers_count`. If `pending_articles` (the actual list, not just count) is not passed, you'll need to check and potentially add it. Check `routes_admin.py` for the dashboard route to see available template variables.

CSS for two-column grid:

```css
.bo-dashboard-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--space-md);
    margin-bottom: var(--space-lg);
}

@media (max-width: 768px) {
    .bo-dashboard-grid { grid-template-columns: 1fr; }
}
```

---

## Phase 4 — Lawyer dashboard

### File: `templates/advogado/dashboard.html`

1. Remove stat cards from the top.
2. **"Fila de Revisao"** as a hero section:
   - Count as heading: "3 artigos aguardando sua revisao".
   - Article cards with more prominent approve button (primary style) and Edit as secondary.
   - Add `i18n_badge()` to each article card.
3. **History section** below with sub-tabs:
   - "Approved by me" / "Published" as `bo-tab` buttons.
   - Filter via JS, same tab pattern as settings.
4. Improve empty states with contextual CTAs.

---

## Phase 5 — Polish

- Add `transition: all 0.2s ease` to `.bo-sidebar-nav a`, `.bo-card`, interactive elements.
- Ensure all new components work in `[data-theme="light"]`.
- Test all forms submit correctly (no missing hidden fields after tab/i18n changes).
- Test responsive: sidebar collapse, tab overflow, form layout on mobile.
- Verify that the i18n bar correctly submits ALL language fields regardless of which language is currently visible (fields are hidden via CSS `display:none` but still in the DOM and submitted by the form).

---

## Files you will modify

| File | Phases |
|---|---|
| `static/style.css` | 0, 2, 3, 4, 5 |
| `static/app.js` | 0, 1, 5 |
| `templates/components/bo_components.html` | 0 |
| `templates/components/article_form_fields.html` | 1.5 |
| `templates/admin/settings.html` | 1 |
| `templates/admin/dashboard.html` | 3 |
| `templates/admin/articles.html` | 1.5 |
| `templates/advogado/dashboard.html` | 4 |
| `templates/base_admin.html` | 2 |
| `templates/base_lawyer.html` | 2 |

## Files you MUST NOT modify

- `*.py` (no backend changes unless strictly needed for missing template variables)
- `translations/*.json`
- `CLAUDE.md`, `ARCHITECTURE.md`
- Any public-facing templates in `templates/` that are NOT in the list above

## Critical constraints

1. All `name=""` attributes on form inputs MUST stay exactly the same — the backend reads them by name.
2. The CSRF token hidden input must be present in every form.
3. `<details>` blocks for translations are REMOVED and replaced by the i18n system — do not keep both.
4. Pico CSS remains as the base — don't fight it, layer on top of it.
5. Every template change must be valid Jinja2.
6. Commit after each phase with conventional commit format: `feat(admin): phase N — description`.
