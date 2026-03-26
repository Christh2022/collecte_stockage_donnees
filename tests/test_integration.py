"""
Tests d'intégration — vérifient les interactions inter-modules
sans nécessiter de services Docker externes (PostgreSQL, Kafka…).

Ces tests mockent les I/O réseau mais exercent le vrai code applicatif
bout-en-bout : ETL pipeline, callbacks Dash, structure du layout.
"""

import json
import re
from io import StringIO
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

# ═══════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════

SAMPLE_RAW = [
    {
        "title": "Data Engineer",
        "company": {"display_name": "Acme Corp"},
        "location": {"display_name": "Paris, France"},
        "description": "Poste de data engineer avec Python, Docker, AWS. CDI.",
        "salary_min": 45000,
        "salary_max": 55000,
        "created": "2026-03-01T10:00:00Z",
        "redirect_url": "https://example.com/job/1",
        "id": "abc1",
    },
    {
        "title": "Data Scientist",
        "company": {"display_name": "Beta Inc"},
        "location": {"display_name": "Lyon"},
        "description": "Recherche data scientist Python SQL TensorFlow. Stage.",
        "salary_min": 35000,
        "salary_max": 42000,
        "created": "2026-03-05T08:30:00Z",
        "redirect_url": "https://example.com/job/2",
        "id": "abc2",
    },
    {
        "title": "ML Engineer",
        "company": {"display_name": "Gamma SAS"},
        "location": {"display_name": "Paris"},
        "description": "ML engineer deep learning PyTorch. Full remote. CDI.",
        "salary_min": None,
        "salary_max": None,
        "created": "2026-03-10T14:00:00Z",
        "redirect_url": "https://example.com/job/3",
        "id": "abc3",
    },
]


@pytest.fixture()
def raw_df():
    """DataFrame brut simulant des données issues de l'API Adzuna."""
    rows = []
    for item in SAMPLE_RAW:
        rows.append({
            "title": item["title"],
            "company": item["company"]["display_name"],
            "city": item["location"]["display_name"],
            "description": item["description"],
            "salary_min": item["salary_min"],
            "salary_max": item["salary_max"],
            "published_at": item["created"],
            "url": item["redirect_url"],
            "source": "adzuna",
            "contract_type": "permanent",
        })
    return pd.DataFrame(rows)


# ═══════════════════════════════════════════════════════════
# 1. ETL Pipeline intégré : normalize → extract → deduplicate
# ═══════════════════════════════════════════════════════════

class TestETLPipeline:
    """Exerce le pipeline ETL complet sur des données brutes."""

    def test_full_pipeline(self, raw_df):
        from src.transform.etl_transform import (
            deduplicate,
            extract_tech_stack,
            normalize_city,
            normalize_contract,
            normalize_date,
            parse_salary,
        )

        # 1. normalize_date
        raw_df["published_at"] = normalize_date(raw_df["published_at"])
        assert raw_df["published_at"].notna().all()

        # 2. normalize_contract
        raw_df["contract_type"] = normalize_contract(raw_df["contract_type"])
        assert raw_df["contract_type"].iloc[0] == "CDI"

        # 3. normalize_city
        raw_df["city_clean"] = normalize_city(raw_df["city"])
        assert "Paris" in raw_df["city_clean"].values

        # 4. extract_tech_stack
        raw_df["tech_stack"] = raw_df["description"].apply(extract_tech_stack)
        assert raw_df["tech_stack"].str.contains("Python").any()

        # 5. parse_salary
        for idx, row in raw_df.iterrows():
            if pd.notna(row["salary_min"]) and pd.notna(row["salary_max"]):
                mn, mx, cur = parse_salary(
                    f"{int(row['salary_min'])}-{int(row['salary_max'])}€"
                )
                raw_df.at[idx, "salary_avg"] = (mn + mx) / 2 if mn else None
            else:
                raw_df.at[idx, "salary_avg"] = None

        assert raw_df["salary_avg"].notna().sum() >= 2

        # 6. deduplicate
        doubled = pd.concat([raw_df, raw_df.iloc[:1]], ignore_index=True)
        result = deduplicate(doubled)
        assert len(result) == len(raw_df)

    def test_etl_preserves_columns(self, raw_df):
        from src.transform.etl_transform import normalize_contract, normalize_date

        raw_df["published_at"] = normalize_date(raw_df["published_at"])
        raw_df["contract_type"] = normalize_contract(raw_df["contract_type"])

        required = ["title", "company", "city", "description", "contract_type",
                     "published_at"]
        for col in required:
            assert col in raw_df.columns

    def test_etl_handles_empty_df(self):
        from src.transform.etl_transform import normalize_contract, normalize_date

        empty = pd.DataFrame(columns=["published_at", "contract_type"])
        result_date = normalize_date(empty["published_at"])
        result_contract = normalize_contract(empty["contract_type"])
        assert len(result_date) == 0
        assert len(result_contract) == 0


# ═══════════════════════════════════════════════════════════
# 2. Scraping → enrichissement → structure S3-ready
# ═══════════════════════════════════════════════════════════

