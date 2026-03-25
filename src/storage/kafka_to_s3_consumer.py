"""
Consumer Kafka → S3/MinIO.

Lit le topic `job_api_raw` depuis Kafka et téléverse les messages
par lots vers S3 ou MinIO. Un batch est écrit quand :
    - 50 messages sont accumulés, OU
    - 1 minute s'est écoulée depuis le dernier flush

Les fichiers sont partitionnés par date :
    raw/adzuna/YYYY/MM/DD/<timestamp>_batch_<id>.jsonl

Usage:
    python -m src.storage.kafka_to_s3_consumer

Variables d'environnement requises:
    KAFKA_BOOTSTRAP_SERVERS, S3_BUCKET_NAME
    + AWS credentials OU MINIO_ENDPOINT pour le dev local
"""

import io
import json
import os
import sys
import time
from datetime import datetime, timezone

import boto3
from kafka import KafkaConsumer
from kafka.errors import NoBrokersAvailable
from dotenv import load_dotenv

load_dotenv()

# ── Configuration ──────────────────────────────────────────
KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC_RAW", "job_api_raw")
KAFKA_GROUP_ID = os.getenv("KAFKA_GROUP_ID", "s3-consumer-group")

S3_BUCKET = os.getenv("S3_BUCKET_NAME", "dpia-data-bucket")
S3_PREFIX = os.getenv("S3_PREFIX", "raw/adzuna")
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT")  # None en prod → AWS S3

BATCH_SIZE = int(os.getenv("CONSUMER_BATCH_SIZE", "50"))
BATCH_TIMEOUT = int(os.getenv("CONSUMER_BATCH_TIMEOUT", "60"))


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
        print(f"[S3] Mode AWS S3 → region {os.getenv('AWS_DEFAULT_REGION', 'eu-west-1')}")

    return boto3.client("s3", **kwargs)


def create_consumer(retries: int = 5, delay: int = 5) -> KafkaConsumer:
    """Crée un consumer Kafka avec retry."""
    for attempt in range(1, retries + 1):
        try:
            consumer = KafkaConsumer(
                KAFKA_TOPIC,
                bootstrap_servers=KAFKA_BOOTSTRAP,
                group_id=KAFKA_GROUP_ID,
                auto_offset_reset="earliest",
                enable_auto_commit=False,
                value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            )
            print(f"[OK] Consumer connecté à Kafka ({KAFKA_BOOTSTRAP}), topic '{KAFKA_TOPIC}'")
            return consumer
        except NoBrokersAvailable:
            print(f"[RETRY {attempt}/{retries}] Kafka indisponible, attente {delay}s...")
            time.sleep(delay)
    print("[ERREUR] Impossible de se connecter à Kafka.")
    sys.exit(1)


def build_s3_key(batch_id: int) -> str:
    """Construit un chemin S3 partitionné par date : raw/adzuna/YYYY/MM/DD/..."""
    now = datetime.now(timezone.utc)
    date_partition = now.strftime("%Y/%m/%d")
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    return f"{S3_PREFIX}/{date_partition}/{timestamp}_batch_{batch_id:04d}.jsonl"


def upload_batch(s3_client, batch: list[dict], batch_id: int) -> str:
    """Téléverse un lot de messages en JSON Lines vers S3/MinIO."""
    key = build_s3_key(batch_id)

    content = "\n".join(json.dumps(record, ensure_ascii=False) for record in batch)
    body = io.BytesIO(content.encode("utf-8"))

    s3_client.upload_fileobj(body, S3_BUCKET, key)
    print(f"[UPLOAD] {len(batch)} records → s3://{S3_BUCKET}/{key}")
    return key


def main():
    s3_client = create_s3_client()
    consumer = create_consumer()

    batch: list[dict] = []
    batch_id = 0
    total_uploaded = 0
    last_flush_time = time.monotonic()

    print(f"[INFO] Consommation en cours (batch={BATCH_SIZE} msgs / {BATCH_TIMEOUT}s)...\n")

    try:
        while True:
            # Poll avec un court timeout pour vérifier régulièrement le timer
            poll_timeout_ms = min(5000, BATCH_TIMEOUT * 1000)
            records = consumer.poll(timeout_ms=poll_timeout_ms)

            for topic_partition, messages in records.items():
                for message in messages:
                    batch.append(message.value)

                    # Flush si le batch atteint la taille max
                    if len(batch) >= BATCH_SIZE:
                        upload_batch(s3_client, batch, batch_id)
                        total_uploaded += len(batch)
                        batch_id += 1
                        batch = []
                        consumer.commit()
                        last_flush_time = time.monotonic()

            # Flush si le timeout est atteint avec des messages en attente
            elapsed = time.monotonic() - last_flush_time
            if batch and elapsed >= BATCH_TIMEOUT:
                upload_batch(s3_client, batch, batch_id)
                total_uploaded += len(batch)
                batch_id += 1
                batch = []
                consumer.commit()
                last_flush_time = time.monotonic()

    except KeyboardInterrupt:
        print("\n[STOP] Arrêt demandé.")
    finally:
        if batch:
            upload_batch(s3_client, batch, batch_id)
            total_uploaded += len(batch)
            batch_id += 1
            consumer.commit()

        consumer.close()
        print(f"[TERMINÉ] {total_uploaded} records uploadés en {batch_id} batches.")


if __name__ == "__main__":
    main()
    main()
