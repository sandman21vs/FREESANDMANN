# Phase 2 — Implementation Plan

Authored by: Claude Opus 4.6 (planning role)
Target executor: GPT-5.4 (implementation role)
Date: 2026-03-28

---

## Overview

Transform FREESANDMANN from a personal campaign site with hidden backoffice into a
generic, self-hosted legal defense fundraising engine ready for Umbrel App Store
distribution.

**Guiding constraints:**
- Keep Flask + Jinja2 SSR. No frontend framework. No build step. No node_modules.
- App must run standalone on any mini PC (Raspberry Pi 4, NUC, etc.), not depend on Umbrel.
- All changes must maintain backward compatibility with existing SQLite databases.
- Every deliverable must include pytest tests.
- Commits in English, conventional commits format.
- Code comments/docstrings in English. UI strings go through `translations/*.json`.

---

## Phase 2.1 — Discoverability + First-Run Wizard

**Goal:** A user installs via Docker, opens the browser, and can configure everything
without knowing any hidden URLs.

### Task 2.1.1 — Admin link in public footer

**What:** Add a subtle admin access link to the public site footer.

**Files to modify:**
- `templates/base.html` (line ~93, the third `footer-col`)

**Spec:**
- Add a link at the bottom of the third footer column: `<a href="{{ url_for('admin_login') }}" class="footer-admin-link">Admin</a>`
- CSS class `footer-admin-link` in `static/style.css`: small text, muted color, no decoration by default. Subtle, not hidden.
- Add a translation key `footer_admin` with values: PT="Admin", EN="Admin", DE="Admin" in all three `translations/*.json` files.
- Use `{{ t('footer_admin') }}` as link text.

**Tests:**
- `test_routes_public.py`: assert the index page HTML contains a link to `/admin/login`.

---

### Task 2.1.2 — `setup_complete` config flag

**What:** Add a config key that tracks whether the initial setup wizard has been completed.

**Files to modify:**
- `config.py`: add `"setup_complete": "0"` to `DEFAULTS` dict.

That's it. The key will be auto-inserted by `init_db.py` on next startup (existing
`INSERT OR IGNORE` loop handles it). Existing databases get `"0"` on upgrade,
which correctly triggers the wizard.

**Tests:**
- `test_config.py` or `test_init_db.py`: verify the key exists after `init_db()` and defaults to `"0"`.

---

### Task 2.1.3 — Setup wizard route + template + service

**What:** Multi-step wizard shown on first access when `setup_complete == "0"`.

**New files:**
- `templates/admin/setup_wizard.html`
- `service_setup.py`

**Files to modify:**
- `routes_admin.py`: add wizard routes
- `app_auth.py`: add wizard redirect logic
- `static/style.css`: wizard-specific styles

#### Route design

```python
# In routes_admin.py — add these BEFORE other admin routes

@app.route("/admin/setup", methods=["GET", "POST"])
def admin_setup():
    """First-run setup wizard. Accessible without login when setup_complete == '0'."""
    cfg = models.get_all_config()

    # If setup is already complete, redirect to login
    if cfg.get("setup_complete") == "1":
        return redirect(url_for("admin_login"))

    # GET: show wizard form
    # POST: process wizard, handled by service_setup.process_setup_wizard()

    if request.method == "POST":
        result = process_setup_wizard(request.form)
        if not result["ok"]:
            for error in result["errors"]:
                flash(error, "error")
            return render_template("admin/setup_wizard.html", cfg=result["cfg"])

        flash("Setup complete! You are now logged in.", "success")
        session["admin"] = True
        return redirect(url_for("admin_dashboard"))

    return render_template("admin/setup_wizard.html", cfg=cfg)
```

#### Redirect logic

In `app_auth.py`, modify `login_required` decorator:

```python
def login_required(f):
    @functools.wraps(f)
    def wrapped(*args, **kwargs):
        # First-run wizard takes priority
        if models.get_config("setup_complete") != "1" and request.endpoint != "admin_setup":
            return redirect(url_for("admin_setup"))

        if not session.get("admin"):
            return redirect(url_for("admin_login"))
        if models.must_change_password() and request.endpoint != "admin_change_password":
            flash("You must change your password before continuing.", "warning")
            return redirect(url_for("admin_change_password"))
        return f(*args, **kwargs)
    return wrapped
```

Also modify `admin_login` route to redirect to wizard if `setup_complete == "0"`:

```python
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    # Redirect to wizard if first run
    cfg = models.get_all_config()
    if cfg.get("setup_complete") != "1":
        return redirect(url_for("admin_setup"))

    # ... rest of existing login logic unchanged
```

