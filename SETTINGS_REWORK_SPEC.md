# Settings "Bitcoin & Payments" Tab Rework

> **Temporary file.** Remove from repo after implementation is complete.

## Goal

Restructure the Bitcoin & Payments tab in `/admin/settings` to have a clearer hierarchy:
1. **Receiving Addresses** section up front (onchain, lightning, liquid) — simple, manual fields.
2. **A note** explaining that automatic balance tracking only works for onchain (via mempool.space) unless Coinos advanced features are configured.
3. **Advanced: Coinos API** section — API key, plus toggles to enable/disable Coinos-managed Lightning, Liquid, and Onchain.
4. **Fallback logic**: if a manual address field is empty AND Coinos is configured, the public site should display the Coinos-derived address instead.

## Current state (what exists)

### Settings template (`templates/admin/settings.html`)
- Bitcoin tab currently shows: btc_address, lightning_address, wallet_explorer_url, then Coinos toggle+sub-fields, then Liquid toggle+sub-fields.
- Liquid address is buried inside a toggle-dependent block.

### Backend (`service_admin.py`, `model_config.py`, `coinos_client.py`)
- `coinos_enabled`, `coinos_onchain`, `liquid_enabled` are checkbox flags ("0"/"1").
- `coinos_client.get_onchain_address()` generates a Coinos BTC address.
- Coinos `create_invoice()` supports types `"lightning"` and `"liquid"`.
- There is NO function in `coinos_client.py` to fetch the Coinos username/LN address.
- `liquid_address` is already a config field in `config.py` DEFAULTS.

### Public site (`templates/donate.html`)
- Shows QR codes for `btc_address`, `lightning_address`, and `liquid_address` (if `liquid_enabled == '1'`).
- Shows Coinos invoice widget if `coinos_enabled == '1'`.

### Config defaults (`config.py`)
- `liquid_address: ""`, `liquid_enabled: "0"` already exist.

---

## Implementation plan

### Part 1 — Template: restructure Bitcoin & Payments tab

**File: `templates/admin/settings.html`**

Replace the entire `data-tab="bitcoin"` panel with this structure:

```
Section: Receiving Addresses
  - btc_address (text field, label "Bitcoin On-Chain Address")
    hint: "Your on-chain BTC address for donations."
    If Coinos onchain is active: readonly + hint says "Managed by Coinos"
  - lightning_address (text field, label "Lightning Address")
    hint: "An LN address like you@coinos.io or LNURL."
  - liquid_address (text field, label "Liquid Address")
    hint: "A Liquid Network address (lq1qq... or VJL...)."
    NOT gated behind any toggle. Always visible and editable.
  - wallet_explorer_url (text field, label "Wallet Explorer URL")
    hint: "Public link for transparency (e.g. mempool.space)."

Info note (use a styled <div class="bo-info-note">):
  "Automatic balance tracking: On-chain balance is updated every 5 minutes
   via mempool.space. Lightning and Liquid balances are only tracked
   automatically when Coinos is configured below."

Section: Advanced — Coinos API
  - text_field: coinos_api_key (password field, label "Coinos API Key")
    hint: "Read-only token from coinos.io/docs. Enables invoice generation and balance tracking."
    placeholder: "Paste your read-only token"
  - text_field: coinos_webhook_secret
    hint: "Optional. Random string to verify webhook callbacks."

  Subsection (only visible when coinos_api_key is not empty — use data-depends):
    - toggle_field: coinos_enabled (label "Lightning Invoices via Coinos")
      hint: "Generate Lightning invoices through your Coinos account."
    - toggle_field: liquid_enabled (label "Liquid Invoices via Coinos")
      hint: "Generate Liquid invoices through your Coinos account."
    - toggle_field: coinos_onchain (label "On-Chain via Coinos")
      hint: "Use a Coinos-generated BTC address. Balance tracked via Coinos instead of mempool.space."

  Info note:
    "When Coinos features are enabled and manual address fields above are
     empty, the site will automatically use your Coinos account addresses."
```

### Part 2 — CSS: info note style

**File: `static/style.css`**

Add a new class for informational notes inside settings:

```css
.bo-info-note {
    padding: var(--space-md);
    background: color-mix(in srgb, var(--role-accent-lawyer) 8%, transparent);
    border-left: 3px solid var(--role-accent-lawyer);
    border-radius: var(--radius-sm);
    font-size: 0.88rem;
    color: var(--text-secondary);
    margin-bottom: var(--space-lg);
    line-height: 1.5;
}
```

### Part 3 — JS: toggle dependent on non-empty text field

**File: `static/app.js`**

The current `initToggleDependents()` only works with checkbox toggles. We need a variant that shows/hides based on whether a text input has content.

Update `initToggleDependents()` to also handle `data-depends-notempty` attributes:

```javascript
// Inside initToggleDependents, after the existing checkbox logic, add:
document.querySelectorAll('[data-depends-notempty]').forEach(function(dep) {
    var fieldName = dep.dataset.dependsNotempty;
    var field = document.querySelector('input[name="' + fieldName + '"]');
    if (!field) return;

    function update() {
        dep.style.display = field.value.trim() ? "block" : "none";
    }

    field.addEventListener("input", update);
    update();
});
```

In the template, the Coinos toggles subsection uses:
```html
<div class="bo-toggle-sub" data-depends-notempty="coinos_api_key">
```

### Part 4 — Backend: address fallback logic

**File: `service_admin.py`** — in `process_admin_settings()`:

After saving settings, if Coinos is enabled and the Coinos API key is set:
- If `lightning_address` is empty, try to derive it. The Coinos LN address format is `username@coinos.io`. We can get the username from the API.
- If `liquid_address` is empty and `liquid_enabled == "1"`, no automatic derivation needed (Coinos handles liquid invoices directly, no static address needed).
- If `btc_address` is empty and `coinos_onchain == "1"`, the existing `coinos.get_onchain_address()` logic already handles this.

