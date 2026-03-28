# Gouvernance des Données — Projet DPIA

## 1. Présentation

Ce document définit la politique de gouvernance des données du projet **DPIA** (Data Pipeline & Intelligence Analytique). Le projet collecte, stocke, transforme et visualise des offres d'emploi Data Science publiquement accessibles en France, à des fins d'analyse statistique du marché de l'emploi.

| Élément             | Détail                                                      |
| ------------------- | ----------------------------------------------------------- |
| Responsable         | Équipe DPIA                                                 |
| Périmètre           | Offres d'emploi Data Science (Adzuna API, LesJeudis)       |
| Finalité            | Analyse statistique du marché de l'emploi                   |
| Base légale (RGPD)  | Intérêt légitime (art. 6.1.f) — données publiques agrégées |
| Date de rédaction   | Mars 2026                                                   |

---

## 2. Données collectées

### 2.1 Sources

| Source      | Type d'accès | Méthode               | Fréquence    |
| ----------- | ------------ | --------------------- | ------------ |
| Adzuna API  | API publique | REST + clé API        | Quotidienne  |
| LesJeudis   | Web public   | Scraping (HTTP + BS4) | Quotidienne  |

### 2.2 Catégories de données

| Catégorie              | Champs                                                  | Données personnelles |
| ---------------------- | ------------------------------------------------------- | -------------------- |
| Offre d'emploi         | Titre, description, entreprise, localisation            | Non                  |
| Conditions             | Type de contrat, salaire min/max, date de publication   | Non                  |
| Compétences            | Tech stack (extrait par regex depuis la description)    | Non                  |
| Métadonnées techniques | Source, URL d'origine, date de collecte, identifiant    | Non                  |

> **Aucune donnée à caractère personnel** (nom, email, téléphone, CV) n'est collectée, stockée ou traitée par le pipeline. Seules les informations publiques relatives aux offres d'emploi sont exploitées.

---

## 3. Cycle de vie des données

```
 Collecte          Ingestion         Stockage           Transformation      Visualisation
+-----------+     +-----------+     +--------------+    +--------------+   +-------------+
| Adzuna    |---->|  Kafka    |---->|              |    |              |   |             |
| API       |     |  (topic)  |     |   MinIO      |--->|  ETL         |-->|  Dashboard  |
+-----------+     +-----------+     |   (raw/)     |    |  (pandas +   |   |  (Dash)     |
| LesJeudis |---------------------->|              |    |   psycopg2)  |   |             |
+-----------+                       +--------------+    +------+-------+   +-------------+
                                                               |
                                                        +------+-------+
                                                        | PostgreSQL   |
                                                        | (dpia_db)    |
                                                        | CSV export   |
                                                        +--------------+
```

| Phase            | Stockage              | Durée de rétention | Format            |
| ---------------- | --------------------- | ------------------ | ----------------- |
| Données brutes   | MinIO (`raw/`)        | 30 jours           | JSONL partitionné |
| Données nettoyées| PostgreSQL + CSV      | 90 jours           | Table SQL / CSV   |
| Logs applicatifs | Loki                  | 15 jours           | Docker JSON logs  |
| Métriques infra  | Prometheus            | 15 jours           | TSDB              |

---

## 4. Conformité RGPD

### 4.1 Analyse d'impact (DPIA simplifiée)

| Critère                                    | Évaluation | Justification                                                   |
| ------------------------------------------ | ---------- | --------------------------------------------------------------- |
| Données personnelles traitées              | **Non**    | Aucune donnée nominative collectée                              |
| Profilage de personnes physiques           | **Non**    | Analyse agrégée du marché, pas des individus                    |
| Traitement à grande échelle                | **Non**    | ~300-500 offres/jour, périmètre France uniquement               |
| Croisement de données                      | **Non**    | Pas de croisement avec d'autres bases de données                |
| Transfert hors UE                          | **Non**    | Hébergement EC2 eu-north-1 (Stockholm) + MinIO local sur l'instance |
| Nécessité d'une AIPD complète (art. 35)   | **Non**    | Aucun critère du G29 n'est rempli                               |

### 4.2 Droits des personnes

Le projet ne traite aucune donnée personnelle. Les données des offres sont publiquement disponibles sur les plateformes sources. En cas de demande d'un recruteur souhaitant le retrait de ses offres :
- Contact : équipe DPIA
- Délai de traitement : 72h
- Méthode : suppression de l'offre dans PostgreSQL + MinIO

### 4.3 Durées de conservation

| Donnée               | Durée       | Action à expiration                        |
| -------------------- | ----------- | ------------------------------------------ |
| Offres brutes (MinIO)| 30 jours    | Suppression manuelle ou script de purge    |
| Offres nettoyées     | 90 jours    | Archivage ou suppression                   |
| Logs                 | 15 jours    | Rotation automatique (Loki/Prometheus)     |
| Sauvegardes          | 7 jours     | Rotation des snapshots                     |

---

## 5. Sécurité des données

### 5.1 Mesures techniques

