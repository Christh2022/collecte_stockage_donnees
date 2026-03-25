"""
Producer API Adzuna → Kafka.

Interroge l'API Adzuna pour récupérer les offres d'emploi Data Science
et envoie chaque offre en JSON dans le topic Kafka `job_offers_raw`.

Usage:
    python -m src.scraping.api_producer

Variables d'environnement requises:
    ADZUNA_APP_ID, ADZUNA_API_KEY, KAFKA_BOOTSTRAP_SERVERS
"""

import json
import os
import sys
import time

import requests
from kafka import KafkaProducer
from kafka.errors import NoBrokersAvailable
from dotenv import load_dotenv

load_dotenv()

# ── Configuration ──────────────────────────────────────────
ADZUNA_APP_ID = os.getenv("ADZUNA_APP_ID")
ADZUNA_API_KEY = os.getenv("ADZUNA_API_KEY")
ADZUNA_BASE_URL = "https://api.adzuna.com/v1/api/jobs"
ADZUNA_COUNTRY = os.getenv("ADZUNA_COUNTRY", "fr")

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC_RAW", "job_offers_raw")

SEARCH_QUERY = os.getenv("ADZUNA_SEARCH_QUERY", "data science")
MAX_PAGES = int(os.getenv("ADZUNA_MAX_PAGES", "5"))
RESULTS_PER_PAGE = 50


def create_producer(retries: int = 5, delay: int = 5) -> KafkaProducer:
    """Crée un producer Kafka avec retry en cas d'indisponibilité du broker."""
    for attempt in range(1, retries + 1):
        try:
            producer = KafkaProducer(
                bootstrap_servers=KAFKA_BOOTSTRAP,
                value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode("utf-8"),
                acks="all",
                retries=3,
            )
            print(f"[OK] Connecté à Kafka ({KAFKA_BOOTSTRAP})")
            return producer
        except NoBrokersAvailable:
            print(f"[RETRY {attempt}/{retries}] Kafka indisponible, attente {delay}s...")
            time.sleep(delay)
    print("[ERREUR] Impossible de se connecter à Kafka.")
    sys.exit(1)


def fetch_adzuna_jobs(page: int = 1) -> list[dict]:
    """Récupère une page de résultats depuis l'API Adzuna."""
    url = f"{ADZUNA_BASE_URL}/{ADZUNA_COUNTRY}/search/{page}"
    params = {
        "app_id": ADZUNA_APP_ID,
        "app_key": ADZUNA_API_KEY,
        "results_per_page": RESULTS_PER_PAGE,
        "what": SEARCH_QUERY,
        "content-type": "application/json",
    }

    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()

    data = response.json()
    return data.get("results", [])


def enrich_offer(offer: dict, page: int) -> dict:
    """Ajoute des métadonnées au message avant l'envoi dans Kafka."""
    return {
        "source": "adzuna",
        "country": ADZUNA_COUNTRY,
        "search_query": SEARCH_QUERY,
        "page": page,
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "data": offer,
    }


def main():
    if not ADZUNA_APP_ID or not ADZUNA_API_KEY:
        print("[ERREUR] ADZUNA_APP_ID et ADZUNA_API_KEY requis dans .env")
        sys.exit(1)

    producer = create_producer()
    total_sent = 0

    for page in range(1, MAX_PAGES + 1):
        print(f"[API] Récupération page {page}/{MAX_PAGES}...")

        try:
            offers = fetch_adzuna_jobs(page)
        except requests.exceptions.RequestException as e:
            print(f"[ERREUR] API Adzuna page {page}: {e}")
            continue

        if not offers:
            print(f"[INFO] Page {page} vide, arrêt de la pagination.")
            break

        for offer in offers:
            message = enrich_offer(offer, page)
            producer.send(KAFKA_TOPIC, value=message)
            total_sent += 1

        print(f"[OK] {len(offers)} offres envoyées dans '{KAFKA_TOPIC}'")
        time.sleep(1)  # Rate limiting

    producer.flush()
    producer.close()
    print(f"\n[TERMINÉ] {total_sent} offres envoyées au total dans Kafka.")


if __name__ == "__main__":
    main()