#### service_setup.py

```python
"""First-run setup wizard logic."""

import models
from werkzeug.security import generate_password_hash


def process_setup_wizard(form_data):
    """Validate and apply the setup wizard form.

    Returns dict with keys: ok (bool), errors (list[str]), cfg (dict for re-render).
    """
    errors = []

    # Step 1: Password
    password = form_data.get("admin_password", "").strip()
    confirm = form_data.get("admin_password_confirm", "").strip()
    if len(password) < 8:
        errors.append("Password must be at least 8 characters.")
    elif password != confirm:
        errors.append("Passwords do not match.")
    elif password == "FREE":
        errors.append("You cannot use the default password.")

    # Step 2: Campaign info
    site_title = form_data.get("site_title", "").strip()
    site_description = form_data.get("site_description", "").strip()
    if not site_title:
        errors.append("Site title is required.")

    # Step 3: Bitcoin
    btc_address = form_data.get("btc_address", "").strip()
    goal_btc = form_data.get("goal_btc", "").strip()
    if goal_btc:
        try:
            val = float(goal_btc)
            if val <= 0:
                errors.append("Goal must be a positive number.")
        except ValueError:
            errors.append("Goal must be a valid number.")

    if errors:
        return {
            "ok": False,
            "errors": errors,
            "cfg": {
                "site_title": site_title,
                "site_description": site_description,
                "btc_address": btc_address,
                "goal_btc": goal_btc or "1.0",
            },
        }

    # Apply changes
    models.change_password(password)
    models.set_config("site_title", site_title)
    if site_description:
        models.set_config("site_description", site_description)
    if btc_address:
        models.set_config("btc_address", btc_address)
    if goal_btc:
        models.set_config("goal_btc", goal_btc)

    # Mark setup as complete and disable force password change
    models.set_config("setup_complete", "1")
    models.set_config("admin_force_password_change", "0")

    return {"ok": True, "errors": []}
```

#### Template: `templates/admin/setup_wizard.html`

