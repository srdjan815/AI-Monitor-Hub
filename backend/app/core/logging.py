from functools import lru_cache
from logging.config import dictConfig

from app.core.config import Settings

# Logging configuration
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {"()": "app.core.observability.JsonFormatter"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
        }
    },
    "root": {
        "level": "INFO",
        "handlers": ["console"],
    },
}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.model_validate({})


def setup_logging() -> None:
    dictConfig(LOGGING_CONFIG)
