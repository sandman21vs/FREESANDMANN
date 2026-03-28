"""Tests for profile settings and profile_links model helpers."""

import models
from model_config import get_localized_config


class TestProfileSettingsConfig:
    def test_validate_settings_form_accepts_profile_fields(self, temp_database):
        """Profile text/url fields should validate and normalize correctly."""
        current_cfg = models.get_all_config()
        normalized, form_cfg, errors = models.validate_settings_form(
            {
                "site_title": "Bastion",
                "goal_btc": current_cfg["goal_btc"],
                "raised_lightning_btc": current_cfg["raised_lightning_btc"],
                "raised_btc_manual_adjustment": current_cfg["raised_btc_manual_adjustment"],
                "supporters_count": current_cfg["supporters_count"],
                "profile_enabled": "1",
                "profile_display_name": "Sandmann",
                "profile_heading": "Quem sou eu?",
                "profile_summary_md": "Resumo",
                "profile_long_bio_md": "Bio longa",
                "profile_commitment_md": "Compromissos",
                "profile_avatar_url": "https://example.com/avatar.png",
            },
            current_cfg,
        )

        assert errors == []
        assert normalized["profile_enabled"] == "1"
        assert normalized["profile_display_name"] == "Sandmann"
        assert normalized["profile_avatar_url"] == "https://example.com/avatar.png"
        assert form_cfg["profile_heading"] == "Quem sou eu?"

    def test_profile_avatar_url_rejects_invalid_scheme(self, temp_database):
        """Profile avatar URL should reject unsafe schemes like data:."""
        current_cfg = models.get_all_config()
        normalized, form_cfg, errors = models.validate_settings_form(
            {
                "site_title": current_cfg["site_title"],
                "goal_btc": current_cfg["goal_btc"],
                "raised_lightning_btc": current_cfg["raised_lightning_btc"],
                "raised_btc_manual_adjustment": current_cfg["raised_btc_manual_adjustment"],
                "supporters_count": current_cfg["supporters_count"],
                "profile_avatar_url": "data:image/svg+xml,<svg></svg>",
            },
            current_cfg,
        )

        assert normalized["profile_enabled"] == "0"
        assert form_cfg["profile_avatar_url"] == "data:image/svg+xml,<svg></svg>"
        assert "Profile Avatar URL must be a valid http(s) URL or site-relative path." in errors

    def test_get_localized_config_applies_profile_translations(self, temp_database):
        """Localized profile copy should override the base fields when present."""
        cfg = models.get_all_config()
        cfg["profile_heading"] = "Quem sou eu?"
        cfg["profile_heading_en"] = "Who am I?"
        cfg["profile_summary_md"] = "Resumo"
        cfg["profile_summary_md_en"] = "Summary"

        localized = get_localized_config(cfg, "en")

        assert localized["profile_heading"] == "Who am I?"
        assert localized["profile_summary_md"] == "Summary"


class TestProfileLinksModel:
    def test_profile_link_crud(self, temp_database):
        """Profile links should support add, update, read, and delete."""
        models.add_profile_link(
            title="Podcast Appearance",
            url="https://example.com/podcast",
            category="podcast",
            description="Episode 42",
            sort_order=2,
            featured=True,
            title_en="Podcast Appearance EN",
        )

        links = models.get_profile_links()
        assert len(links) == 1
        link = links[0]
        assert link["title"] == "Podcast Appearance"
        assert link["featured"] == 1

        models.update_profile_link(
            link["id"],
            title="Updated Podcast",
            sort_order=1,
            featured=False,
            description_de="Beschreibung",
        )
        updated = models.get_profile_link_by_id(link["id"])
        assert updated["title"] == "Updated Podcast"
        assert updated["sort_order"] == 1
        assert updated["featured"] == 0
        assert updated["description_de"] == "Beschreibung"

        models.delete_profile_link(link["id"])
        assert models.get_profile_link_by_id(link["id"]) is None

    def test_get_featured_profile_links_limit(self, temp_database):
        """Featured links helper should return at most the requested number."""
        for index in range(5):
            models.add_profile_link(
                title=f"Link {index}",
                url=f"https://example.com/{index}",
                category="project",
                sort_order=index,
                featured=True,
            )

        featured = models.get_featured_profile_links(3)

        assert len(featured) == 3
        assert [link["title"] for link in featured] == ["Link 0", "Link 1", "Link 2"]

    def test_get_profile_links_grouped(self, temp_database):
        """Links should be grouped by category preserving order inside groups."""
        models.add_profile_link("GitHub", "https://example.com/github", category="github", sort_order=2)
        models.add_profile_link("Podcast", "https://example.com/podcast", category="podcast", sort_order=1)
        models.add_profile_link("Project", "https://example.com/project", category="github", sort_order=3)

        grouped = models.get_profile_links_grouped()

        assert set(grouped) == {"podcast", "github"}
        assert [link["title"] for link in grouped["github"]] == ["GitHub", "Project"]
        assert grouped["podcast"][0]["title"] == "Podcast"

    def test_valid_categories_constant(self, temp_database):
        """The category constant should expose all supported public categories."""
        assert models.VALID_CATEGORIES == (
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
