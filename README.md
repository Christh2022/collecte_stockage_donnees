# DPIA — Data Pipeline & Intelligence Analytique

**Plateforme complète de collecte, stockage, transformation et visualisation des offres d'emploi Data Science en France.**

Le projet orchestre un pipeline de données de bout en bout : scraping multi-sources, ingestion temps réel via Kafka, stockage objet MinIO, ETL avec export PostgreSQL, et un dashboard interactif Dash/Plotly — le tout orchestré par Apache Airflow et déployé automatiquement sur EC2 via GitLab CI/CD.

---

## Architecture

```
                         +==============+
                         |  Airflow DAG |  (schedule : 8h UTC)
                         +======+========+
                    +-----------+-----------+
                    v           v           v
            +----------+ +-----------+ +------------+
            | Adzuna   | | LesJeudis | | Kafka--S3  |
            | API--Kafka| | Scraper   | | Consumer   |
            +----+-----+ +-----+-----+ +-----+------+
                 |              |              |
                 v              v              v
            +-------------------------------------+
            |           MinIO (S3 local)          |
            |     raw/adzuna/    raw/lesjeudis/    |
            +----------------+--------------------+
                             v
                      +----------------+
                      |  ETL Transform |
                      |  (pandas +     |
                      |   psycopg2)    |
                      +---+--------+---+
                          v        v
                   +----------+  +--------------+
                   |   CSV    |  |  PostgreSQL  |
                   |  export  |  |  (dpia_db)   |
                   +----------+  +------+-------+
                                        v
                               +----------------+
                               |   Dashboard    |
                               |  Dash + Plotly |
                               |   port 8050    |
                               +----------------+
```

### Services Docker (10 containers)

| Service           | Image / Build                         | Port      | Rôle                                  |
| ----------------- | ------------------------------------- | --------- | ------------------------------------- |
| PostgreSQL        | `postgres:16-alpine`                  | 5432      | Métadonnées Airflow + base `dpia_db`  |
| Airflow Webserver | `apache/airflow:2.9.3-python3.11`     | 8080      | Interface Airflow (admin/admin)       |
| Airflow Scheduler | `apache/airflow:2.9.3-python3.11`     | —         | Orchestration DAG pipeline            |
| Kafka             | `confluentinc/cp-kafka:7.7.0` (KRaft) | 9092      | Ingestion temps réel (sans Zookeeper) |
| MinIO             | `minio/minio`                         | 9000/9001 | Stockage objet S3 local               |
| Dashboard         | Build custom (Dash)                   | 8050      | Visualisation interactive             |
| Prometheus        | `prom/prometheus:v2.54.0`             | 9090      | Collecte de métriques                 |
| Grafana           | `grafana/grafana:11.2.0`              | 3000      | Dashboards monitoring (admin/admin)   |
| Loki              | `grafana/loki:2.9.7`                  | 3100      | Agrégation de logs                    |
| Promtail          | `grafana/promtail:2.9.7`              | ---         | Collecte logs Docker vers Loki           |

---

## Pipeline de données

### 1. Scraping (2 sources)

- **Adzuna API** (`src/scraping/api_producer.py`) : interroge l'API Adzuna, envoie chaque offre en JSON dans le topic Kafka `job_api_raw`. Retry avec backoff exponentiel.
- **LesJeudis** (`src/scraping/lesjeudis_scraper.py`) : scrape lesjeudis.com avec requests + BeautifulSoup, téléverse en JSONL directement dans MinIO.

### 2. Ingestion Kafka vers S3

- **Consumer** (`src/storage/kafka_to_s3_consumer.py`) : lit le topic Kafka par batchs de 50 messages (ou timeout 60s), écrit en JSONL partitionné par date dans MinIO (`raw/adzuna/YYYY/MM/DD/`).

### 3. ETL Transform

- **ETL** (`src/transform/etl_transform.py`) : charge les fichiers bruts depuis MinIO, normalise les colonnes/dates/salaires, dédoublonne (entreprise + titre + ville), enrichit (source, tech_stack via regex), exporte en CSV + insertion PostgreSQL via `psycopg2` COPY.

### 4. Orchestration Airflow

Le DAG `dpia_pipeline` (`src/dags/dpia_pipeline.py`) enchaîne automatiquement les 4 tâches chaque jour à 8h UTC :

```
scrape_adzuna --> kafka_to_s3 --> etl_transform
scrape_lesjeudis -----------------/
```

---

## Dashboard

Dashboard interactif multi-pages accessible sur le port **8050** :

| Page               | Contenu                                                              |
| ------------------ | -------------------------------------------------------------------- |
| **Vue d'ensemble** | KPIs globaux, répartition par contrat, top entreprises               |
| **Compétences**    | Power trio (Python+SQL+Cloud), GenAI vs Trad, heatmap skills/contrat |
| **Salaires**       | Distribution salariale, boxplot par contrat, scatter exp/salaire     |
| **Géographie**     | Carte de France, top villes, répartition par région                  |
| **Temporel**       | Évolution des publications, saisonnalité                             |
| **Qualité**        | Taux de complétion des champs, doublons, couverture                  |

Technologies : Dash, Plotly, Bokeh, Dash Bootstrap Components (thème LUX).

---

## Monitoring

- **Prometheus** : collecte les métriques CPU/RAM/disque (Node Exporter) et métriques Docker par conteneur (Docker Exporter custom).
- **Loki + Promtail** : agrégation et collecte des logs de tous les containers Docker. Les logs PostgreSQL (connexions, erreurs, requêtes lentes > 500ms) sont visibles dans Grafana.
- **Grafana** : 2 dashboards pré-provisionnés — monitoring infra (métriques) + logs (PostgreSQL, Airflow, Kafka). Alertes CPU > 90%, RAM > 85%, disque > 80%.
- **Alertes Prometheus** : règles configurées dans `infra/prometheus/alert_rules.yml`.
- **Logging** : module `src/monitoring/logger.py` — console en dev, CloudWatch en prod.

