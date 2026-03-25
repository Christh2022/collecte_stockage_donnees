# ============================================================
# Dockerfile — Projet DPIA
# Image légère Python 3.11 pour pipeline Data
# ============================================================

FROM python:3.11-slim AS base

# Métadonnées
LABEL maintainer="DPIA Team"
LABEL description="Pipeline d'analyse du marché de l'emploi Data Science"

# Variables d'environnement
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Dépendances système (chromedriver pour Selenium, pg_config pour psycopg2)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    gnupg \
    chromium \
    chromium-driver \
    gcc \
    libpq-dev && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Répertoire de travail
WORKDIR /app

# Installation des dépendances Python (layer cache optimisé)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copie du code source (ignoré en dev grâce aux volumes)
COPY src/ ./src/

# Utilisateur non-root pour la sécurité
RUN useradd --create-home appuser
USER appuser

# Point d'entrée par défaut
CMD ["python", "-m", "src.main"]