| Mesure                       | Implémentation                                            | Fichier                              |
| ---------------------------- | --------------------------------------------------------- | ------------------------------------ |
| Stockage objet local         | MinIO (compatible S3) sur l'instance EC2 — pas d'AWS S3   | `infra/docker-compose.yml`           |
| Isolation réseau MinIO       | Accessible uniquement via le réseau Docker interne         | `infra/docker-compose.yml`           |
| Volumes persistants          | Données MinIO + PostgreSQL sur volumes Docker nommés       | `infra/docker-compose.yml`           |
| Snapshots EBS                | Volume EBS 100 Go — snapshots pour sauvegarde              | Infrastructure EC2                   |
| Chiffrement en transit       | HTTPS pour les API (Adzuna), connexion interne Docker      | —                                    |
| Conteneurs non-root          | `USER` non-root dans Dockerfile                            | `Dockerfile`                         |
| Secrets masqués              | Variables CI/CD marquées "Protégé + Masqué" dans GitLab    | `.gitlab-ci.yml`                     |
| Réseau isolé                 | Réseau Docker bridge `dpia-net` — pas d'exposition inutile | `infra/docker-compose.yml`           |
| Security Group EC2           | Ports ouverts : 22 (SSH), 8080, 8050, 3000, 9090 uniquement| Infrastructure AWS                   |

### 5.2 Monitoring et alertes

| Outil       | Rôle                                          | Seuils d'alerte                  |
| ----------- | --------------------------------------------- | -------------------------------- |
| Prometheus  | Métriques CPU, RAM, disque, containers        | CPU > 90%, RAM > 85%, Disk > 80% |
| Grafana     | Dashboards monitoring + logs                  | Alertes visuelles                |
| Loki        | Agrégation des logs Docker (PostgreSQL, etc.) | Erreurs FATAL/PANIC              |
| Logger      | Logs applicatifs console                       | Configurable par module          |

### 5.3 Contrôle d'accès

| Service        | Authentification           | Accès réseau            |
| -------------- | -------------------------- | ----------------------- |
| Airflow        | admin / admin (à changer)  | Port 8080               |
| Grafana        | admin / admin (à changer)  | Port 3000               |
| MinIO Console  | minioadmin / minioadmin    | Port 9001               |
| PostgreSQL     | airflow / airflow          | Port 5432 (interne)     |
| Dashboard      | Aucun (lecture seule)      | Port 8050               |

> **Recommandation** : en production, remplacer les mots de passe par défaut et activer HTTPS via un reverse proxy (Nginx/Traefik + Let's Encrypt).

---

## 6. Qualité des données

### 6.1 Contrôles ETL

| Contrôle                   | Implémentation                                          |
| -------------------------- | ------------------------------------------------------- |
| Dédoublonnage              | Hash (entreprise + titre + ville) dans `etl_transform`  |
| Normalisation des dates    | Conversion ISO 8601, gestion des fuseaux horaires       |
| Normalisation des salaires | Conversion annuel/mensuel, fourchette min/max           |
| Normalisation contrats     | CDD, CDI, Stage, Alternance, Freelance, Intérim, Autre |
| Extraction tech stack      | Regex sur description vers liste de competences         |
| Validation des types       | Vérification des colonnes avant export PostgreSQL       |

### 6.2 Métriques de qualité (Dashboard page "Qualité")

- Taux de complétion par champ (salaire, localisation, contrat…)
- Nombre de doublons détectés et supprimés
- Couverture des données par source
- Évolution temporelle de la qualité

---

## 7. Traçabilité

| Élément                | Mécanisme                                                  |
| ---------------------- | ---------------------------------------------------------- |
| Origine des données    | Champ `source` (adzuna / lesjeudis) dans chaque enregistrement |
| Date de collecte       | Champ `collected_at` horodaté UTC                          |
| Pipeline d'exécution   | Airflow DAG `dpia_pipeline` — logs par tâche dans Airflow UI |
| Historique des fichiers| Partitionnement MinIO par date (`raw/adzuna/YYYY/MM/DD/`) |
| Versioning code        | Git (GitLab) — chaque déploiement lié à un commit          |
| Logs centralises       | Loki + Promtail vers Grafana (retention 15 jours)          |

---

## 8. Plan de continuité

| Risque                        | Mesure de mitigation                                          |
| ----------------------------- | ------------------------------------------------------------- |
| Perte de données MinIO        | Volumes Docker persistants + snapshots EBS                    |
| Perte base PostgreSQL         | Volume Docker persistant + possibilité de dump `pg_dump`      |
| Indisponibilité API Adzuna    | Retry avec backoff exponentiel (5 tentatives)                 |
| Indisponibilité LesJeudis     | Retry HTTP (3 tentatives) + données historiques conservées    |
| Crash container                | `restart: unless-stopped` sur tous les services               |
| Saturation disque              | Alerte Prometheus à 80% + rétention limitée (Loki 15j)       |
| Panne EC2                      | CI/CD GitLab — redéploiement en un push sur `main`            |

---

## 9. Responsabilités

| Rôle                     | Responsabilité                                              |
| ------------------------ | ----------------------------------------------------------- |
| Data Engineer            | Pipeline de collecte, ETL, qualité des données              |
| DevOps / Infra           | Docker, CI/CD, monitoring, sécurité infrastructure          |
| Responsable données      | Conformité RGPD, durées de conservation, demandes de retrait|
| Équipe projet            | Documentation, tests, maintenance du dashboard              |

---

## 10. Révision

Ce document doit être revu :
- À chaque ajout d'une nouvelle source de données
- En cas de modification du type de données collectées
- Au minimum une fois par an
- En cas d'incident de sécurité

| Version | Date       | Modification                          |
| ------- | ---------- | ------------------------------------- |
| 1.0     | Mars 2026  | Version initiale                      |
