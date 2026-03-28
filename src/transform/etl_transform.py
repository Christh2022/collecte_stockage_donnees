"""
ETL Transform : S3 raw -> clean_jobs (CSV + PostgreSQL).

Charge les fichiers bruts depuis S3/MinIO (Adzuna JSONL + WTJ JSON/CSV),
normalise, dédoublonne, enrichit et exporte vers CSV et/ou PostgreSQL.

Pipeline :
    1. Lecture multi-sources (Adzuna API + WTJ scraping)
    2. Normalisation des colonnes, dates, salaires
    3. Dédoublonnage intelligent (entreprise + titre + ville)
    4. Enrichissement (source, tech_stack via regex)
    5. Optimisation des types pour SQL
    6. Export CSV + insertion PostgreSQL

Usage:
    python -m src.transform.etl_transform

Variables d'environnement : voir .env / .env.example
"""

import io
import json
import os
import re
import sys
import time

import boto3
import pandas as pd
from dotenv import load_dotenv

from src.monitoring.logger import get_logger

load_dotenv()
logger = get_logger("etl_transform")

# ── Configuration ──────────────────────────────────────────
S3_BUCKET = os.getenv("S3_BUCKET_NAME", "dpia-data-bucket")
S3_PREFIX_ADZUNA = os.getenv("S3_PREFIX", "raw/adzuna")
S3_PREFIX_WTJ = os.getenv("S3_PREFIX_WTJ", "raw/wtj")
S3_PREFIX_LESJEUDIS = os.getenv("S3_PREFIX_LESJEUDIS", "raw/lesjeudis")
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT")
ENV_MODE = os.getenv("ENV_MODE", "dev")

OUTPUT_DIR = os.getenv("ETL_OUTPUT_DIR", "data/clean")
OUTPUT_FILE = "clean_jobs.csv"
SQL_TABLE = os.getenv("ETL_SQL_TABLE", "offres_emploi_clean")

# PostgreSQL
DB_HOST = os.getenv("RDS_HOST", "postgres") or "postgres"
DB_PORT = os.getenv("RDS_PORT", "5432") or "5432"
DB_NAME = os.getenv("RDS_DB_NAME", "dpia_db") or "dpia_db"
DB_USER = os.getenv("RDS_USERNAME", "airflow") or "airflow"
DB_PASS = os.getenv("RDS_PASSWORD", "airflow") or "airflow"

# ── Mapping de normalisation ──────────────────────────────
# Colonnes cibles standardisées
TARGET_COLUMNS = [
    "title", "company", "city", "contract_type", "salary_min",
    "salary_max", "salary_avg", "currency", "description",
    "category", "published_at", "url", "source", "tech_stack",
    "collected_at",
]

ADZUNA_COL_MAP = {
    "title": "title",
    "company.display_name": "company",
    "location.display_name": "city",
    "contract_type": "contract_type",
    "contract_time": "contract_time",
    "salary_min": "salary_min",
    "salary_max": "salary_max",
    "description": "description",
    "category.label": "category",
    "created": "published_at",
    "redirect_url": "url",
    "id": "source_id",
}

WTJ_COL_MAP = {
    "title": "title",
    "job_title": "title",
    "titre_poste": "title",
    "company_name": "company",
    "entreprise": "company",
    "organization.name": "company",
    "location": "city",
    "ville": "city",
    "office.city": "city",
    "contract_type": "contract_type",
    "type_contrat": "contract_type",
    "salary": "salary_raw",
    "salaire": "salary_raw",
    "description": "description",
    "published_at": "published_at",
    "date_publication": "published_at",
    "url": "url",
    "link": "url",
}

LESJEUDIS_COL_MAP = {
    "title": "title",
    "company": "company",
    "location": "city",
    "contract_type": "contract_type",
    "salary": "salary_raw",
    "description": "description",
    "url": "url",
    "remote": "remote",
}

# ── Tech stack : compétences à détecter ───────────────────
TECH_SKILLS = [
    "Python", "SQL", "R", "Scala", "Java", "Julia", "Go",
    "Spark", "PySpark", "Hadoop", "Hive", "Kafka", "Flink",
    "TensorFlow", "PyTorch", "Scikit-Learn", "Keras", "XGBoost", "LightGBM",
    "AWS", "Azure", "GCP", "Google Cloud",
    "Docker", "Kubernetes", "Airflow", "dbt", "MLflow", "Kubeflow",
    "Tableau", "Power BI", "Looker", "Metabase",
    "Snowflake", "BigQuery", "Redshift", "Databricks",
    "MongoDB", "PostgreSQL", "MySQL", "Elasticsearch", "Redis",
    "FastAPI", "Flask", "Django",
    "Git", "Terraform", "CI/CD", "Linux",
    "Deep Learning", "Machine Learning", "NLP", "Computer Vision",
    "Pandas", "NumPy", "SciPy",
]

