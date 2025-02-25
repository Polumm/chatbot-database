from flask import Flask
import redis
from flask_cors import CORS

from config import Config
from models import db
from routes.chat_message import chat_message_api_bp  # Import the Blueprint
from routes.friendship import friendship_api_bp
from routes.user import user_api_bp
from routes.saved_movie import saved_movie_api_bp


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

    # Register the Blueprints
    app.register_blueprint(chat_message_api_bp)
    app.register_blueprint(friendship_api_bp)
    app.register_blueprint(saved_movie_api_bp)
    app.register_blueprint(user_api_bp)

    # Create database tables if they don't exist
    with app.app_context():
        db.create_all()

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=6003, debug=True)
