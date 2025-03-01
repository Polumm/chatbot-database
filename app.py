import threading
import time
from datetime import datetime, timedelta, timezone
from models.active_user import ActiveUser
from flask import Flask
import redis
from flask_cors import CORS

from config import Config
from models import db
from routes.chat_message import chat_message_api_bp  # Import the Blueprint
from routes.friendship import friendship_api_bp
from routes.user import user_api_bp
from routes.saved_movie import saved_movie_api_bp
from routes.chat_message import get_redis_connection
from routes import sync_redis_session_to_postgres


def background_inactive_checker(app):
    with app.app_context():
        while True:
            time.sleep(300)  # 5 minutes
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=15)
            inactive_records = ActiveUser.query.filter(
                ActiveUser.last_seen < cutoff
            ).all()
            for record in inactive_records:
                username = record.user.username
                r = get_redis_connection()
                session_list_key = f"bot-sessions-{username}"
                session_ids = r.smembers(session_list_key)
                for s_id in session_ids:
                    sync_redis_session_to_postgres(username, s_id)
                db.session.delete(record)
            db.session.commit()


def create_app():
    app = Flask(__name__)
    CORS(app)
    app.config.from_object(Config)

    # Initialize SQLAlchemy
    db.init_app(app)

    # Create a helper function that returns a Redis client with robust settings
    def create_robust_redis_client():
        return redis.Redis(
            host=Config.REDIS_HOST,
            port=Config.REDIS_PORT,
            db=Config.REDIS_DB,
            decode_responses=Config.REDIS_DECODE_RESPONSES,
            # The following are key to avoiding stale connections:
            socket_keepalive=True,  # Keep TCP alive
            retry_on_timeout=True,  # Retry automatically if timed out
            health_check_interval=30,  # Seconds between PINGs for idle connections
        )

    # Initialize a robust Redis client
    app.redis = create_robust_redis_client()

    # Register the Blueprints
    app.register_blueprint(chat_message_api_bp)
    app.register_blueprint(friendship_api_bp)
    app.register_blueprint(saved_movie_api_bp)
    app.register_blueprint(user_api_bp)

    # Create database tables if they don't exist
    with app.app_context():
        db.create_all()

    # Start the background thread
    thread = threading.Thread(
        target=background_inactive_checker, args=(app,), daemon=True
    )
    thread.start()
    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=6003, debug=True)
