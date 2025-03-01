import os
from dotenv import load_dotenv

# Only load .env in development mode (Optional)
if os.getenv("FLASK_ENV") == "development":
    load_dotenv()


class Config:
    # --------------------------------------
    # Flask / SQLAlchemy Settings
    # --------------------------------------
    SQLALCHEMY_DATABASE_URI = os.getenv("SQLALCHEMY_DATABASE_URI")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # This dictionary passes extra options to SQLAlchemy's create_engine.
    # 'pool_pre_ping': True ensures the connection is tested with a SELECT 1,
    # preventing stale connections from causing errors.
    # 'pool_recycle' ensures connections are recycled after N seconds,
    # so they don't remain idle too long.
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,  # 5 minutes
    }

    # --------------------------------------
    # Redis config
    # --------------------------------------
    REDIS_HOST = os.getenv("REDIS_HOST")
    REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
    REDIS_DB = int(os.getenv("REDIS_DB", 0))
    REDIS_DECODE_RESPONSES = (
        os.getenv("REDIS_DECODE_RESPONSES", "True") == "True"
    )

    # --------------------------------------
    # Flask Secret Key
    # (Make sure to set this as an environment variable in production)
    # --------------------------------------
    SECRET_KEY = os.getenv("SECRET_KEY", "default_secret_key")