class TestScrapingToStorage:
    """Vérifie que les données enrichies sont compatibles avec le stockage S3."""

    def test_enrich_then_build_key(self):
        from src.scraping.api_producer import enrich_offer
        from src.storage.kafka_to_s3_consumer import build_s3_key

        enriched = enrich_offer(SAMPLE_RAW[0], page=1)
        key = build_s3_key(batch_id=1)

        # L'offre enrichie contient les champs attendus
        assert "source" in enriched
        assert "fetched_at" in enriched
        assert "data" in enriched

        # La clé S3 est bien formée
        assert key.startswith("raw/adzuna/")
        assert key.endswith(".jsonl")

    def test_enriched_offer_is_json_serializable(self):
        from src.scraping.api_producer import enrich_offer

        enriched = enrich_offer(SAMPLE_RAW[0], page=1)
        serialized = json.dumps(enriched, default=str)
        deserialized = json.loads(serialized)
        assert deserialized["source"] == "adzuna"
        assert deserialized["data"]["title"] == "Data Engineer"


# ═══════════════════════════════════════════════════════════
# 3. Dashboard — structure, imports, callbacks
# ═══════════════════════════════════════════════════════════

@pytest.fixture()
def _mock_db(monkeypatch):
    """Mock load_data pour les tests dashboard (pas de PostgreSQL)."""
    sample = pd.DataFrame({
        "title": ["Data Engineer", "Data Scientist"],
        "company": ["Acme", "Beta"],
        "city": ["Paris, France", "Lyon"],
        "city_clean": ["Paris", "Lyon"],
        "contract_type": ["CDI", "CDD"],
        "salary_avg": [50000.0, 45000.0],
        "salary_min": [45000.0, 40000.0],
        "salary_max": [55000.0, 50000.0],
        "tech_stack": ["Python, Docker", "Python, SQL"],
        "published_at": pd.to_datetime(["2026-03-01", "2026-03-05"], utc=True),
        "description": ["Data engineer Python", "Data scientist SQL"],
        "lat": [48.8566, 45.764],
        "lon": [2.3522, 4.8357],
    })
    import src.visualization.data as data_mod
    monkeypatch.setattr(data_mod, "DF", sample)


class TestDashboardStructure:
    """Vérifie que le dashboard Dash se construit sans erreur."""

    def test_app_import(self, _mock_db):
        from src.visualization.app import app
        assert app is not None
        assert app.title == "DPIA — Marché Data Science"

    def test_layout_has_required_components(self, _mock_db):
        from src.visualization.app import app
        layout = app.layout
        # Layout doit contenir un Location (url) et le contenu
        assert layout is not None

    def test_server_is_flask(self, _mock_db):
        from src.visualization.app import server
        assert hasattr(server, "test_client")

    def test_all_page_layouts_callable(self, _mock_db):
        from src.visualization.pages import (
            competences, dashboard, geographie, qualite, salaires, temporel,
        )
        modules = [dashboard, competences, temporel, geographie, salaires, qualite]
        for mod in modules:
            result = mod.layout()
            assert result is not None, f"{mod.__name__}.layout() returned None"


class TestDashboardRoutes:
    """Vérifie que chaque route renvoie HTTP 200 via le test client Flask."""

    ROUTES = ["/", "/competences", "/temporel", "/geographie", "/salaires", "/qualite"]

    def test_all_routes_200(self, _mock_db):
        from src.visualization.app import server

        client = server.test_client()
        for route in self.ROUTES:
            resp = client.get(route)
            assert resp.status_code == 200, f"Route {route} returned {resp.status_code}"


class TestFilterIntegration:
    """Vérifie filter_df → JSON → _read_store round-trip."""

    def test_filter_serialize_deserialize(self, _mock_db):
        from src.visualization.data import _read_store, filter_df

        df = filter_df("ALL", "ALL", [0, 150])
        json_data = df.to_json(date_format="iso", orient="split")
        restored = _read_store(json_data)

        assert len(restored) == len(df)
        assert list(restored.columns) == list(df.columns)

    def test_filter_by_city_round_trip(self, _mock_db):
        from src.visualization.data import _read_store, filter_df

        df = filter_df("Paris", "ALL", [0, 150])
        json_data = df.to_json(date_format="iso", orient="split")
        restored = _read_store(json_data)

        assert all(restored["city_clean"] == "Paris")


# ═══════════════════════════════════════════════════════════
# 4. Config cohérence
# ═══════════════════════════════════════════════════════════

class TestConfigCrossModule:
    """Vérifie que les constantes config sont cohérentes entre modules."""

    def test_remote_patterns_match_detect_remote(self, _mock_db):
        from src.visualization.config import REMOTE_PATTERNS
        from src.visualization.data import _detect_remote

        labels = set(REMOTE_PATTERNS.keys())
        # _detect_remote devrait retourner une clé de REMOTE_PATTERNS ou "Non précisé"
        row = {"description": "poste en full remote", "title": "Dev"}
        result = _detect_remote(row)
        assert result in labels or result == "Non précisé"

    def test_city_coords_covers_sample_cities(self, _mock_db):
        from src.visualization.config import CITY_COORDS

        # Villes fréquentes dans les données
        for city in ["Paris", "Lyon", "Marseille", "Toulouse", "Nantes"]:
            assert city in CITY_COORDS, f"{city} missing from CITY_COORDS"