**File: `coinos_client.py`** — add function to get account info:

```python
def get_account_username():
    """Fetch the Coinos account username for LN address derivation."""
    if models.get_config("coinos_enabled") != "1":
        return None
    result = _coinos_request("GET", "/me")
    if result and "username" in result:
        return result["username"]
    return None
```

**File: `app_hooks.py`** or **`routes_public.py`** — in the template context:

When building the public page context, apply fallback logic:
- If `lightning_address` is empty and Coinos is enabled, compute `{coinos_username}@coinos.io` and use that.
- The `btc_address` fallback is already handled (Coinos onchain sets it in config).
- `liquid_address` stays as-is (Coinos liquid works via invoices, not static addresses).

The cleanest place for this is a new helper in `service_admin.py` or a small function in `app_hooks.py` that enriches the config dict before passing to templates.

### Part 5 — Backend: validation changes

**File: `model_config.py`** — in `validate_settings_form()`:

Current validation:
- `liquid_enabled == "1"` requires `liquid_address` to be set → **REMOVE this rule**. Liquid can now work via Coinos invoices without a static address.
- `coinos_onchain == "1"` requires `coinos_enabled == "1"` → Keep this.
- `coinos_enabled == "1"` requires `coinos_api_key` → Keep this.

Add new validation:
- If `liquid_enabled == "1"` and `liquid_address` is empty and `coinos_enabled != "1"`: error "Liquid address is required when Coinos is not configured."

Also: `liquid_enabled` now means "show Liquid on the public site" (either via static address OR Coinos invoices). The toggle in the Coinos subsection should be a SEPARATE flag for Coinos-generated liquid invoices. BUT to avoid overcomplicating, we can reuse `liquid_enabled` as the single flag — if Coinos is on, liquid invoices go through Coinos; if Coinos is off, a static address is needed.

### Part 6 — Public site: show liquid based on address OR Coinos

**File: `templates/donate.html`**

Current line 13:
```jinja
{{ qr_section(cfg.get('btc_address', ''), cfg.get('lightning_address', ''), 'large', cfg.get('liquid_address', '') if cfg.get('liquid_enabled') == '1' else '') }}
```

Change to also show liquid when Coinos liquid is enabled even without a static address:
```jinja
{% set show_liquid_address = cfg.get('liquid_address', '') if (cfg.get('liquid_enabled') == '1' or cfg.get('liquid_address', '')) else '' %}
```

Actually, the logic is simpler: if `liquid_address` exists in the enriched config (after fallback), show it. The Coinos liquid invoices are handled by the invoice widget, not QR codes. So the QR section only shows liquid if there's a static address. Keep the current logic but remove the `liquid_enabled` gate — if there's a liquid address, show it:

```jinja
{{ qr_section(cfg.get('btc_address', ''), cfg.get('lightning_address', ''), 'large', cfg.get('liquid_address', '')) }}
```

Wait — that would always show it even when empty. Keep it gated but simplify:
```jinja
{{ qr_section(
    cfg.get('btc_address', ''),
    cfg.get('lightning_address', ''),
    'large',
    cfg.get('liquid_address', '') if cfg.get('liquid_address', '') else ''
) }}
```

This is the same as just passing `cfg.get('liquid_address', '')` since `qr_section` already handles empty strings by not rendering the QR.

Check how `qr_section` handles empty addresses:

### Part 7 — Ensure `qr_section` handles empty liquid gracefully

**File: `templates/components/qr_codes.html`** — verify that it skips rendering when address is empty. If it does, just pass `cfg.get('liquid_address', '')` unconditionally.

---

## Files to modify

| File | What changes |
|---|---|
| `templates/admin/settings.html` | Restructure Bitcoin & Payments tab |
| `static/style.css` | Add `.bo-info-note` class |
| `static/app.js` | Add `data-depends-notempty` logic in `initToggleDependents` |
| `coinos_client.py` | Add `get_account_username()` function |
| `service_admin.py` | Add LN address fallback after settings save |
| `app_hooks.py` | Enrich config with fallback addresses for public templates |
| `model_config.py` | Relax `liquid_enabled` validation (allow Coinos-only liquid) |
| `templates/donate.html` | Simplify liquid address display logic |
| `templates/components/qr_codes.html` | Verify empty-address handling (may need no change) |

## Files NOT to modify

- `config.py` — no new DEFAULTS needed, `liquid_address` and `liquid_enabled` already exist.
- Translation files — no new UI strings needed.
- Test files — update tests AFTER implementation to match new behavior.

## Key constraints

1. All existing `name=""` attributes on form inputs MUST stay the same. The backend reads them by name.
2. CSRF token must remain in the form.
3. The Coinos API endpoint `/me` must be verified to return `{"username": "..."}`. If not available, skip the LN address auto-derivation and just document it as a manual step.
4. Run `pytest tests/ -v` after all changes. Fix any broken tests.
5. Commit with: `feat(admin): restructure payment settings with address fallbacks`

## Summary of UX changes

**Before**: Bitcoin addresses scattered, Liquid hidden behind toggle, no explanation of what's automatic vs manual, confusing Coinos sub-section.

**After**:
1. Open the Bitcoin & Payments tab → see all 3 address fields immediately (onchain, LN, liquid).
2. Clear note explaining automatic tracking only works for onchain unless Coinos is set up.
3. Scroll down to "Advanced — Coinos API" → paste API key → toggles appear for LN/Liquid/Onchain via Coinos.
4. If you leave address fields empty and Coinos is configured, the public site auto-fills from Coinos.
5. LN address always shows as `username@coinos.io` (email-like format).
