"""
Scraper LesJeudis.com → MinIO/S3.

Scrape les offres d'emploi Data/IT depuis lesjeudis.com
et téléverse les résultats directement dans MinIO/S3 en JSONL.

Utilise requests + BeautifulSoup (pas de JS côté listing).
Pagination automatique avec arrêt configurable.

Usage:
    python -m src.scraping.lesjeudis_scraper

Variables d'environnement optionnelles:
    LESJEUDIS_SEARCH_QUERY, LESJEUDIS_MAX_PAGES,
    MINIO_ENDPOINT, S3_BUCKET_NAME
"""

import io
import json
import os
import re
import time
from datetime import datetime, timezone

import boto3
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

# ── Configuration ──────────────────────────────────────────
BASE_URL = "https://lesjeudis.com"
SEARCH_URL = f"{BASE_URL}/jobs"

SEARCH_QUERY = os.getenv("LESJEUDIS_SEARCH_QUERY", "data science")
MAX_PAGES = int(os.getenv("LESJEUDIS_MAX_PAGES", "5"))
REQUEST_DELAY = float(os.getenv("LESJEUDIS_REQUEST_DELAY", "2"))

S3_BUCKET = os.getenv("S3_BUCKET_NAME", "dpia-data-bucket")
S3_PREFIX = os.getenv("S3_PREFIX_LESJEUDIS", "raw/lesjeudis")
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT")

MAX_RETRIES = 3

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.5",
}


def create_s3_client():
    """Crée un client S3 : MinIO en dev, AWS S3 en prod."""
    kwargs = {}
    if MINIO_ENDPOINT:
        kwargs.update(
            endpoint_url=MINIO_ENDPOINT,
            aws_access_key_id=os.getenv("MINIO_ROOT_USER", "minioadmin"),
            aws_secret_access_key=os.getenv("MINIO_ROOT_PASSWORD", "minioadmin"),
        )
        print(f"[S3] Mode MinIO → {MINIO_ENDPOINT}")
    else:
        print("[S3] Mode AWS S3")
    return boto3.client("s3", **kwargs)


def upload_to_s3(s3_client, records: list[dict]) -> str:
    """Téléverse une liste de records en JSONL vers S3/MinIO."""
    now = datetime.now(timezone.utc)
    date_partition = now.strftime("%Y/%m/%d")
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    key = f"{S3_PREFIX}/{date_partition}/{timestamp}_lesjeudis.jsonl"

    content = "\n".join(json.dumps(r, ensure_ascii=False) for r in records)
    body = io.BytesIO(content.encode("utf-8"))

    s3_client.upload_fileobj(body, S3_BUCKET, key)
    print(f"[UPLOAD] {len(records)} records → s3://{S3_BUCKET}/{key}")
    return key


def fetch_page(url: str, params: dict | None = None) -> BeautifulSoup | None:
    """Télécharge une page avec retry et retourne un objet BeautifulSoup."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(url, params=params, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            return BeautifulSoup(resp.text, "lxml")
        except requests.exceptions.RequestException as e:
            delay = 2 ** attempt
            print(f"[RETRY {attempt}/{MAX_RETRIES}] {e} — attente {delay}s...")
            time.sleep(delay)
    print(f"[ERREUR] Impossible de charger {url}")
    return None


def extract_listing_urls(soup: BeautifulSoup) -> list[str]:
    """Extrait les URLs des offres depuis une page de résultats."""
    urls = []
    for link in soup.select("a[href*='/fr/job/']"):
        href = link.get("href", "")
        if href and href not in urls:
            full_url = href if href.startswith("http") else BASE_URL + href
            urls.append(full_url)
    return urls


def parse_job_detail(soup: BeautifulSoup, url: str) -> dict:
    """Parse une page de détail d'offre et retourne un dict structuré."""
    title_tag = soup.find("h1")
    title = title_tag.get_text(strip=True) if title_tag else ""

    # Entreprise : lien vers /organization/
    company = ""
    company_link = soup.select_one("a[href*='/organization/']")
    if company_link:
        company = company_link.get_text(strip=True)

    # Localisation
    location = ""
    loc_el = soup.find("img", attrs={"alt": "location"})
    if loc_el and loc_el.parent:
        location = loc_el.parent.get_text(strip=True)
    if not location:
        # fallback: chercher texte contenant "France"
        for el in soup.find_all(string=re.compile(r"\d{5}.*France")):
            location = el.strip()
            break

    # Télétravail
    remote = ""
    remote_el = soup.find("img", attrs={"alt": "remote"})
    if remote_el and remote_el.parent:
        remote = remote_el.parent.get_text(strip=True)

    # Type de contrat (CDI, CDD, etc.)
    contract_type = ""
    for text_node in soup.find_all(string=re.compile(r"\b(CDI|CDD|Freelance|Stage|Alternance|Intérim)\b", re.I)):
        parent = text_node.parent
        if parent and parent.name in ("span", "div", "li", "p", "a"):
            contract_type = text_node.strip()
            break

    # Salaire
    salary = ""
    salary_match = soup.find(string=re.compile(r"\d+\s*[kK€]"))
    if salary_match:
        salary = salary_match.strip()

    # Description complète (texte principal)
    description = ""
    # Le contenu principal est souvent après les métadonnées
    body_parts = []
    for p in soup.find_all(["p", "li"]):
        text = p.get_text(strip=True)
        if len(text) > 30 and "cookie" not in text.lower():
            body_parts.append(text)
    description = "\n".join(body_parts[:50])  # Limiter la taille

    return {
        "title": title,
        "company": company,
        "location": location,
        "remote": remote,
        "contract_type": contract_type,
        "salary": salary,
        "url": url,
        "description": description,
    }


def scrape_listing_page(page: int) -> list[str]:
    """Scrape une page de résultats et retourne les URLs des offres."""
    params = {"query": SEARCH_QUERY, "page": page}
    print(f"[LISTING] Page {page}/{MAX_PAGES} — query='{SEARCH_QUERY}'")

    soup = fetch_page(SEARCH_URL, params=params)
    if not soup:
        return []

    urls = extract_listing_urls(soup)
    print(f"  → {len(urls)} offres trouvées")
    return urls


def scrape_job(url: str) -> dict | None:
    """Scrape une offre individuelle."""
    soup = fetch_page(url)
    if not soup:
        return None
    return parse_job_detail(soup, url)


def enrich_offer(offer: dict, page: int) -> dict:
    """Ajoute des métadonnées au message avant envoi dans Kafka."""
    return {
        "source": "lesjeudis",
        "search_query": SEARCH_QUERY,
        "page": page,
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "data": offer,
    }


def main():
    s3_client = create_s3_client()
    all_records = []

    for page in range(1, MAX_PAGES + 1):
        job_urls = scrape_listing_page(page)

        if not job_urls:
            print(f"[INFO] Page {page} vide, arrêt de la pagination.")
            break

        for url in job_urls:
            job = scrape_job(url)
            if job:
                message = enrich_offer(job, page)
                all_records.append(message)
                print(f"  [OK] {job['title'][:60]}")
            time.sleep(REQUEST_DELAY)

        print(f"[PAGE {page}] {len(job_urls)} offres traitées")
        time.sleep(REQUEST_DELAY)

    if all_records:
        upload_to_s3(s3_client, all_records)

    print(f"\n[TERMINÉ] {len(all_records)} offres LesJeudis uploadées dans MinIO/S3.")


if __name__ == "__main__":
    main()
