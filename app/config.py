import logging
import os

logger = logging.getLogger(__name__)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, os.pardir))

DEV_SECRET_KEY = "eduscore-tracker-dev-key-change-in-production"


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", DEV_SECRET_KEY)
    if SECRET_KEY == DEV_SECRET_KEY:
        logger.warning(
            "SECRET_KEY not set in environment — using insecure dev key. "
            "Set the SECRET_KEY environment variable for production use."
        )
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{os.path.join(PROJECT_ROOT, 'instance', 'eduscore.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DEBUG = os.environ.get("DEBUG", "False").lower() in ("1", "true", "yes")
    HOST = os.environ.get("HOST", "127.0.0.1")
    PORT = int(os.environ.get("PORT", 5001))
    CACHE_TYPE = os.environ.get("CACHE_TYPE", "SimpleCache")
    CACHE_DEFAULT_TIMEOUT = int(os.environ.get("CACHE_DEFAULT_TIMEOUT", 300))
