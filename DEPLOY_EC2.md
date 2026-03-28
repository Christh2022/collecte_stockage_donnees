# Déploiement sur AWS EC2 — Guide complet

## Architecture

```
              GitLab CI/CD (push main)
                      │
                      ▼
              ┌──────────────────┐
              │   EC2 t3.large   │
              │  (Ubuntu 22.04)  │
              └──────┬───────────┘
                     │  docker compose up
                     ▼
  ┌─────────────────────────────────────────────┐
  │  Airflow (scheduler + webserver)            │
  │    DAG: dpia_pipeline (quotidien 8h UTC)    │
  │    ├── scrape_adzuna ──→ kafka_to_s3 ──┐    │
  │    │                                    ├──→ etl_transform → PostgreSQL
  │    └── scrape_lesjeudis ───────────────┘    │
  ├─────────────────────────────────────────────┤
  │  Kafka (KRaft) │ MinIO (S3) │ PostgreSQL    │
  │  Dashboard     │ Grafana    │ Prometheus    │
  └─────────────────────────────────────────────┘
```

**Containers** : postgres, airflow-init, airflow-webserver, airflow-scheduler, kafka, dashboard, node-exporter, docker-exporter, prometheus, grafana.
Le scraping et l'ETL sont orchestrés par le **DAG Airflow** (plus de containers standalone).

## Prérequis

- Un compte AWS avec accès à EC2
- Une paire de clés SSH (.pem) pour se connecter à l'instance
- Un compte GitLab avec le projet `collecte_stockage_donnees`

---

## 1. Créer l'instance EC2

1. Connectez-vous à la **console AWS** → **EC2** → **Lancer une instance**
2. Configuration recommandée :
   - **AMI** : Ubuntu Server 22.04 LTS
   - **Type** : `t3.large` (2 vCPU, 8 Go RAM) — minimum requis pour Airflow + Kafka
   - **Stockage** : 100 Go gp3 (Docker images + volumes Kafka/MinIO)
   - **Paire de clés** : sélectionnez ou créez une clé `.pem`
3. **Groupe de sécurité** — ouvrir les ports entrants :

   | Port | Protocole | Source   | Usage             |
   | ---- | --------- | -------- | ----------------- |
   | 22   | TCP       | Votre IP | SSH               |
   | 8080 | TCP       | Votre IP | Airflow Webserver |
   | 8050 | TCP       | Votre IP | Dashboard Dash    |
   | 9090 | TCP       | Votre IP | Prometheus        |
   | 3000 | TCP       | Votre IP | Grafana           |
   | 9001 | TCP       | Votre IP | MinIO Console     |

4. Lancez l'instance et notez l'**IP publique**

---

## 2. Se connecter à l'instance

```bash
ssh -i "votre-cle.pem" ubuntu@<IP_PUBLIQUE_EC2>
```

---

## 3. Installer Docker

```bash
# Mettre à jour le système
sudo apt-get update && sudo apt-get upgrade -y

# Installer les dépendances
sudo apt-get install -y ca-certificates curl gnupg lsb-release

# Ajouter la clé GPG Docker
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# Ajouter le dépôt Docker
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Installer Docker
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Ajouter l'utilisateur ubuntu au groupe docker
sudo usermod -aG docker ubuntu

# Vérifier l'installation
docker --version
docker compose version
```

> **Déconnectez-vous et reconnectez-vous** pour que le groupe docker soit pris en compte :
>
> ```bash
> exit
> ssh -i "votre-cle.pem" ubuntu@<IP_PUBLIQUE_EC2>
> ```

---

## 4. Installer Git

```bash
sudo apt-get install -y git
git --version
```

---

## 5. Installer GitLab Runner

```bash
# Télécharger le binaire
sudo curl -L --output /usr/local/bin/gitlab-runner \
  https://gitlab-runner-downloads.s3.amazonaws.com/latest/binaries/gitlab-runner-linux-amd64

# Rendre exécutable
sudo chmod +x /usr/local/bin/gitlab-runner

# Créer l'utilisateur gitlab-runner
sudo useradd --comment 'GitLab Runner' --create-home gitlab-runner --shell /bin/bash

# Installer et démarrer le service
sudo gitlab-runner install --user=gitlab-runner --working-directory=/home/gitlab-runner
sudo gitlab-runner start

# Ajouter gitlab-runner au groupe docker
sudo usermod -aG docker gitlab-runner

# Vérifier le statut
sudo gitlab-runner status
```

