"""
Tests unitaires — ETL Transform (parse_salary, normalize_*, extract_tech_stack, deduplicate).
"""

import pandas as pd
import pytest

from src.transform.etl_transform import (
    deduplicate,
    extract_tech_stack,
    normalize_city,
    normalize_contract,
    normalize_date,
    parse_salary,
)


# ═══════════════════════════════════════════════════════════
# parse_salary
# ═══════════════════════════════════════════════════════════

class TestParseSalary:
    def test_range_with_k_euro(self):
        mn, mx, cur = parse_salary("45k-55k€")
        assert mn == 45_000
        assert mx == 55_000
        assert cur == "EUR"

    def test_range_with_spaces(self):
        mn, mx, cur = parse_salary("45 000 - 55 000 EUR")
        assert mn == 45_000
        assert mx == 55_000
        assert cur == "EUR"

    def test_single_value(self):
        mn, mx, cur = parse_salary("50K€")
        assert mn == 50_000
        assert mx == 50_000

    def test_usd_currency(self):
        _, _, cur = parse_salary("80000 USD")
        assert cur == "USD"

    def test_gbp_currency(self):
        _, _, cur = parse_salary("£60000")
        assert cur == "GBP"

    def test_chf_currency(self):
        _, _, cur = parse_salary("90K CHF")
        assert cur == "CHF"

    def test_empty_string(self):
        assert parse_salary("") == (None, None, "EUR")

    def test_none_input(self):
        assert parse_salary(None) == (None, None, "EUR")

    def test_non_string(self):
        assert parse_salary(12345) == (None, None, "EUR")

    def test_no_numbers(self):
        assert parse_salary("salaire compétitif") == (None, None, "EUR")

    def test_min_max_order(self):
        mn, mx, _ = parse_salary("60k-40k€")
        assert mn <= mx


# ═══════════════════════════════════════════════════════════
# normalize_date
# ═══════════════════════════════════════════════════════════

class TestNormalizeDate:
    def test_iso_string(self):
        s = pd.Series(["2026-03-15T12:00:00Z"])
        result = normalize_date(s)
        assert pd.notna(result.iloc[0])

    def test_invalid_date(self):
        s = pd.Series(["not-a-date"])
        result = normalize_date(s)
        assert pd.isna(result.iloc[0])

    def test_mixed(self):
        s = pd.Series(["2026-01-01", None, "bad"])
        result = normalize_date(s)
        assert pd.notna(result.iloc[0])
        assert pd.isna(result.iloc[1])
        assert pd.isna(result.iloc[2])


# ═══════════════════════════════════════════════════════════
# normalize_contract
# ═══════════════════════════════════════════════════════════

class TestNormalizeContract:
    @pytest.mark.parametrize("raw,expected", [
        ("permanent", "CDI"),
        ("cdi", "CDI"),
        ("full_time", "CDI"),
        ("contract", "CDD"),
        ("cdd", "CDD"),
        ("temporary", "CDD"),
        ("freelance", "Freelance"),
        ("internship", "Stage"),
        ("stage", "Stage"),
        ("apprenticeship", "Alternance"),
        ("alternance", "Alternance"),
        ("part_time", "Temps partiel"),
    ])
    def test_known_mappings(self, raw, expected):
        result = normalize_contract(pd.Series([raw]))
        assert result.iloc[0] == expected

    def test_uppercase_input(self):
        result = normalize_contract(pd.Series(["  CDI  "]))
        assert result.iloc[0] == "CDI"

    def test_nan_becomes_string(self):
        result = normalize_contract(pd.Series([None]))
        # normalize_contract converts None → "none" via .str.lower().str.strip()
        assert result.iloc[0] in ("none", None) or pd.isna(result.iloc[0])


# ═══════════════════════════════════════════════════════════
# normalize_city
# ═══════════════════════════════════════════════════════════

class TestNormalizeCity:
    def test_title_case(self):
        result = normalize_city(pd.Series(["paris"]))
        assert result.iloc[0] == "Paris"

    def test_paris_france_alias(self):
        result = normalize_city(pd.Series(["Paris, France"]))
        assert result.iloc[0] == "Paris"

    def test_ile_de_france_alias(self):
        result = normalize_city(pd.Series(["ile-de-france"]))
        assert result.iloc[0] == "Paris"

    def test_nan_filled(self):
        result = normalize_city(pd.Series([None]))
        assert result.iloc[0] == "Non Precise"


# ═══════════════════════════════════════════════════════════
# extract_tech_stack
# ═══════════════════════════════════════════════════════════

class TestExtractTechStack:
    def test_basic_skills(self):
        desc = "Maîtrise de Python, SQL et Docker requise."
        result = extract_tech_stack(desc)
        assert "Python" in result
        assert "SQL" in result
        assert "Docker" in result

    def test_case_insensitive(self):
        result = extract_tech_stack("connaissance en PYTORCH et tensorflow")
        assert "PyTorch" in result
        assert "TensorFlow" in result

    def test_empty_string(self):
        assert extract_tech_stack("") == ""

    def test_none_input(self):
        assert extract_tech_stack(None) == ""

    def test_no_skills(self):
        assert extract_tech_stack("Gestion de projet et communication") == ""

    def test_multiple_cloud_providers(self):
        result = extract_tech_stack("AWS, Azure et GCP")
        for skill in ["AWS", "Azure", "GCP"]:
            assert skill in result


# ═══════════════════════════════════════════════════════════
# deduplicate
# ═══════════════════════════════════════════════════════════

class TestDeduplicate:
    def _make_df(self, rows):
        return pd.DataFrame(rows, columns=["title", "company", "city", "salary_avg"])

    def test_exact_duplicates_removed(self):
        df = self._make_df([
            ["Data Engineer", "Acme", "Paris", 50000],
            ["Data Engineer", "Acme", "Paris", 50000],
        ])
        result = deduplicate(df)
        assert len(result) == 1

    def test_case_insensitive_dedup(self):
        df = self._make_df([
            ["Data Engineer", "Acme", "Paris", 50000],
            ["data engineer", "acme", "paris", 55000],
        ])
        result = deduplicate(df)
        assert len(result) == 1

    def test_different_jobs_kept(self):
        df = self._make_df([
            ["Data Engineer", "Acme", "Paris", 50000],
            ["Data Scientist", "Beta", "Lyon", 55000],
        ])
        result = deduplicate(df)
        assert len(result) == 2

    def test_keeps_most_complete_row(self):
        df = self._make_df([
            ["Data Engineer", "Acme", "Paris", None],
            ["data engineer", "acme", "paris", 50000],
        ])
        result = deduplicate(df)
        assert len(result) == 1
        assert result.iloc[0]["salary_avg"] == 50000
