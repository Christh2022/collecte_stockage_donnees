"""
"""Module monitoring — logging console (dev) ou CloudWatch (prod)."""

from src.monitoring.logger import get_logger

__all__ = ["get_logger"]


LOG_GROUP = os.getenv("CLOUDWATCH_LOG_GROUP", "/dpia/pipeline")
AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "eu-west-1")

_initialized_loggers: dict[str, logging.Logger] = {}


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Retourne un logger qui écrit en console ET dans CloudWatch Logs.

    Args:
        name: Nom du logger (ex: 'scraper', 'storage', 'pipeline').
              Utilisé comme nom de stream dans CloudWatch.
        level: Niveau de log (default: INFO).

    Returns:
        Logger configuré avec double handler (console + CloudWatch).
    """
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

    # --- CloudWatch handler (si credentials AWS dispo) ---
    try:
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
