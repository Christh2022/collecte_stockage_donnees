"""Module monitoring - logging console (dev) ou CloudWatch (prod)."""

from src.monitoring.logger import get_logger

__all__ = ["get_logger"]
