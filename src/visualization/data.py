"""
Chargement des données et fonctions utilitaires partagées.
"""

import re
import time
from io import StringIO

import pandas as pd
from sqlalchemy import create_engine

from src.visualization.config import (
    CITY_COORDS, DB_HOST, DB_NAME, DB_PASS, DB_PORT, DB_USER,
    REMOTE_PATTERNS, SQL_TABLE,
)

_EMPTY_COLS = [
    "title", "company", "city", "contract_type",
    "salary_avg", "salary_min", "salary_max",
    "tech_stack", "published_at", "description",
    "city_clean", "lat", "lon",
]


def load_data() -> pd.DataFrame:
    conn_str = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    engine = create_engine(conn_str)
    for attempt in range(5):
        try:
            df = pd.read_sql_table(SQL_TABLE, engine)
            break
        except Exception as exc:
            print(f"[load_data] attempt {attempt+1}/5 failed: {exc}")
            if attempt < 4:
                time.sleep(3)
            else:
                print("[load_data] returning empty DataFrame")
                return pd.DataFrame(columns=_EMPTY_COLS)
    df["published_at"] = pd.to_datetime(df["published_at"], errors="coerce", utc=True)
    df["salary_avg"] = pd.to_numeric(df["salary_avg"], errors="coerce")
    df["salary_min"] = pd.to_numeric(df["salary_min"], errors="coerce")
    df["salary_max"] = pd.to_numeric(df["salary_max"], errors="coerce")
    df["city_clean"] = df["city"].fillna("Non précisé").apply(lambda x: x.split(",")[0].strip())
    df["lat"] = df["city_clean"].map(lambda c: CITY_COORDS.get(c, (None, None))[0])
    df["lon"] = df["city_clean"].map(lambda c: CITY_COORDS.get(c, (None, None))[1])
    return df


DF = load_data()


def filter_df(city, contract, salary_range):
    df = DF.copy()
    if df.empty:
        return df
    if city != "ALL" and "city_clean" in df.columns:
        df = df[df["city_clean"] == city]
    if contract != "ALL" and "contract_type" in df.columns:
        df = df[df["contract_type"] == contract]
    if "salary_avg" in df.columns:
        sal_min, sal_max = salary_range[0] * 1000, salary_range[1] * 1000
        df = df[
            (df["salary_avg"].isna()) |
            ((df["salary_avg"] >= sal_min) & (df["salary_avg"] <= sal_max))
        ]
    return df


def _read_store(data):
    if not data:
        return pd.DataFrame(columns=_EMPTY_COLS)
    df = pd.read_json(StringIO(data), orient="split")
    if df.empty:
        return pd.DataFrame(columns=_EMPTY_COLS)
    df["published_at"] = pd.to_datetime(df["published_at"], errors="coerce", utc=True)
    return df


def _text_blob(df):
    if df.empty:
        return pd.Series(dtype=str)
    desc = df["description"].fillna("") if "description" in df.columns else pd.Series("", index=df.index)
    stack = df["tech_stack"].fillna("") if "tech_stack" in df.columns else pd.Series("", index=df.index)
    return (desc + " " + stack).str.lower()


def _keyword_pct(blob, keywords):
    mask = blob.str.contains("|".join(re.escape(k) for k in keywords), case=False, na=False)
    return mask.mean() * 100 if len(blob) > 0 else 0


def _keyword_count(blob, keywords):
    mask = blob.str.contains("|".join(re.escape(k) for k in keywords), case=False, na=False)
    return int(mask.sum())


def _detect_remote(row):
    text = f"{row.get('description', '')} {row.get('title', '')}".lower()
    for label, pat in REMOTE_PATTERNS.items():
        if pat.search(text):
            return label
    return "Non précisé"


JOUR_FR = {0: "Lundi", 1: "Mardi", 2: "Mercredi", 3: "Jeudi",
           4: "Vendredi", 5: "Samedi", 6: "Dimanche"}
