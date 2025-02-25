import os
from dotenv import load_dotenv

# Only load .env in development mode (Optional)
if os.getenv("FLASK_ENV") == "development":
    load_dotenv()


class Config:
    # Flask/SQLAlchemy config
    SQLALCHEMY_DATABASE_URI = os.getenv("SQLALCHEMY_DATABASE_URI")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Redis config
    REDIS_HOST = os.getenv("REDIS_HOST")
    REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
    REDIS_DB = int(os.getenv("REDIS_DB", 0))
    REDIS_DECODE_RESPONSES = (
        os.getenv("REDIS_DECODE_RESPONSES", "True") == "True"
    )

    # Flask Secret Key (Make sure to set this as an environment variable in production)
    SECRET_KEY = os.getenv("SECRET_KEY", "default_secret_key")