# Pré-compiler les regex pour la performance
_SKILL_PATTERNS = {
    skill: re.compile(r"\b" + re.escape(skill) + r"\b", re.IGNORECASE)
    for skill in TECH_SKILLS
}


# ═══════════════════════════════════════════════════════════
# S3 / MinIO
# ═══════════════════════════════════════════════════════════

def create_s3_client():
    """Client S3 adapté au mode (dev=MinIO, prod=AWS)."""
    if MINIO_ENDPOINT:
        return boto3.client(
            "s3",
            endpoint_url=MINIO_ENDPOINT,
            aws_access_key_id=os.getenv("MINIO_ROOT_USER", "minioadmin"),
            aws_secret_access_key=os.getenv("MINIO_ROOT_PASSWORD", "minioadmin"),
        )
    return boto3.client("s3")


def list_s3_files(s3, prefix: str) -> list[dict]:
    """Liste les fichiers S3 sous un préfixe, triés du plus récent au plus ancien."""
    files = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=prefix):
        for obj in page.get("Contents", []):
            if obj["Size"] > 0:
                files.append({
                    "key": obj["Key"],
                    "modified": obj["LastModified"],
                    "size": obj["Size"],
                })
    files.sort(key=lambda x: x["modified"], reverse=True)
    return files


def load_jsonl(s3, key: str) -> list[dict]:
    """Charge un fichier JSONL depuis S3."""
    obj = s3.get_object(Bucket=S3_BUCKET, Key=key)
    content = obj["Body"].read().decode("utf-8")
    records = []
    for i, line in enumerate(content.strip().split("\n"), 1):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as e:
            logger.warning("Ligne %d corrompue dans %s : %s", i, key, e)
    return records


def load_json(s3, key: str) -> list[dict]:
    """Charge un fichier JSON (array ou objet unique) depuis S3."""
    obj = s3.get_object(Bucket=S3_BUCKET, Key=key)
    content = obj["Body"].read().decode("utf-8")
    data = json.loads(content)
    return data if isinstance(data, list) else [data]


def load_csv(s3, key: str) -> pd.DataFrame:
    """Charge un fichier CSV depuis S3."""
    obj = s3.get_object(Bucket=S3_BUCKET, Key=key)
    return pd.read_csv(io.BytesIO(obj["Body"].read()), encoding="utf-8")


# ═══════════════════════════════════════════════════════════
# ÉTAPE 1 : Lecture multi-sources
# ═══════════════════════════════════════════════════════════

def load_adzuna(s3) -> pd.DataFrame:
    """Charge tous les fichiers Adzuna JSONL depuis S3."""
    files = list_s3_files(s3, S3_PREFIX_ADZUNA)
    logger.info("[ADZUNA] %d fichiers trouvés sous '%s/'", len(files), S3_PREFIX_ADZUNA)

    all_records = []
    files_ok, files_err = 0, 0

    for f in files:
        try:
            records = load_jsonl(s3, f["key"])
            # Les records Adzuna sont enrichis : {source, data: {offre brute}}
            for r in records:
                entry = r.get("data", r)
                entry["_fetched_at"] = r.get("fetched_at")
                all_records.append(entry)
            files_ok += 1
        except Exception as e:
            logger.warning("[ADZUNA] Fichier corrompu ignoré : %s (%s)", f["key"], e)
            files_err += 1

    if not all_records:
        logger.warning("[ADZUNA] Aucun enregistrement chargé")
        return pd.DataFrame()

    df = pd.json_normalize(all_records)
    logger.info(
        "[ADZUNA] %d offres chargées (%d fichiers OK, %d erreurs)",
        len(df), files_ok, files_err,
    )
    return df


