"""
Configuration — constantes, palettes, coordonnées, mots-clés.
"""

import os
import re

from dotenv import load_dotenv

load_dotenv()

# ── Base de données ────────────────────────────────────────
DB_HOST = os.getenv("RDS_HOST", "postgres") or "postgres"
DB_PORT = os.getenv("RDS_PORT", "5432") or "5432"
DB_NAME = os.getenv("RDS_DB_NAME", "dpia_db") or "dpia_db"
DB_USER = os.getenv("RDS_USERNAME", "airflow") or "airflow"
DB_PASS = os.getenv("RDS_PASSWORD", "airflow") or "airflow"
SQL_TABLE = os.getenv("ETL_SQL_TABLE", "offres_emploi_clean")

# ── Coordonnées des villes ─────────────────────────────────
CITY_COORDS = {
    "Paris": (48.8566, 2.3522),
    "Lyon": (45.7640, 4.8357),
    "Marseille": (43.2965, 5.3698),
    "Toulouse": (43.6047, 1.4442),
    "Bordeaux": (44.8378, -0.5792),
    "Nantes": (47.2184, -1.5536),
    "Lille": (50.6292, 3.0573),
    "Strasbourg": (48.5734, 7.7521),
    "Montpellier": (43.6108, 3.8767),
    "Nice": (43.7102, 7.2620),
    "Rennes": (48.1173, -1.6778),
    "Grenoble": (45.1885, 5.7245),
    "Aix-En-Provence": (43.5297, 5.4474),
    "Rouen": (49.4432, 1.0993),
    "Nanterre": (48.8924, 2.2071),
    "Boulogne-Billancourt": (48.8397, 2.2399),
    "La Defense": (48.8918, 2.2382),
    "Levallois-Perret": (48.8938, 2.2882),
    "Issy-Les-Moulineaux": (48.8244, 2.2700),
    "Clermont-Ferrand": (45.7772, 3.0870),
    "Angers": (47.4784, -0.5632),
    "Tours": (47.3941, 0.6848),
    "Dijon": (47.3220, 5.0415),
    "Saint-Etienne": (45.4397, 4.3872),
    "Metz": (49.1193, 6.1757),
    "Nancy": (48.6921, 6.1844),
    "Sophia-Antipolis": (43.6163, 7.0553),
    "Suresnes": (48.8694, 2.2291),
}

# ── Palette cohérente (bleu pétrole / gris anthracite) ────
PALETTE = {
    "primary": "#1B4965",
    "primary_light": "#5FA8D3",
    "secondary": "#62B6CB",
    "accent": "#BEE9E8",
    "success": "#2D936C",
    "warning": "#F4A261",
    "danger": "#E76F51",
    "dark": "#2B2D42",
    "muted": "#8D99AE",
    "light_bg": "#F8F9FA",
    "white": "#FFFFFF",
}

PLOT_COLORS = ["#1B4965", "#5FA8D3", "#62B6CB", "#2D936C",
               "#F4A261", "#E76F51", "#264653", "#E9C46A"]

SKELETON_DELAY = float(os.getenv("SKELETON_DELAY", "0"))

# ── Sidebar palette ───────────────────────────────────────
SB = {
    "bg":       "#111827",
    "surface":  "#1F2937",
    "border":   "#374151",
    "text":     "#D1D5DB",
    "text_dim": "#6B7280",
    "white":    "#F9FAFB",
    "accent":   "#3B82F6",
}

# ── Mots-clés d'analyse ───────────────────────────────────
CLOUD_KEYWORDS = ["aws", "azure", "gcp", "google cloud"]

GENAI_KEYWORDS = ["llm", "langchain", "rag", "gpt", "openai", "chatgpt",
                  "generative ai", "ia générative", "prompt engineering",
                  "transformer", "hugging face", "huggingface", "fine-tuning",
                  "vector database", "embedding"]

TRADITIONAL_KEYWORDS = ["hadoop", "spark", "pyspark", "hive", "mapreduce",
                        "pig", "sqoop", "hdfs", "oozie", "presto"]

SOFT_SKILLS = ["gestion de projet", "management", "agilité", "agile", "scrum",
               "communication", "leadership", "teamwork", "travail d'équipe",
               "présentation", "autonomie", "rigueur", "organisation",
               "esprit d'équipe", "reporting", "coordination"]

HARD_SKILLS = ["python", "sql", "r", "scala", "java", "spark", "tensorflow",
               "pytorch", "scikit-learn", "docker", "kubernetes", "airflow",
               "aws", "azure", "gcp", "tableau", "power bi", "git",
               "machine learning", "deep learning", "nlp", "pandas",
               "snowflake", "bigquery", "databricks", "kafka", "dbt"]

REMOTE_PATTERNS = {
    "Full Remote": re.compile(
        r"full\s*remote|100\s*%?\s*remote|télétravail\s*complet|fully\s*remote", re.I),
    "Hybride": re.compile(
        r"hybride|hybrid|télétravail\s*partiel|remote\s*partiel|\d+\s*j(?:ours?)?\s*/?\s*semaine", re.I),
    "Présentiel": re.compile(
        r"présentiel|sur\s*site|on[\s-]?site|pas\s*de\s*télétravail|no\s*remote", re.I),
}

CITY_POPULATION = {
    "Paris": 2_161_000, "Lyon": 522_969, "Marseille": 873_076,
    "Toulouse": 498_003, "Bordeaux": 260_958, "Nantes": 320_732,
    "Lille": 236_234, "Strasbourg": 287_228, "Montpellier": 299_096,
    "Nice": 342_669, "Rennes": 222_485, "Grenoble": 158_198,
    "Aix-En-Provence": 147_122, "Rouen": 114_007, "Nanterre": 96_855,
    "Boulogne-Billancourt": 121_334, "La Defense": 20_000,
    "Levallois-Perret": 66_082, "Issy-Les-Moulineaux": 69_056,
    "Clermont-Ferrand": 147_865, "Angers": 157_175, "Tours": 138_588,
    "Dijon": 160_106, "Saint-Etienne": 177_480, "Metz": 120_205,
    "Nancy": 104_885, "Sophia-Antipolis": 10_000, "Suresnes": 49_833,
}
