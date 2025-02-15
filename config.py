import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    # Flask/SQLAlchemy config
    SQLALCHEMY_DATABASE_URI = os.getenv("SQLALCHEMY_DATABASE_URI")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Redis config
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
    REDIS_DB = int(os.getenv("REDIS_DB", 0))
    REDIS_DECODE_RESPONSES = (
        os.getenv("REDIS_DECODE_RESPONSES", "True") == "True"
    )

    # Flask Secret Key
    SECRET_KEY = os.getenv("SECRET_KEY", "default_secret_key")