def load_wtj(s3) -> pd.DataFrame:
    """Charge les fichiers WTJ (JSON/CSV) depuis S3."""
    try:
        files = list_s3_files(s3, S3_PREFIX_WTJ)
    except Exception:
        logger.info("[WTJ] Aucun fichier disponible sous '%s/'", S3_PREFIX_WTJ)
        return pd.DataFrame()

    if not files:
        logger.info("[WTJ] Aucun fichier trouvé")
        return pd.DataFrame()

    logger.info("[WTJ] %d fichiers trouvés sous '%s/'", len(files), S3_PREFIX_WTJ)
    all_records = []
    files_ok, files_err = 0, 0

    for f in files:
        key = f["key"]
        try:
            if key.endswith(".jsonl"):
                all_records.extend(load_jsonl(s3, key))
            elif key.endswith(".json"):
                all_records.extend(load_json(s3, key))
            elif key.endswith(".csv"):
                df_temp = load_csv(s3, key)
                all_records.extend(df_temp.to_dict("records"))
            else:
                continue
            files_ok += 1
        except Exception as e:
            logger.warning("[WTJ] Fichier corrompu ignoré : %s (%s)", key, e)
            files_err += 1

    if not all_records:
        logger.warning("[WTJ] Aucun enregistrement chargé")
        return pd.DataFrame()

    df = pd.DataFrame(all_records)
    logger.info(
        "[WTJ] %d offres chargées (%d fichiers OK, %d erreurs)",
        len(df), files_ok, files_err,
    )
    return df


def load_lesjeudis(s3) -> pd.DataFrame:
    """Charge tous les fichiers LesJeudis JSONL depuis S3."""
    files = list_s3_files(s3, S3_PREFIX_LESJEUDIS)
    logger.info("[LESJEUDIS] %d fichiers trouv\u00e9s sous '%s/'", len(files), S3_PREFIX_LESJEUDIS)

    all_records = []
    files_ok, files_err = 0, 0

    for f in files:
        try:
            records = load_jsonl(s3, f["key"])
            for r in records:
                entry = r.get("data", r)
                entry["_fetched_at"] = r.get("fetched_at")
                all_records.append(entry)
            files_ok += 1
        except Exception as e:
            logger.warning("[LESJEUDIS] Fichier corrompu ignor\u00e9 : %s (%s)", f["key"], e)
            files_err += 1

    if not all_records:
        logger.warning("[LESJEUDIS] Aucun enregistrement charg\u00e9")
        return pd.DataFrame()

    df = pd.json_normalize(all_records)
    logger.info(
        "[LESJEUDIS] %d offres charg\u00e9es (%d fichiers OK, %d erreurs)",
        len(df), files_ok, files_err,
    )
    return df


# ═══════════════════════════════════════════════════════════
# ÉTAPE 2 : Normalisation
# ═══════════════════════════════════════════════════════════

def normalize_columns(df: pd.DataFrame, col_map: dict, source_name: str) -> pd.DataFrame:
    """Renomme les colonnes selon le mapping, ajoute la source."""
    rename = {k: v for k, v in col_map.items() if k in df.columns}
    df = df.rename(columns=rename)
    df["source"] = source_name
    return df


def parse_salary(raw: str) -> tuple[float | None, float | None, str]:
    """Extrait salaire min/max et devise d'une chaîne.

    Gère : '45k-55k€', '45000 - 55000 EUR', '45K', '45 000€/an', etc.
    """
    if not isinstance(raw, str) or not raw.strip():
        return None, None, "EUR"

    text = raw.upper().replace("\u00a0", " ").replace(",", ".")

    # Détecter la devise
    currency = "EUR"
    if "$" in text or "USD" in text:
        currency = "USD"
    elif "£" in text or "GBP" in text:
        currency = "GBP"
    elif "CHF" in text:
        currency = "CHF"

    # Extraire les nombres (avec gestion du K = ×1000)
    numbers = []
    for match in re.finditer(r"(\d[\d\s]*\.?\d*)\s*K?", text):
        num_str = match.group(1).replace(" ", "")
        try:
            val = float(num_str)
            # Si "K" suit le nombre
            full_match = text[match.start():match.end()]
            if "K" in full_match and val < 1000:
                val *= 1000
            numbers.append(val)
        except ValueError:
            continue

    if len(numbers) >= 2:
        return min(numbers[0], numbers[1]), max(numbers[0], numbers[1]), currency
    elif len(numbers) == 1:
        return numbers[0], numbers[0], currency
    return None, None, currency


def normalize_date(series: pd.Series) -> pd.Series:
    """Convertit une série de dates en datetime UTC (ISO 8601)."""
    return pd.to_datetime(series, errors="coerce", utc=True)


