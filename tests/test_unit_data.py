"""
Tests unitaires — visualization.data (fonctions utilitaires sans accès DB).

Le module data.py appelle load_data() à l'import, qui nécessite PostgreSQL.
On mock load_data pour tester filter_df, _read_store, _text_blob, etc.
"""

import json

import pandas as pd
import pytest

# ── Fixtures ──────────────────────────────────────────────

SAMPLE_DF = pd.DataFrame({
    "title": ["Data Engineer", "Data Scientist", "ML Engineer", "Analyst"],
    "company": ["Acme", "Beta", "Gamma", "Delta"],
    "city": ["Paris", "Lyon, France", "Paris", "Marseille"],
    "city_clean": ["Paris", "Lyon", "Paris", "Marseille"],
    "contract_type": ["CDI", "CDD", "CDI", "Stage"],
    "salary_avg": [50000.0, 45000.0, None, 35000.0],
    "salary_min": [45000.0, 40000.0, None, 30000.0],
    "salary_max": [55000.0, 50000.0, None, 40000.0],
    "tech_stack": ["Python, Docker", "Python, SQL", "TensorFlow", "R, Tableau"],
    "published_at": pd.to_datetime(
        ["2026-03-01", "2026-03-05", "2026-03-10", "2026-03-15"], utc=True
    ),
    "description": [
        "Poste de data engineer avec Python et Docker",
        "Recherche data scientist maîtrisant SQL",
        "ML engineer spécialisé deep learning pytorch",
        "Analyste BI avec Tableau et Power BI",
    ],
    "lat": [48.8566, 45.764, 48.8566, 43.2965],
    "lon": [2.3522, 4.8357, 2.3522, 5.3698],
})


@pytest.fixture(autouse=True)
def _mock_load_data(monkeypatch):
    """Remplace DF dans data.py par un DataFrame de test sans toucher à PostgreSQL."""
    import src.visualization.data as data_mod
    monkeypatch.setattr(data_mod, "DF", SAMPLE_DF.copy())


# ═══════════════════════════════════════════════════════════
# filter_df
# ═══════════════════════════════════════════════════════════

class TestFilterDf:
    def test_no_filter(self):
        from src.visualization.data import filter_df

        result = filter_df("ALL", "ALL", [0, 150])
        assert len(result) == 4

    def test_filter_by_city(self):
        from src.visualization.data import filter_df

        result = filter_df("Paris", "ALL", [0, 150])
        assert all(result["city_clean"] == "Paris")
        assert len(result) == 2

    def test_filter_by_contract(self):
        from src.visualization.data import filter_df

        result = filter_df("ALL", "CDI", [0, 150])
        assert all(result["contract_type"] == "CDI")

    def test_filter_by_salary_range(self):
        from src.visualization.data import filter_df

        result = filter_df("ALL", "ALL", [40, 55])
        # salary_range is in k€ → filter keeps 40k-55k + NaN
        salaries = result["salary_avg"].dropna()
        assert all(salaries >= 40_000)
        assert all(salaries <= 55_000)

    def test_nan_salary_preserved(self):
        from src.visualization.data import filter_df

        result = filter_df("ALL", "ALL", [0, 150])
        assert result["salary_avg"].isna().sum() == 1

    def test_combined_filters(self):
        from src.visualization.data import filter_df

        result = filter_df("Paris", "CDI", [0, 150])
        assert len(result) >= 1
        assert all(result["city_clean"] == "Paris")
        assert all(result["contract_type"] == "CDI")


# ═══════════════════════════════════════════════════════════
# _read_store
# ═══════════════════════════════════════════════════════════

class TestReadStore:
    def test_valid_json(self):
        from src.visualization.data import _read_store

        df = SAMPLE_DF.copy()
        data = df.to_json(date_format="iso", orient="split")
        result = _read_store(data)
        assert len(result) == 4
        assert "title" in result.columns

    def test_empty_data(self):
        from src.visualization.data import _read_store

        result = _read_store(None)
        assert result.empty

    def test_empty_string(self):
        from src.visualization.data import _read_store

        result = _read_store("")
        assert result.empty


# ═══════════════════════════════════════════════════════════
# _text_blob
# ═══════════════════════════════════════════════════════════

class TestTextBlob:
    def test_combines_description_and_tech_stack(self):
        from src.visualization.data import _text_blob

        blob = _text_blob(SAMPLE_DF)
        assert "python" in blob.iloc[0]
        assert "docker" in blob.iloc[0]

    def test_lowercase(self):
        from src.visualization.data import _text_blob

        blob = _text_blob(SAMPLE_DF)
        for val in blob:
            assert val == val.lower()

    def test_empty_df(self):
        from src.visualization.data import _text_blob

        result = _text_blob(pd.DataFrame())
        assert len(result) == 0


# ═══════════════════════════════════════════════════════════
# _keyword_pct / _keyword_count
# ═══════════════════════════════════════════════════════════

class TestKeywordHelpers:
    def test_keyword_pct(self):
        from src.visualization.data import _keyword_pct, _text_blob

        blob = _text_blob(SAMPLE_DF)
        pct = _keyword_pct(blob, ["python"])
        assert pct > 0  # At least 2/4 have python
        assert pct <= 100

    def test_keyword_count(self):
        from src.visualization.data import _keyword_count, _text_blob

        blob = _text_blob(SAMPLE_DF)
        count = _keyword_count(blob, ["python"])
        assert count >= 2

    def test_nonexistent_keyword(self):
        from src.visualization.data import _keyword_count, _text_blob

        blob = _text_blob(SAMPLE_DF)
        assert _keyword_count(blob, ["zzzznotexist"]) == 0


# ═══════════════════════════════════════════════════════════
# _detect_remote
# ═══════════════════════════════════════════════════════════

class TestDetectRemote:
    def test_full_remote(self):
        from src.visualization.data import _detect_remote

        row = {"description": "Poste en full remote", "title": "Data Engineer"}
        assert _detect_remote(row) == "Full Remote"

    def test_hybrid(self):
        from src.visualization.data import _detect_remote

        row = {"description": "Poste hybride 3j/semaine", "title": "Dev"}
        assert _detect_remote(row) == "Hybride"

    def test_onsite(self):
        from src.visualization.data import _detect_remote

        row = {"description": "Poste sur site uniquement", "title": "Dev"}
        assert _detect_remote(row) == "Présentiel"

    def test_unknown(self):
        from src.visualization.data import _detect_remote

        row = {"description": "On cherche un dev motivé", "title": "Dev Python"}
        assert _detect_remote(row) == "Non précisé"
