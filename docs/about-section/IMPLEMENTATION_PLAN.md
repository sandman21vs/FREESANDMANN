# About Section Implementation Plan

This document describes a future implementation path for an "About the campaign owner"
section in Bastion.

## Main product decision

Do not hardcode a section like `Who is Sandmann?`.

Instead, build a reusable feature:

- public label can be customized per campaign;
- admin/settings stays generic;
- the whole section can be disabled if the user does not need it.

## Recommended rollout

### Phase A — Content model and UX copy

Goal: validate the structure before touching routes/templates heavily.

Define the minimum fields:

- `profile_enabled`
- `profile_display_name`
- `profile_heading`
- `profile_summary_md`
- `profile_long_bio_md`
- `profile_commitment_md`

Why:

- simple enough for conventional Umbrel users;
- editable in one place;
- no new relationship tables yet;
- markdown keeps it expressive without requiring a page builder.

### Phase B — Proof links

Goal: make claims easy to verify.

Recommended new repeatable entity:

- `profile_links`

Suggested fields:

- `id`
- `title`
- `url`
- `category`
- `description`
- `sort_order`
- `featured`

Suggested categories:

- `podcast`
- `github`
- `project`
- `crowdfunding`
- `tutorial`
- `talk`
- `community`
- `press`

Why a table instead of a single markdown blob:

- easier for normal users to manage from the admin UI;
- easier to reorder;
- easier to render grouped sections;
- easier to validate URLs and keep consistent cards.

### Phase C — Public rendering

Goal: present trust clearly without overwhelming the homepage.

Recommended public pattern:

#### Homepage

Show only:

- heading like `Who is {{ profile_display_name }}?`
- 2-4 sentence summary
- 3 highlighted proof items max
- CTA: `Learn more`

#### Dedicated page

Add a dedicated route such as:

- `/about`

Render:

- long-form markdown bio
- grouped link cards
- talks / podcasts / projects / tutorials
- public commitment block

### Phase D — Admin UX

Goal: keep this maintainable for non-technical users.

Add a new section in settings:

- `Profile & Background`

Structure:

- enable/disable checkbox
- display name
- short summary textarea
- long biography textarea
- commitment textarea
- simple repeatable links manager

Do not make users hand-edit JSON.

## Why not implement this as only one giant markdown field

That would be faster at first, but worse long-term because:

- hard to maintain;
- hard to reorder links;
- hard to create a clean public layout;
- harder for Umbrel users who are not comfortable writing markdown link lists;
- harder to localize later.

## Why not overload the existing `media_links` table

`media_links` is currently campaign-facing and generic.

Mixing media coverage with personal profile proofs would create ambiguity:

- media about the case/campaign;
- media proving the person’s public history.

Keep those concepts separate.

## Suggested template structure later

- `templates/about.html`
- `templates/components/profile_link_group.html`
- optional homepage partial such as `templates/components/profile_teaser.html`

## Suggested service/model split later

- `model_profile.py`
- `service_profile.py`

Or, if kept small, extend `model_config.py` only for markdown fields and create a
small dedicated model for repeatable links.

## Suggested test coverage later

- public route renders when enabled
- section hidden when disabled
- links grouped by category
- admin settings save and reload correctly
- invalid URLs rejected
- markdown sanitized through the existing safe renderer
- homepage teaser does not render empty blocks

## Recommended implementation order

1. Add the content fields.
2. Add the dedicated public page.
3. Add the homepage teaser.
4. Add repeatable profile links.
5. Polish styling and translations.

This keeps risk low and makes the feature useful early.