---

## 6. Enregistrer le Runner sur GitLab

1. Dans GitLab, allez dans **Settings** → **CI/CD** → **Runners** → **New project runner**
2. Cochez **Run untagged jobs** et ajoutez le tag : `ec2-shell`
3. Copiez le **token** affiché
4. Sur l'EC2 :

```bash
sudo gitlab-runner register \
  --non-interactive \
  --url "https://gitlab.com/" \
  --token "VOTRE_RUNNER_TOKEN" \
  --executor "shell" \
  --description "EC2 DPIA Runner" \
  --tag-list "ec2-shell"
```

5. Vérifiez que le runner apparaît **en ligne (vert)** dans GitLab → Settings → CI/CD → Runners

---

## 7. Créer le fichier .env

```bash
sudo bash -c 'cat > /home/gitlab-runner/collecte_stockage_donnees/.env << "EOF"
ENV_MODE=dev
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_DEFAULT_REGION=eu-west-1
S3_BUCKET_NAME=dpia-data-bucket
RDS_HOST=postgres
RDS_PORT=5432
RDS_DB_NAME=dpia_db
RDS_USERNAME=airflow
RDS_PASSWORD=airflow
CLOUDWATCH_LOG_GROUP=/dpia/pipeline
MINIO_ENDPOINT=http://minio:9000
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin
ADZUNA_APP_ID=8c5da6fd
ADZUNA_API_KEY=28d1f034ca7c72e30d62c1c28798e785
ADZUNA_COUNTRY=fr
ADZUNA_SEARCH_QUERY=data science
ADZUNA_MAX_PAGES=5
KAFKA_BOOTSTRAP_SERVERS=kafka:29092
KAFKA_TOPIC_RAW=job_api_raw
KAFKA_GROUP_ID=s3-consumer-group
CONSUMER_BATCH_SIZE=50
CONSUMER_BATCH_TIMEOUT=60
API_MAX_RETRIES=5
API_RETRY_BASE_DELAY=2
S3_PREFIX=raw/adzuna
S3_PREFIX_WTJ=raw/wtj
ETL_OUTPUT_DIR=data/clean
ETL_SQL_TABLE=offres_emploi_clean
EOF'
```

---

## 8. Créer le dossier data

```bash
sudo mkdir -p /home/gitlab-runner/collecte_stockage_donnees/data/clean
sudo chown -R gitlab-runner:gitlab-runner /home/gitlab-runner/collecte_stockage_donnees/.env \
  /home/gitlab-runner/collecte_stockage_donnees/data
```

---

## 9. Configurer les variables CI/CD sur GitLab

Dans **GitLab** → **Settings** → **CI/CD** → **Variables**, ajoutez (si besoin pour la prod) :

| Variable                | Valeur             | Protégé | Masqué |
| ----------------------- | ------------------ | ------- | ------ |
| `AWS_ACCESS_KEY_ID`     | Votre clé AWS      | Oui     | Oui    |
| `AWS_SECRET_ACCESS_KEY` | Votre secret AWS   | Oui     | Oui    |
| `AWS_DEFAULT_REGION`    | `eu-west-1`        | Non     | Non    |
| `S3_BUCKET_NAME`        | `dpia-data-bucket` | Non     | Non    |

---

## 10. Déployer

Le déploiement est **automatique**. Depuis votre machine locale :

```bash
git add .
git commit -m "Déploiement initial sur EC2 via CI/CD"
git push origin main
```

Le pipeline GitLab CI/CD va :

1. **lint** — Vérifier le code avec flake8
2. **build** — Construire l'image Docker et push au registre GitLab
3. **test** — Exécuter les tests unitaires et d'intégration
4. **deploy** — Sur l'EC2 :
   - Génère le `.env` à partir des variables CI/CD
   - `docker compose up -d --force-recreate`
   - Attend PostgreSQL → crée `dpia_db`
   - Attend Airflow healthy (scheduler + webserver)
   - Attend 60s que le scheduler parse les DAGs
   - `airflow dags unpause + trigger dpia_pipeline` (scraping + stockage MinIO)
   - Attend 300s que les tâches Airflow finissent
   - Re-exécute l'ETL pour export PostgreSQL (via psycopg2 COPY)
   - Vérifie le nombre de lignes dans `offres_emploi_clean`
   - Redémarre le dashboard (pour charger les données PostgreSQL)

