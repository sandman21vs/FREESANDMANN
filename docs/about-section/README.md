# About Section Notes

This folder documents a future "About / Who is this person?" section for Bastion.

The goal is to help campaign owners show:

- who they are;
- what they have built or contributed publicly;
- why people should trust their history and track record;
- where donors can independently verify that history;
- what kind of public updates they intend to publish.

## Product direction

This should **not** become a Sandmann-specific feature.

For Bastion to stay reusable for normal self-hosted users and Umbrel users, the
feature should be modeled as a generic optional profile section, for example:

- public heading: `Who is {{ display_name }}?`
- admin/settings label: `Profile & Background`
- status: optional, disabled by default

## Why this matters

For legal-defense fundraising, many visitors will ask:

- who is this person;
- what have they done publicly before;
- are they credible;
- are they part of the Bitcoin/community ecosystem;
- is there a visible public track record beyond the campaign itself.

This section answers those questions without forcing donors to search across
GitHub, podcasts, talks, tutorials, and community archives manually.

## UX principles

- Keep the homepage concise. The homepage should introduce trust, not dump a full biography.
- Use the homepage for a short trust summary plus a CTA such as `Learn more`.
- Put the full narrative on a dedicated page or dedicated long section.
- Keep the admin UX simple enough for non-technical Umbrel users.
- Avoid complex page builders or deeply nested CMS behavior.

## Recommended information architecture

Use two layers:

1. A short homepage trust block.
2. A full profile page with grouped evidence and background.

Suggested public sections:

- short intro
- background and mission
- projects and open-source work
- podcasts, talks, and interviews
- crowdfunding and community history
- Bitcoin education and tutorials
- public commitment / values

## Recommendation for Bastion

If implemented later, prefer a **generic profile feature** with:

- a display name
- a short markdown summary
- a long markdown biography
- a repeatable list of external proof links grouped by category
- an optional featured quote or public commitment

This keeps the feature useful for Sandmann now and maintainable for other users later.