def normalize_contract(series: pd.Series) -> pd.Series:
    """Standardise les types de contrat."""
    mapping = {
        "permanent": "CDI", "cdi": "CDI", "full_time": "CDI",
        "contract": "CDD", "cdd": "CDD", "temporary": "CDD",
        "freelance": "Freelance", "independent": "Freelance",
        "internship": "Stage", "stage": "Stage", "intern": "Stage",
        "apprenticeship": "Alternance", "alternance": "Alternance",
        "part_time": "Temps partiel",
    }
    normalized = series.astype(str).str.lower().str.strip()
    return normalized.replace(mapping).replace("nan", pd.NA)


_STAGE_PATTERN = re.compile(
    r"\b(stage|stagiaire|internship|intern)\b", re.IGNORECASE,
)
_ALTERNANCE_PATTERN = re.compile(
    r"\b(alternance|alternant|apprenti|apprentissage|apprentice)\b", re.IGNORECASE,
)


def infer_contract_from_text(df: pd.DataFrame) -> pd.DataFrame:
    """Infère Stage/Alternance depuis le titre ou la description si contract_type est manquant."""
    text = (
        df["title"].fillna("") + " " + df.get("description", pd.Series("", index=df.index)).fillna("")
    )
    is_missing = df["contract_type"].isna()

    is_stage = text.str.contains(_STAGE_PATTERN, na=False)
    is_alternance = text.str.contains(_ALTERNANCE_PATTERN, na=False)

    # Alternance first (some offers mention both "stage" and "alternance")
    df.loc[is_missing & is_alternance, "contract_type"] = "Alternance"
    df.loc[is_missing & is_stage & ~is_alternance, "contract_type"] = "Stage"

    # Also fix wrongly classified (e.g. stage labelled as CDI/CDD)
    wrong_cdi_cdd = df["contract_type"].isin(["CDI", "CDD"])
    df.loc[wrong_cdi_cdd & is_stage & ~is_alternance, "contract_type"] = "Stage"
    df.loc[wrong_cdi_cdd & is_alternance, "contract_type"] = "Alternance"

    n_stage = (df["contract_type"] == "Stage").sum()
    n_alt = (df["contract_type"] == "Alternance").sum()
    logger.info("[CONTRACT] Inférence : %d stages, %d alternances détectés", n_stage, n_alt)
    return df


def normalize_city(series: pd.Series) -> pd.Series:
    """Normalise les noms de ville."""
    import re as _re
    s = series.fillna("Non precise").str.strip().str.title()

    # Filtrer les entrées JSON/HTML invalides
    s = s.apply(lambda x: "Non precise" if any(k in str(x) for k in [
        "{", "}", "Props", "Authenticated", "@Context", "Schema.Org",
        "Http", "<", ">", "\\",
    ]) else x)

    # Mapping direct
    direct = {
        "Paris, France": "Paris",
        "Ile-De-France": "Paris",
        "Ile De France": "Paris",
        "France": "Non precise",
        "Haute-Garonne, Occitanie": "Toulouse",
        "Nord, Hauts-De-France": "Lille",
        "Rhône, Auvergne-Rhône-Alpes": "Lyon",
        "Bouches-Du-Rhône, Provence-Alpes-Côte D'Azur": "Marseille",
        "Hauts-De-Seine, Ile-De-France": "Paris",
        "Gironde, Nouvelle-Aquitaine": "Bordeaux",
        "Loire-Atlantique, Pays De La Loire": "Nantes",
        "Bas-Rhin, Grand Est": "Strasbourg",
        "Hérault, Occitanie": "Montpellier",
        "Ille-Et-Vilaine, Bretagne": "Rennes",
        "Isère, Auvergne-Rhône-Alpes": "Grenoble",
        "Alpes-Maritimes, Provence-Alpes-Côte D'Azur": "Nice",
    }
    s = s.replace(direct)

    # Arrondissements parisiens → Paris
    s = s.apply(lambda x: "Paris" if _re.match(
        r"^\d+(Er|Ème|E)\s+Arrondissement,?\s*Paris", str(x)) else x)

    # "Ville, Région/Département" → garder la ville principale
    s = s.apply(lambda x: str(x).split(",")[0].strip() if "," in str(x) else x)

    return s