---

## 11. Vérifier le déploiement

Sur l'EC2 :

```bash
# Vérifier les containers
sudo docker ps --format "table {{.Names}}\t{{.Status}}" | sort

# Vérifier Airflow
curl -s http://localhost:8080/health

# Vérifier les tâches du DAG
sudo docker exec dpia-airflow-scheduler airflow tasks states-for-dag-run dpia_pipeline latest

# Vérifier les données dans PostgreSQL
sudo docker exec dpia-postgres psql -U airflow -d dpia_db -c "SELECT COUNT(*) FROM offres_emploi_clean;"

# Voir les logs Airflow scheduler
sudo docker logs dpia-airflow-scheduler --tail 30
```

Accès via navigateur :

- **Airflow** : `http://<IP_EC2>:8080` (admin / admin)
- **Dashboard** : `http://<IP_EC2>:8050`
- **Grafana** : `http://<IP_EC2>:3000`
- **MinIO** : `http://<IP_EC2>:9001` (minioadmin / minioadmin)
- **Prometheus** : `http://<IP_EC2>:9090`

---

## Dépannage

```bash
# Voir tous les containers (y compris arrêtés)
docker ps -a

# Logs d'un container
docker logs <nom_container> --tail 50

# Logs Airflow scheduler (exécution des tâches)
docker logs dpia-airflow-scheduler --tail 100

# Vérifier l'état du DAG
docker exec dpia-airflow-scheduler airflow dags list
docker exec dpia-airflow-scheduler airflow tasks states-for-dag-run dpia_pipeline latest

# Relancer le DAG manuellement
docker exec dpia-airflow-scheduler airflow dags trigger dpia_pipeline

# Relancer l'ETL manuellement (export PostgreSQL)
docker exec dpia-airflow-scheduler bash -c "cd /opt/airflow && python -m src.transform.etl_transform"

# Vérifier les données PostgreSQL
docker exec dpia-postgres psql -U airflow -d dpia_db -c "SELECT COUNT(*) FROM offres_emploi_clean;"

# Redémarrer le dashboard (recharge les données)
docker restart dpia-dashboard

# Redémarrer toute l'infra
INFRA_DIR=$(sudo find /home/gitlab-runner/builds -name docker-compose.yml -path '*/infra/*' -printf '%h' -quit)
sudo bash -c "cd $INFRA_DIR && docker compose down --remove-orphans && docker compose up -d"

# Vérifier le runner
sudo gitlab-runner status
sudo gitlab-runner verify

# Espace disque
df -h /
docker system df

# Nettoyage complet (⚠ supprime toutes les données)
docker system prune -af --volumes
```

## Datasets Airflow

Le DAG utilise des **Datasets** pour la traçabilité des données (visible dans Airflow UI → Datasets) :

| Dataset      | URI                                         | Produit par      | Consommé par  |
| ------------ | ------------------------------------------- | ---------------- | ------------- |
| kafka_raw    | `kafka://kafka:29092/job-offers`            | scrape_adzuna    | kafka_to_s3   |
| s3_lesjeudis | `s3://dpia-data-bucket/lesjeudis/`          | scrape_lesjeudis | etl_transform |
| s3_adzuna    | `s3://dpia-data-bucket/adzuna/`             | kafka_to_s3      | etl_transform |
| pg_clean     | `postgres://...dpia_db/offres_emploi_clean` | etl_transform    | Dashboard     |

## Flux des données

```
Adzuna API ──→ Kafka ──→ MinIO (S3) ──┐
                                        ├──→ ETL (psycopg2 COPY) ──→ PostgreSQL ──→ Dashboard
LesJeudis  ──→ MinIO (S3) ────────────┘
                                                                          ↓
                                                                    CSV (backup)
```

**Export PostgreSQL** : L'ETL utilise `psycopg2.copy_expert()` avec `COPY ... FROM STDIN WITH CSV` pour une insertion rapide et compatible avec toutes les versions de SQLAlchemy.
