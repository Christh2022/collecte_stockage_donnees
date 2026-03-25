"""
Module de logging — console (dev) + CloudWatch (prod).

En dev (ENV_MODE=dev) : logs en console uniquement, aucune dépendance AWS.
En prod (ENV_MODE=prod) : logs console + CloudWatch via watchtower.

Usage:
    from src.monitoring.logger import get_logger
    logger = get_logger("scraper")
    logger.info("Scraping démarré")
"""

import logging
import os

from dotenv import load_dotenv

load_dotenv()

ENV_MODE = os.getenv("ENV_MODE", "dev")
LOG_GROUP = os.getenv("CLOUDWATCH_LOG_GROUP", "/dpia/pipeline")
AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "eu-west-1")

_initialized_loggers: dict[str, logging.Logger] = {}


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Retourne un logger avec console (toujours) + CloudWatch (prod uniquement)."""
    if name in _initialized_loggers:
        return _initialized_loggers[name]

    logger = logging.getLogger(f"dpia.{name}")
    logger.setLevel(level)
    logger.propagate = False

    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # --- Console handler (toujours actif) ---
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # --- CloudWatch handler (prod uniquement) ---
    if ENV_MODE == "prod":
        try:
            import boto3
            import watchtower

            session = boto3.Session(region_name=AWS_REGION)
            cw_handler = watchtower.CloudWatchLogHandler(
                log_group_name=LOG_GROUP,
                stream_name=name,
                boto3_session=session,
                create_log_group=True,
            )
            cw_handler.setFormatter(formatter)
            logger.addHandler(cw_handler)
            logger.debug("CloudWatch handler activé pour '%s'", name)
        except Exception as e:
            logger.warning(
                "CloudWatch indisponible, logs en console uniquement: %s", e
            )

    _initialized_loggers[name] = logger
    return logger
