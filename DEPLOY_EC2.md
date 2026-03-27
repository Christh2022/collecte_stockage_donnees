# Déploiement sur AWS EC2 — Guide complet

## Prérequis

- Un compte AWS avec accès à EC2
- Une paire de clés SSH (.pem) pour se connecter à l'instance
- Un compte GitLab avec le projet `collecte_stockage_donnees`

---

## 1. Créer l'instance EC2

1. Connectez-vous à la **console AWS** → **EC2** → **Lancer une instance**
2. Configuration recommandée :
   - **AMI** : Ubuntu Server 22.04 LTS
   - **Type** : `t3.medium` (2 vCPU, 4 Go RAM) minimum
   - **Stockage** : 30 Go gp3
   - **Paire de clés** : sélectionnez ou créez une clé `.pem`
3. **Groupe de sécurité** — ouvrir les ports entrants :

   | Port  | Protocole | Source    | Usage              |
   |-------|-----------|----------|--------------------|
   | 22    | TCP       | Votre IP | SSH                |
   | 8080  | TCP       | Votre IP | Airflow Webserver  |
   | 8050  | TCP       | Votre IP | Dashboard Dash     |
   | 9090  | TCP       | Votre IP | Prometheus         |
   | 3000  | TCP       | Votre IP | Grafana            |
   | 9001  | TCP       | Votre IP | MinIO Console      |

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

## 7. Cloner le projet

```bash
sudo -u gitlab-runner git clone https://gitlab.com/Christh2022/collecte_stockage_donnees.git \
  /home/gitlab-runner/collecte_stockage_donnees
```

---

## 8. Créer le fichier .env

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

## 9. Créer le dossier data

```bash
sudo mkdir -p /home/gitlab-runner/collecte_stockage_donnees/data/clean
sudo chown -R gitlab-runner:gitlab-runner /home/gitlab-runner/collecte_stockage_donnees/.env \
  /home/gitlab-runner/collecte_stockage_donnees/data
```

---

## 10. Configurer les variables CI/CD sur GitLab

Dans **GitLab** → **Settings** → **CI/CD** → **Variables**, ajoutez (si besoin pour la prod) :

| Variable               | Valeur                    | Protégé | Masqué |
|------------------------|---------------------------|---------|--------|
| `AWS_ACCESS_KEY_ID`    | Votre clé AWS             | Oui     | Oui    |
| `AWS_SECRET_ACCESS_KEY`| Votre secret AWS          | Oui     | Oui    |
| `AWS_DEFAULT_REGION`   | `eu-west-1`               | Non     | Non    |
| `S3_BUCKET_NAME`       | `dpia-data-bucket`        | Non     | Non    |

---

## 11. Déployer

Le déploiement est **automatique**. Depuis votre machine locale :

```bash
git add .
git commit -m "Déploiement initial sur EC2 via CI/CD"
git push origin main
```

Le pipeline GitLab CI/CD va :
1. **lint** — Vérifier le code avec flake8
2. **build** — Construire l'image Docker
3. **test** — Exécuter les tests unitaires et d'intégration
4. **deploy** — Sur l'EC2, `git pull` + `docker compose up -d`

---

## 12. Vérifier le déploiement

Sur l'EC2 :

```bash
# Vérifier les containers
sudo -u gitlab-runner docker ps

# Vérifier Airflow
curl -s http://localhost:8080/health

# Voir les logs Airflow
sudo -u gitlab-runner docker logs dpia-airflow-webserver --tail 20
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

# Redémarrer toute l'infra
cd /home/gitlab-runner/collecte_stockage_donnees/infra
sudo -u gitlab-runner docker compose down
sudo -u gitlab-runner docker compose up -d

# Vérifier le runner
sudo gitlab-runner status
sudo gitlab-runner verify
```
