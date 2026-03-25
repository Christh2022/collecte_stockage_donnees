"""
Script de configuration sécurité AWS pour le projet DPIA.

Actions effectuées :
1. Active le chiffrement AES-256 (SSE-S3) par défaut sur le bucket S3.
2. Bloque tout accès public au bucket.
3. Active le versioning pour la protection des données.

Usage:
    python -m infra.aws.setup_s3_encryption

Prérequis:
    - Variables AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION
      configurées dans .env ou dans l'environnement.
    - Le bucket S3 doit déjà exister.
"""

import os
import sys

import boto3
from dotenv import load_dotenv

load_dotenv()

BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "dpia-data-bucket")
AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "eu-west-1")


def get_s3_client():
    return boto3.client("s3", region_name=AWS_REGION)


def enable_default_encryption(s3_client):
    """Active le chiffrement AES-256 (SSE-S3) par défaut."""
    s3_client.put_bucket_encryption(
        Bucket=BUCKET_NAME,
        ServerSideEncryptionConfiguration={
            "Rules": [
                {
                    "ApplyServerSideEncryptionByDefault": {
                        "SSEAlgorithm": "AES256"
                    },
                    "BucketKeyEnabled": True,
                }
            ]
        },
    )
    print(f"[OK] Chiffrement AES-256 activé sur s3://{BUCKET_NAME}")


def block_public_access(s3_client):
    """Bloque tout accès public au bucket."""
    s3_client.put_public_access_block(
        Bucket=BUCKET_NAME,
        PublicAccessBlockConfiguration={
            "BlockPublicAcls": True,
            "IgnorePublicAcls": True,
            "BlockPublicPolicy": True,
            "RestrictPublicBuckets": True,
        },
    )
    print(f"[OK] Accès public bloqué sur s3://{BUCKET_NAME}")


def enable_versioning(s3_client):
    """Active le versioning pour protéger contre les suppressions accidentelles."""
    s3_client.put_bucket_versioning(
        Bucket=BUCKET_NAME,
        VersioningConfiguration={"Status": "Enabled"},
    )
    print(f"[OK] Versioning activé sur s3://{BUCKET_NAME}")


def main():
    print(f"Configuration sécurité du bucket: {BUCKET_NAME}")
    print("=" * 50)

    s3 = get_s3_client()

    try:
        s3.head_bucket(Bucket=BUCKET_NAME)
    except s3.exceptions.ClientError:
        print(f"[ERREUR] Le bucket '{BUCKET_NAME}' n'existe pas ou accès refusé.")
        sys.exit(1)

    enable_default_encryption(s3)
    block_public_access(s3)
    enable_versioning(s3)

    print("=" * 50)
    print("Configuration sécurité S3 terminée.")


if __name__ == "__main__":
    main()
