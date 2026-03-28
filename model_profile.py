"""Data access for the profile_links table."""

from db import get_db

VALID_CATEGORIES = (
    "podcast",
    "github",
    "project",
    "crowdfunding",
    "tutorial",
    "talk",
    "community",
    "press",
    "other",
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
    """Return featured links for the homepage teaser."""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM profile_links WHERE featured = 1 ORDER BY sort_order, id LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_profile_links_grouped():
    """Return links grouped by category as {category: [links]}."""
    grouped = {}
    for link in get_profile_links():
        grouped.setdefault(link["category"], []).append(link)
    return grouped


def get_profile_link_by_id(link_id):
    """Return one profile link dict or None."""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM profile_links WHERE id = ?",
        (link_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def add_profile_link(
    title,
    url,
    category="other",
    description="",
    sort_order=0,
    featured=False,
    title_en="",
    title_de="",
    description_en="",
    description_de="",
):
    """Insert a new profile link."""
    conn = get_db()
    conn.execute(
        "INSERT INTO profile_links "
        "(title, url, category, description, sort_order, featured, "
        " title_en, title_de, description_en, description_de) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            title,
            url,
            category,
            description,
            sort_order,
            1 if featured else 0,
            title_en,
            title_de,
            description_en,
            description_de,
        ),
    )
    conn.commit()
    conn.close()


def update_profile_link(link_id, **kwargs):
    """Update allowed fields for an existing profile link."""
    allowed = {
        "title",
        "url",
        "category",
        "description",
        "sort_order",
        "featured",
        "title_en",
        "title_de",
        "description_en",
        "description_de",
    }
    fields = {key: value for key, value in kwargs.items() if key in allowed}
    if not fields:
        return

    if "featured" in fields:
        fields["featured"] = 1 if fields["featured"] else 0

    set_clause = ", ".join(f"{key} = ?" for key in fields)
    values = list(fields.values()) + [link_id]

    conn = get_db()
    conn.execute(
        f"UPDATE profile_links SET {set_clause} WHERE id = ?",
        values,
    )
    conn.commit()
    conn.close()


def delete_profile_link(link_id):
    """Delete a profile link by id."""
    conn = get_db()
    conn.execute("DELETE FROM profile_links WHERE id = ?", (link_id,))
    conn.commit()
    conn.close()
