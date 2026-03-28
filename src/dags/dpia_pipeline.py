"""
DAG DPIA — Pipeline complet : Scraping → Stockage → ETL.

Planifié tous les jours à 8h UTC.
  1. Scraping Adzuna API (→ Kafka)
  2. Scraping LesJeudis (→ MinIO/S3)
  3. Consommation Kafka → S3  (en parallèle, attend Adzuna)
  4. ETL Transform (nettoyage + insertion PostgreSQL)
"""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

default_args = {
    "owner": "dpia",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="dpia_pipeline",
    default_args=default_args,
    description="Pipeline quotidien : Scraping → S3 → ETL → PostgreSQL",
    schedule_interval="0 8 * * *",
    start_date=datetime(2026, 3, 1),
    catchup=False,
    max_active_runs=1,
    is_paused_upon_creation=False,
    tags=["dpia", "scraping", "etl"],
) as dag:

    # ── 1. Scraping Adzuna API → Kafka ────────────────────
    scrape_adzuna = BashOperator(
        task_id="scrape_adzuna",
        bash_command="cd /opt/airflow && python -m src.scraping.api_producer",
        execution_timeout=timedelta(minutes=15),
    )

    # ── 2. Scraping LesJeudis → MinIO/S3 ─────────────────
    scrape_lesjeudis = BashOperator(
        task_id="scrape_lesjeudis",
        bash_command="cd /opt/airflow && python -m src.scraping.lesjeudis_scraper",
        execution_timeout=timedelta(minutes=15),
    )

    # ── 3. Kafka Consumer → S3 ────────────────────────────
    kafka_to_s3 = BashOperator(
        task_id="kafka_to_s3",
        bash_command="cd /opt/airflow && timeout 120 python -m src.storage.kafka_to_s3_consumer || true",
        execution_timeout=timedelta(minutes=5),
    )

    # ── 4. ETL Transform → PostgreSQL ─────────────────────
    etl_transform = BashOperator(
        task_id="etl_transform",
        bash_command="cd /opt/airflow && python -m src.transform.etl_transform",
        execution_timeout=timedelta(minutes=10),
    )

    # ── Dépendances ───────────────────────────────────────
    # 1. Les deux scrapers tournent en parallèle
    # 2. Kafka consumer attend qu'Adzuna ait fini d'écrire dans Kafka
    # 3. ETL attend que TOUT le stockage MinIO/S3 soit terminé
    #
    #  scrape_adzuna ──→ kafka_to_s3 ──┐
    #                                   ├──→ etl_transform
    #  scrape_lesjeudis ───────────────┘
    scrape_adzuna >> kafka_to_s3 >> etl_transform
    scrape_lesjeudis >> etl_transform
