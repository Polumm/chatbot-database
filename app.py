from flask import Flask
from config import Config
from models import db
import redis
from database_services import database_bp  # Import the Blueprint
from flask_cors import CORS


def create_app():
    app = Flask(__name__)
    CORS(app)
    app.config.from_object(Config)

    # Initialize SQLAlchemy
    db.init_app(app)

    # Initialize Redis
    app.redis = redis.Redis(
        host=Config.REDIS_HOST,
        port=Config.REDIS_PORT,
        db=Config.REDIS_DB,
        decode_responses=Config.REDIS_DECODE_RESPONSES,
    )

    # Register the Blueprint
    app.register_blueprint(database_bp)

    # Create database tables if they don't exist
    with app.app_context():
        db.create_all()

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=6003, debug=True)