Single-page form (not multi-step JS — keep it simple). Uses public base layout
(`base.html`), NOT `base_admin.html` (user isn't logged in yet).

Structure:
```
{% extends "base.html" %}
{% block title %}Setup{% endblock %}
{% block content %}
<article>
  <h1>Welcome — Initial Setup</h1>
  <p>Configure the essential settings to get started.</p>

  <form method="POST" action="{{ url_for('admin_setup') }}">
    <input type="hidden" name="csrf_token" value="{{ session.csrf_token }}">

    <fieldset>
      <legend>1. Admin Password</legend>
      <p>The default password is "FREE". Choose a secure password.</p>
      <label>New Password
        <input type="password" name="admin_password" required minlength="8">
      </label>
      <label>Confirm Password
        <input type="password" name="admin_password_confirm" required>
      </label>
    </fieldset>

    <fieldset>
      <legend>2. Your Campaign</legend>
      <label>Campaign Title *
        <input type="text" name="site_title" value="{{ cfg.get('site_title', '') }}" required>
      </label>
      <label>Description
        <textarea name="site_description">{{ cfg.get('site_description', '') }}</textarea>
      </label>
    </fieldset>

    <fieldset>
      <legend>3. Receive Donations</legend>
      <label>Bitcoin On-Chain Address
        <input type="text" name="btc_address" value="{{ cfg.get('btc_address', '') }}"
               placeholder="bc1q...">
      </label>
      <label>Fundraising Goal (BTC)
        <input type="text" name="goal_btc" value="{{ cfg.get('goal_btc', '1.0') }}">
      </label>
      <small>Lightning and Liquid can be configured later in Settings.</small>
    </fieldset>

    <button type="submit">Complete Setup</button>
  </form>
</article>
{% endblock %}
```

**Styles** in `static/style.css`:
- The wizard should look clean within the existing Pico CSS framework.
- Add minimal wizard-specific styles if needed (e.g., `fieldset` spacing).
- No new CSS framework.

**Tests** (add to `test_routes_admin.py` or new `test_setup_wizard.py`):

1. `test_wizard_shown_on_first_access`: GET `/admin/` when `setup_complete == "0"` → redirects to `/admin/setup`.
2. `test_wizard_shown_on_login_access`: GET `/admin/login` when `setup_complete == "0"` → redirects to `/admin/setup`.
3. `test_wizard_renders`: GET `/admin/setup` when `setup_complete == "0"` → 200, contains "Setup".
4. `test_wizard_redirects_when_complete`: GET `/admin/setup` when `setup_complete == "1"` → redirects to `/admin/login`.
5. `test_wizard_submit_success`: POST valid data to `/admin/setup` → sets `setup_complete` to `"1"`, changes password, sets session, redirects to dashboard.
6. `test_wizard_submit_validation`: POST with short password → re-renders form with error.
7. `test_wizard_submit_password_mismatch`: POST with mismatched passwords → error.
8. `test_wizard_submit_missing_title`: POST without site_title → error.
9. `test_wizard_does_not_require_btc`: POST without btc_address → still succeeds (optional field).
10. `test_normal_login_works_after_setup`: After setup_complete == "1", `/admin/login` works normally.

---

### Task 2.1.4 — Lawyer login link on admin login page

**What:** Add a secondary link on `/admin/login` pointing to `/advogado/login`.

**Files to modify:**
- `templates/admin/login.html`: add below the login form: `<small><a href="{{ url_for('lawyer_login') }}">Lawyer portal →</a></small>`

**Tests:**
- Assert `/admin/login` page contains a link to `/advogado/login`.

---

## Phase 2.2 — Admin UX Polish

**Goal:** Make the admin panel feel organized and guide the user on what needs attention.

### Task 2.2.1 — Dashboard checklist section

**What:** Add a "Getting Started" checklist to the dashboard that shows what's
configured and what still needs attention.

**Files to modify:**
- `service_admin.py`: expand `get_admin_dashboard_context()` to include a checklist.
- `templates/admin/dashboard.html`: render the checklist.
- `static/style.css`: checklist styles.

**Checklist items** (each is a dict with `label`, `done` bool, `link` URL):

```python
def _build_setup_checklist(cfg, articles, lawyers):
    return [
        {
            "label": "Password changed",
            "done": cfg.get("admin_force_password_change") != "1",
            "link": url_for("admin_change_password"),
        },
        {
            "label": "Campaign title set",
            "done": cfg.get("site_title", "") not in ("", "Free Sandmann"),
            "link": url_for("admin_settings") + "#section-general",
        },
        {
            "label": "Bitcoin address configured",
            "done": bool(cfg.get("btc_address", "").strip()),
            "link": url_for("admin_settings") + "#section-bitcoin",
        },
        {
            "label": "Fundraising goal defined",
            "done": cfg.get("goal_btc", "0") not in ("0", "0.0", "1.0"),
            "link": url_for("admin_settings") + "#section-fundraising",
        },
        {
            "label": "First article published",
            "done": any(a["published"] for a in articles),
            "link": url_for("admin_article_new"),
        },
        {
            "label": "Lawyer account created",
            "done": len(lawyers) > 0,
            "link": url_for("admin_lawyers"),
        },
    ]
```

**Note:** Import `url_for` from Flask in `service_admin.py` (it's not currently imported there).
Actually — `url_for` requires app context. Better approach: build the checklist in the
route handler or pass just the data from the service and build links in the template.

Recommended: return raw data from service, build links in template with Jinja `url_for()`.

```python
# service_admin.py — add to get_admin_dashboard_context() return dict
checklist = [
    {"label": "Password changed", "done": cfg.get("admin_force_password_change") != "1", "target": "change_password"},
    {"label": "Campaign title set", "done": cfg.get("site_title", "") not in ("", "Free Sandmann"), "target": "settings_general"},
    {"label": "Bitcoin address configured", "done": bool(cfg.get("btc_address", "").strip()), "target": "settings_bitcoin"},
    {"label": "Fundraising goal defined", "done": cfg.get("goal_btc", "0") not in ("0", "0.0", "1.0"), "target": "settings_fundraising"},
    {"label": "First article published", "done": any(a["published"] for a in articles), "target": "new_article"},
    {"label": "Lawyer account created", "done": len(lawyers) > 0, "target": "lawyers"},
]
```

Template renders each item with a checkmark (done) or link to fix (not done).
Hide the entire checklist section once all items are done (or show a "All set!" message).

**Tests:**
- `test_dashboard_checklist_unconfigured`: Fresh DB → all items show as not done.
- `test_dashboard_checklist_configured`: Set title, btc_address, goal, publish article → items show as done.

---

### Task 2.2.2 — Settings section navigation improvement

**What:** The current settings page already has a `bo-section-nav` with anchor links
(line 12-19 of `templates/admin/settings.html`). This works but could be improved with:

1. **Sticky section nav** that stays visible while scrolling.
2. **Active state** on the current section link using a small JS snippet.
3. **Scroll-margin** on fieldsets so the header doesn't overlap when jumping.

**Files to modify:**
- `static/style.css`: add `scroll-margin-top` to `fieldset[id]`, sticky behavior for `.bo-section-nav`.
- `static/app.js`: add an IntersectionObserver snippet (~15 lines) that highlights the active nav link.

**This is CSS/JS polish only, no backend changes.**

**Tests:**
- No backend tests needed. Visual verification.

---

### Task 2.2.3 — Flash messages upgrade (optional, low priority)

**What:** Replace top-of-page flash messages with auto-dismissing toasts.

**Files to modify:**
- `static/style.css`: toast positioning (fixed bottom-right or top-right).
- `static/app.js`: auto-dismiss after 5 seconds with fade-out.
- `templates/base_admin.html` and `templates/base_lawyer.html`: wrap flash messages in a toast container.

**Spec:**
- Flash messages already work. This is purely a UX polish.
- Keep the same `flash-msg flash-{{ category }}` classes.
- Add `position: fixed`, `z-index`, `animation` for slide-in/fade-out.
- Auto-dismiss after 5s, with a close button.
- No dependency.

**Tests:**
- No backend tests. Visual verification.

---

## Phase 2.3 — Umbrel Packaging

**Goal:** App installable from the Umbrel App Store.

### Task 2.3.1 — Multi-arch Docker image

**What:** Build Docker image for both `linux/amd64` and `linux/arm64`.

**Files to modify:**
- `Dockerfile`: verify the base image `python:3.12-slim` supports both architectures (it does).
- No code changes needed — the app is pure Python.

**Build command** (for CI or manual):
```bash
docker buildx create --use
docker buildx build --platform linux/amd64,linux/arm64 -t ghcr.io/sandman21vs/freesandmann:latest --push .
```

**Add to project:**
- `.github/workflows/docker-publish.yml`: GitHub Actions workflow that builds + pushes multi-arch on tag push.

**Tests:**
- Build locally for `linux/arm64` using `docker buildx build --platform linux/arm64 -t test-arm .`
- Verify it starts: `docker run --rm -p 4040:8000 test-arm`

---

### Task 2.3.2 — Healthcheck

**Files to modify:**
- `routes_public.py`: add `GET /health` → returns `{"status": "ok"}` (200).
- `Dockerfile`: add `HEALTHCHECK --interval=30s --timeout=5s CMD curl -f http://localhost:8000/health || exit 1`

**Spec:**
- The `/health` endpoint should be minimal: no DB check (SQLite is local file, always available).
- Return plain JSON `{"status": "ok"}`.
- No auth required.

**Tests:**
- `test_routes_public.py`: GET `/health` → 200, JSON body `{"status": "ok"}`.

---

### Task 2.3.3 — Umbrel app manifest

**What:** Create the Umbrel app packaging files.

**New files in project root:**
- `umbrel-app.yml`

**Spec for `umbrel-app.yml`:**
```yaml
manifestVersion: 1
id: freesandmann
name: Free Sandmann  # Will be renamed in Phase 2.4
tagline: Self-hosted Bitcoin fundraising for legal defense
icon: https://raw.githubusercontent.com/sandman21vs/FREESANDMANN/main/static/icon.png
category: finance
version: "1.0.0"
port: 4040
description: >-
  A self-hostable Bitcoin fundraising platform for legal defense campaigns.
  Accept on-chain and Lightning donations. Manage your campaign with a
  built-in admin panel. No KYC, no third parties holding your funds.
developer: sandman21vs
website: https://github.com/sandman21vs/FREESANDMANN
repo: https://github.com/sandman21vs/FREESANDMANN
support: https://github.com/sandman21vs/FREESANDMANN/issues
gallery:
  - https://raw.githubusercontent.com/sandman21vs/FREESANDMANN/main/screenshots/homepage.png
  - https://raw.githubusercontent.com/sandman21vs/FREESANDMANN/main/screenshots/admin.png
  - https://raw.githubusercontent.com/sandman21vs/FREESANDMANN/main/screenshots/donate.png
dependencies: []
path: ""
defaultUsername: ""
defaultPassword: ""
submitter: sandman21vs
submission: https://github.com/getumbrel/umbrel-apps/pull/XXX
```

**Also needed:**
- `static/icon.png`: 256x256 or 512x512 app icon (design needed separately).
- `screenshots/` directory with 3 screenshots (take after UI polish is done).

**Note:** The Umbrel app framework (`getumbrel/umbrel-apps`) expects the app to be
added as a directory in their monorepo via PR. The `docker-compose.yml` already
works. Main adaptation needed:
- Ensure `docker-compose.yml` uses a published image tag (not `build: .`).
- Add `APP_HOST`, `APP_PORT` env vars if Umbrel proxy requires them.

Refer to: https://github.com/getumbrel/umbrel-apps#readme for latest spec.

---

## Phase 2.4 — Rebranding

**Goal:** Rename from FREESANDMANN to a product name suitable for any user.

### Name recommendation

**Primary: Bastion**

Rationale: short, memorable, means "fortress/stronghold" — directly evokes defense.
Works in English, French, German, Portuguese ("bastião"). No major open-source
project collision. Works as `bastion-app`, `getbastion`, `bastiondefense`.

**Fallback: Advocato**

Rationale: near-universal cognate for "advocate/lawyer" across Romance languages.
More specific to legal use case. Slightly longer.

### Task 2.4.1 — Internal rename

**Files to modify (search-and-replace):**
- `config.py`: change default `site_title` from `"Free Sandmann"` to new name.
- `templates/base.html`: all fallback strings `'Free Sandmann'` → new name.
- `templates/base_admin.html`: same.
- `templates/base_lawyer.html`: same.
- `templates/admin/settings.html`: same.
- `templates/admin/dashboard.html`: same.
- `README.md`: full rewrite of title, description, clone URL.
- `CLAUDE.md`: update project name and description.
- `ARCHITECTURE.md`: update title.
- `docker-compose.yml`: rename service and volume.
- `Dockerfile`: no changes needed (app code path stays `/app`).
- `umbrel-app.yml`: update id, name, URLs.

**Approach:** Do a global search for "Free Sandmann", "FREESANDMANN", "freesandmann"
and replace with the new name in appropriate casing.

**The GitHub repo itself** can be renamed via GitHub settings (Vinicius does this manually).

**Tests:**
- Existing tests should still pass (they don't hardcode the project name in assertions,
  they use `cfg.get('site_title')` which comes from DB).
- Verify with `pytest tests/ -v` after rename.

---

## Execution order summary

```
Phase 2.1 (Discoverability + Wizard)
  ├── 2.1.1  Admin footer link           [~15 min]
  ├── 2.1.2  setup_complete config key    [~5 min]
  ├── 2.1.3  Setup wizard (route+template+service+tests)  [~2 hours]
  └── 2.1.4  Lawyer link on admin login   [~10 min]

Phase 2.2 (Admin UX)
  ├── 2.2.1  Dashboard checklist          [~1 hour]
  ├── 2.2.2  Settings nav polish (CSS/JS) [~30 min]
  └── 2.2.3  Toast flash messages         [~30 min, optional]

Phase 2.3 (Umbrel Packaging)
  ├── 2.3.1  Multi-arch Docker            [~1 hour]
  ├── 2.3.2  Health endpoint              [~15 min]
  └── 2.3.3  Umbrel manifest             [~30 min]

Phase 2.4 (Rebranding)
  └── 2.4.1  Global rename               [~1 hour]
```

**Dependencies:**
- 2.1.2 must be done before 2.1.3 (wizard needs the config key).
- 2.2.1 can reference the wizard (checklist item "setup complete").
- 2.3.3 should be done after 2.4 (manifest needs final name).
- Everything else is independent and can be done in any order.

---

## Implementation notes for GPT-5.4

1. **Read `ARCHITECTURE.md` first.** It has the complete file structure, DB schema, route table, and all conventions.

2. **Read `CLAUDE.md` for rules.** Commits in English, conventional commits format. Tests with pytest. PT-BR for user-facing content only if going through translations.

3. **Run `pytest tests/ -v` after every task.** All 268+ existing tests must continue to pass.

4. **The project has no `models.get_config(key)` single-key getter.** The existing pattern is `models.get_all_config()` which returns a dict. Check if a single-key getter exists; if not, add one to `model_config.py` (simple SELECT query) and re-export through `models.py`.

5. **CSRF is required on all POST forms.** Every form must include `<input type="hidden" name="csrf_token" value="{{ session.csrf_token }}">`.

6. **The wizard route does NOT use `@login_required`.** It's a special case — the user isn't logged in yet. But it still needs CSRF protection (which is handled globally by `app_hooks.py`).

7. **Test fixtures live in `tests/conftest.py`.** They create a temp SQLite DB and a Flask test client. All tests use this fixture — never touch `data/freesandmann.db`.

8. **Translation keys:** When adding new UI-facing strings, add the key to all three `translations/{pt,en,de}.json` files. Use the `t('key')` function in templates.

9. **Import pattern:** Routes import from `service_*.py`, services import from `models` (which is a facade re-exporting from `model_*.py`). Don't import `model_*.py` directly in routes.