---

## CI/CD

Pipeline GitLab en 4 stages (`.gitlab-ci.yml`) :

```
lint -- build -- test -- deploy
```

| Stage      | Détail                                                      |
| ---------- | ----------------------------------------------------------- |
| **lint**   | `flake8` sur `src/` (max-line-length 120)                   |
| **build**  | Build + push image Docker dans GitLab Container Registry    |
| **test**   | Tests unitaires + intégration avec `pytest` + couverture    |
| **deploy** | Déploiement auto sur EC2 via GitLab Runner (shell executor) |

Le stage deploy :

1. Génère le `.env` depuis les variables CI/CD GitLab
2. Lance `docker compose up -d --force-recreate`
3. Attend PostgreSQL + Airflow
4. Déclenche le DAG pipeline
5. Relance l'ETL + vérifie PostgreSQL + redémarre le dashboard

---

## Arborescence

```
+-- infra/
|   +-- docker-compose.yml          # 8 services Docker
|   +-- prometheus/
|   |   +-- prometheus.yml          # Config scrape
|   |   +-- alert_rules.yml         # Alertes CPU/RAM/disque
|   +-- grafana/provisioning/       # Datasources (Prometheus+Loki) + dashboards JSON
|   +-- promtail/
|   |   +-- promtail-config.yml     # Collecte logs Docker vers Loki
|   +-- docker-exporter/            # Exporter metriques Docker custom
|   +-- postgres/init-dpia-db.sh    # Init base dpia_db
+-- src/
|   +-- main.py
|   +-- dags/
|   |   +-- dpia_pipeline.py        # DAG Airflow (4 taches)
|   +-- scraping/
|   |   +-- api_producer.py         # Adzuna API vers Kafka
|   |   +-- lesjeudis_scraper.py    # LesJeudis vers MinIO
|   +-- storage/
|   |   +-- kafka_to_s3_consumer.py # Kafka vers MinIO (batchs JSONL)
|   +-- transform/
|   |   +-- etl_transform.py        # S3 vers CSV + PostgreSQL
|   +-- monitoring/
|   |   +-- logger.py               # Logger console/CloudWatch
|   +-- visualization/
|       +-- app.py                   # Point d'entree Dash
|       +-- config.py                # Palettes, mots-cles, seuils
|       +-- data.py                  # Chargement donnees
|       +-- sidebar.py               # Navigation sidebar
|       +-- components.py            # Composants reutilisables
|       +-- pages/                   # 6 pages dashboard
+-- tests/
|   +-- test_unit_etl.py
|   +-- test_unit_scraping.py
|   +-- test_unit_data.py
|   +-- test_integration.py
|   +-- test_smoke.py
+-- data/clean/                      # CSV nettoye (sortie ETL)
+-- notebooks/
|   +-- eda_job_market.ipynb         # Analyse exploratoire
+-- Dockerfile                       # Image pipeline Python 3.11
+-- Dockerfile.dashboard             # Image dashboard Dash
+-- requirements.txt                 # Dependances pipeline
+-- requirements-dashboard.txt       # Dependances dashboard
+-- .gitlab-ci.yml                   # Pipeline CI/CD 4 stages
+-- DEPLOY_EC2.md                    # Guide deploiement EC2
```

---

## Démarrage rapide (local)

```bash
# 1. Cloner le projet
git clone https://gitlab.com/Christh2022/collecte_stockage_donnees.git
cd collecte_stockage_donnees

# 2. Créer le fichier .env
cp .env.example .env
# Renseigner ADZUNA_APP_ID et ADZUNA_API_KEY

# 3. Lancer l'infrastructure
cd infra
docker compose up -d

# 4. Accéder aux services
#    Airflow  : http://localhost:8080  (admin/admin)
#    Dashboard: http://localhost:8050
#    MinIO    : http://localhost:9001  (minioadmin/minioadmin)
#    Grafana  : http://localhost:3000  (admin/admin)
#    Prometheus: http://localhost:9090
```

Le DAG Airflow `dpia_pipeline` est activé par défaut et s'exécute tous les jours à 8h UTC. Pour un lancement immédiat :

```bash
docker exec dpia-airflow-scheduler airflow dags trigger dpia_pipeline
```

---

## Tests

```bash
pip install -r requirements.txt -r requirements-dashboard.txt pytest pytest-cov

# Tests unitaires + smoke
pytest tests/test_unit_*.py tests/test_smoke.py -v --cov=src

# Tests d'intégration
pytest tests/test_integration.py -v
```

---

## Déploiement EC2

Voir [DEPLOY_EC2.md](DEPLOY_EC2.md) pour le guide complet de déploiement sur AWS EC2 avec GitLab Runner.

---

## Stack technique

| Catégorie        | Technologies                                       |
| ---------------- | -------------------------------------------------- |
| Orchestration    | Apache Airflow 2.9.3                               |
| Scraping         | Requests, BeautifulSoup, Selenium                  |
| Streaming        | Apache Kafka (KRaft, sans Zookeeper)               |
| Stockage objet   | MinIO (compatible S3)                              |
| Base de données  | PostgreSQL 16                                      |
| ETL              | Pandas, psycopg2 (COPY)                            |
| Visualisation    | Dash, Plotly, Bokeh, Dash Bootstrap Components     |
| Monitoring       | Prometheus, Grafana, Loki, Promtail, Node Exporter |
| CI/CD            | GitLab CI/CD, GitLab Runner (shell executor)       |
| Conteneurisation | Docker, Docker Compose                             |
| Langage          | Python 3.11                                        |