def normalize_dataframe(df: pd.DataFrame, source: str) -> pd.DataFrame:
    """Normalise un DataFrame source vers le schéma cible."""
    if df.empty:
        return df

    col_map = {"adzuna": ADZUNA_COL_MAP, "wtj": WTJ_COL_MAP, "lesjeudis": LESJEUDIS_COL_MAP}[source]
    df = normalize_columns(df, col_map, source)
    n_start = len(df)

    # --- Dates ---
    if "published_at" in df.columns:
        df["published_at"] = normalize_date(df["published_at"])

    if "_fetched_at" in df.columns:
        df["collected_at"] = normalize_date(df["_fetched_at"])
    else:
        df["collected_at"] = pd.Timestamp.now(tz="UTC")

    # --- Salaires Adzuna (déjà numériques) ---
    if source == "adzuna":
        for col in ["salary_min", "salary_max"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        df["currency"] = "EUR"

    # --- Salaires LesJeudis / WTJ (cha\u00eenes \u00e0 parser) ---
    if source in ("wtj", "lesjeudis") and "salary_raw" in df.columns:
        parsed = df["salary_raw"].apply(parse_salary)
        df["salary_min"] = parsed.apply(lambda x: x[0])
        df["salary_max"] = parsed.apply(lambda x: x[1])
        df["currency"] = parsed.apply(lambda x: x[2])
        df.drop(columns=["salary_raw"], inplace=True, errors="ignore")

    # Salaire moyen
    if "salary_min" in df.columns and "salary_max" in df.columns:
        df["salary_avg"] = (
            df[["salary_min", "salary_max"]]
            .mean(axis=1)
            .where(lambda x: (x > 1000) & (x < 500000))
        )

    # --- Contrats ---
    if "contract_type" in df.columns:
        df["contract_type"] = normalize_contract(df["contract_type"])

    # Inférer Stage/Alternance depuis titre/description
    if "contract_type" in df.columns and "title" in df.columns:
        df = infer_contract_from_text(df)

    # --- Villes ---
    if "city" in df.columns:
        df["city"] = normalize_city(df["city"])

    logger.info("[%s] Normalisation : %d lignes traitees", source.upper(), n_start)
    return df


# ═══════════════════════════════════════════════════════════
# ÉTAPE 3 : Dédoublonnage intelligent
# ═══════════════════════════════════════════════════════════

def deduplicate(df: pd.DataFrame) -> pd.DataFrame:
    """Dédoublonne par clé composite (company + title + city) normalisée."""
    n_before = len(df)

    # Convertir les colonnes contenant des listes en chaînes (unhashable)
    for col in df.columns:
        if df[col].apply(lambda x: isinstance(x, (list, dict))).any():
            df[col] = df[col].apply(
                lambda x: str(x) if isinstance(x, (list, dict)) else x
            )

    # Doublons exacts
    df.drop_duplicates(inplace=True)
    n_after_exact = len(df)

    # Clés normalisées
    for col in ["title", "company", "city"]:
        if col in df.columns:
            df[f"_key_{col}"] = df[col].astype(str).str.lower().str.strip()

    key_cols = [c for c in df.columns if c.startswith("_key_")]

    if key_cols:
        # Garder l'offre avec le moins de NaN
        df["_nan_count"] = df.isnull().sum(axis=1)
        df.sort_values("_nan_count", inplace=True)
        df.drop_duplicates(subset=key_cols, keep="first", inplace=True)
        df.drop(columns=key_cols + ["_nan_count"], inplace=True)

    df.reset_index(drop=True, inplace=True)
    n_after = len(df)

    logger.info(
        "[DEDUP] %d -> %d offres (-%d exacts, -%d quasi-doublons)",
        n_before, n_after,
        n_before - n_after_exact,
        n_after_exact - n_after,
    )
    return df


# ═══════════════════════════════════════════════════════════
# ÉTAPE 4 : Enrichissement (tech_stack)
# ═══════════════════════════════════════════════════════════

def extract_tech_stack(description: str) -> str:
    """Extrait les technologies mentionnées, retourne une chaîne séparée par des virgules."""
    if not isinstance(description, str) or not description:
        return ""
    found = [skill for skill, pattern in _SKILL_PATTERNS.items() if pattern.search(description)]
    return ", ".join(found)


def enrich(df: pd.DataFrame) -> pd.DataFrame:
    """Enrichit le DataFrame avec tech_stack."""
    if "description" in df.columns:
        df["tech_stack"] = df["description"].apply(extract_tech_stack)
        n_with_tech = (df["tech_stack"] != "").sum()
        logger.info(
            "[ENRICH] tech_stack extraite pour %d/%d offres (%.1f%%)",
            n_with_tech, len(df), n_with_tech / max(len(df), 1) * 100,
        )
    else:
        df["tech_stack"] = ""
    return df


# ═══════════════════════════════════════════════════════════
# ÉTAPE 5 : Optimisation des types SQL
# ═══════════════════════════════════════════════════════════

def optimize_types(df: pd.DataFrame) -> pd.DataFrame:
    """Convertit les types pour compatibilité SQL optimale."""
    type_map = {
        "title": "string",
        "company": "string",
        "city": "string",
        "contract_type": "string",
        "description": "string",
        "category": "string",
        "url": "string",
        "source": "string",
        "tech_stack": "string",
        "currency": "string",
    }
    for col, dtype in type_map.items():
        if col in df.columns:
            df[col] = df[col].astype(dtype)

    for col in ["salary_min", "salary_max", "salary_avg"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Float64")

    for col in ["published_at", "collected_at"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce", utc=True)

    # Sélectionner et ordonner les colonnes cibles
    available = [c for c in TARGET_COLUMNS if c in df.columns]
    df = df[available]

    logger.info("[TYPES] Colonnes finales : %s", list(df.columns))
    return df


# ═══════════════════════════════════════════════════════════
# ÉTAPE 6 : Export
# ═══════════════════════════════════════════════════════════

def export_csv(df: pd.DataFrame) -> str:
    """Exporte le DataFrame en CSV local."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, OUTPUT_FILE)
    df.to_csv(path, index=False, encoding="utf-8")
    logger.info("[CSV] %d lignes exportees -> %s", len(df), path)
    return path


def export_sql(df: pd.DataFrame) -> None:
    """Insère le DataFrame dans PostgreSQL via psycopg2 COPY (rapide et fiable)."""
    import psycopg2

    try:
        conn = psycopg2.connect(
            host=DB_HOST, port=int(DB_PORT),
            dbname=DB_NAME, user=DB_USER, password=DB_PASS,
        )
        cur = conn.cursor()
        cur.execute(f"DROP TABLE IF EXISTS {SQL_TABLE}")
        col_defs = ", ".join(f'"{c}" TEXT' for c in df.columns)
        cur.execute(f"CREATE TABLE {SQL_TABLE} ({col_defs})")
        buf = io.StringIO()
        df.to_csv(buf, index=False, header=False)
        buf.seek(0)
        columns = ", ".join(f'"{c}"' for c in df.columns)
        cur.copy_expert(f"COPY {SQL_TABLE} ({columns}) FROM STDIN WITH CSV", buf)
        conn.commit()
        cur.execute(f"SELECT COUNT(*) FROM {SQL_TABLE}")
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        logger.info("[SQL] %d lignes inserees dans '%s'", count, SQL_TABLE)
    except Exception as e:
        logger.error("[SQL] Echec insertion : %s", e)
        logger.info("[SQL] Les donnees restent disponibles dans le CSV")


# ═══════════════════════════════════════════════════════════
# PIPELINE PRINCIPAL
# ═══════════════════════════════════════════════════════════

def run():
    """Execute le pipeline ETL complet."""
    start = time.monotonic()
    logger.info("=" * 60)
    logger.info("ETL Transform - Demarrage")
    logger.info("=" * 60)

    # 1. Connexion S3
    s3 = create_s3_client()

    # 2. Chargement multi-sources
    df_adzuna = load_adzuna(s3)
    df_wtj = load_wtj(s3)
    df_lesjeudis = load_lesjeudis(s3)

    # 3. Normalisation
    df_adzuna = normalize_dataframe(df_adzuna, "adzuna")
    df_wtj = normalize_dataframe(df_wtj, "wtj")
    df_lesjeudis = normalize_dataframe(df_lesjeudis, "lesjeudis")

    # 4. Concat\u00e9nation
    frames = [f for f in [df_adzuna, df_wtj, df_lesjeudis] if not f.empty]
    if not frames:
        logger.error("Aucune donnee chargee. Arret du pipeline.")
        sys.exit(1)

    df = pd.concat(frames, ignore_index=True)
    logger.info("[CONCAT] %d offres au total", len(df))

    # 5. Dédoublonnage
    df = deduplicate(df)

    # 6. Enrichissement
    df = enrich(df)

    # 7. Optimisation des types
    df = optimize_types(df)

    # 8. Export
    csv_path = export_csv(df)
    export_sql(df)

    elapsed = time.monotonic() - start
    logger.info("=" * 60)
    logger.info(
        "ETL termine : %d offres propres en %.1fs -> %s + table '%s'",
        len(df), elapsed, csv_path, SQL_TABLE,
    )
    logger.info("=" * 60)

    return df


def main():
    run()


if __name__ == "__main__":
    main()
