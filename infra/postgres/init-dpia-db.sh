#!/bin/bash
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
    SELECT 'CREATE DATABASE dpia_db OWNER airflow'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'dpia_db')\gexec
EOSQL
