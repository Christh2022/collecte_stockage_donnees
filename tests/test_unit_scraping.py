"""
Tests unitaires — Scraping (enrich_offer) et Storage (build_s3_key).
"""

import re
import time
from unittest.mock import patch

import pytest


# ═══════════════════════════════════════════════════════════
# api_producer.enrich_offer
# ═══════════════════════════════════════════════════════════

class TestEnrichOffer:
    def test_adds_metadata(self):
        from src.scraping.api_producer import enrich_offer

        raw = {"title": "Data Engineer", "company": "Acme"}
        result = enrich_offer(raw, page=2)

        assert result["source"] == "adzuna"
        assert result["page"] == 2
        assert result["data"] == raw
        assert "fetched_at" in result

    def test_fetched_at_is_iso(self):
        from src.scraping.api_producer import enrich_offer

        result = enrich_offer({}, page=1)
        # Format: YYYY-MM-DDTHH:MM:SSZ
        assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", result["fetched_at"])

    def test_preserves_original_offer(self):
        from src.scraping.api_producer import enrich_offer

        raw = {"id": 42, "salary": "50k"}
        result = enrich_offer(raw, page=3)
        assert result["data"]["id"] == 42
        assert result["data"]["salary"] == "50k"


# ═══════════════════════════════════════════════════════════
# kafka_to_s3_consumer.build_s3_key
# ═══════════════════════════════════════════════════════════

class TestBuildS3Key:
    def test_format_and_partitioning(self):
        from src.storage.kafka_to_s3_consumer import build_s3_key

        key = build_s3_key(batch_id=7)
        # Should match: raw/adzuna/YYYY/MM/DD/<timestamp>_batch_0007.jsonl
        assert key.startswith("raw/adzuna/")
        assert key.endswith("_batch_0007.jsonl")

    def test_date_partition_present(self):
        from src.storage.kafka_to_s3_consumer import build_s3_key

        key = build_s3_key(batch_id=1)
        parts = key.split("/")
        # raw / adzuna / YYYY / MM / DD / filename
        assert len(parts) >= 6
        assert parts[2].isdigit() and len(parts[2]) == 4  # year
        assert parts[3].isdigit() and len(parts[3]) == 2  # month
        assert parts[4].isdigit() and len(parts[4]) == 2  # day

    def test_batch_id_padded(self):
        from src.storage.kafka_to_s3_consumer import build_s3_key

        key = build_s3_key(batch_id=42)
        assert "_batch_0042.jsonl" in key


# ═══════════════════════════════════════════════════════════
# visualization.config — constantes cohérentes
# ═══════════════════════════════════════════════════════════

class TestConfig:
    def test_palette_has_required_keys(self):
        from src.visualization.config import PALETTE

        required = ["primary", "secondary", "success", "warning", "danger",
                    "dark", "muted", "light_bg", "white"]
        for key in required:
            assert key in PALETTE, f"PALETTE missing '{key}'"

    def test_palette_values_are_hex(self):
        from src.visualization.config import PALETTE

        for key, val in PALETTE.items():
            assert re.match(r"^#[0-9A-Fa-f]{6}$", val), f"PALETTE['{key}'] = '{val}' is not valid hex"

    def test_plot_colors_not_empty(self):
        from src.visualization.config import PLOT_COLORS

        assert len(PLOT_COLORS) >= 4

    def test_city_coords_have_lat_lon(self):
        from src.visualization.config import CITY_COORDS

        for city, (lat, lon) in CITY_COORDS.items():
            assert -90 <= lat <= 90, f"{city} lat out of range"
            assert -180 <= lon <= 180, f"{city} lon out of range"

    def test_remote_patterns_are_compiled(self):
        from src.visualization.config import REMOTE_PATTERNS

        for label, pat in REMOTE_PATTERNS.items():
            assert hasattr(pat, "search"), f"REMOTE_PATTERNS['{label}'] is not compiled"

    def test_hard_skills_non_empty(self):
        from src.visualization.config import HARD_SKILLS

        assert len(HARD_SKILLS) >= 10
