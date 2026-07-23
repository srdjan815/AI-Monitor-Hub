from logging.config import dictConfig
from functools import lru_cache

# Logging configuration
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "()": "logging.Formatter",
            "fmt": "%(asctime)s %(levelname)s %(name)s %(message)s"
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
        }
    },
    "root": {
        "level": "INFO",
        "handlers": ["console"]
    }
}

@lru_cache(maxsize=1)
def get_settings():
    from app.core.config import Settings
    return Settings()

def setup_logging():
    dictConfig(LOGGING_CONFIG)
