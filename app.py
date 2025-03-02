import threading
import time
from datetime import datetime, timedelta, timezone

import redis
from flask import Flask
from flask_cors import CORS

from config import Config
from models import db
from models.active_user import ActiveUser  # Make sure you have this model
from routes.chat_message import chat_message_api_bp, get_redis_connection
from routes.friendship import friendship_api_bp
from routes.saved_movie import saved_movie_api_bp
from routes.user import user_api_bp
from routes import sync_redis_session_to_postgres
from sqlalchemy.exc import OperationalError


def background_inactive_checker(app):
    while True:
        time.sleep(300)
        with app.app_context():
            try:
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

            except OperationalError:
                # Stale connection? Roll back, dispose, and optionally log it.
                db.session.rollback()
                db.engine.dispose()
                print(
                    "Detected stale DB connection, disposed engine and will retry."
                )


def create_app():
    app = Flask(__name__)
    CORS(app)
    app.config.from_object(Config)

    # Initialize SQLAlchemy with the configured engine options
    db.init_app(app)
    print("Engine options:", app.config.get("SQLALCHEMY_ENGINE_OPTIONS"))

    # Create a robust Redis client
    def create_robust_redis_client():
        return redis.Redis(
            host=Config.REDIS_HOST,
            port=Config.REDIS_PORT,
            db=Config.REDIS_DB,
            decode_responses=Config.REDIS_DECODE_RESPONSES,
            # The following help avoid stale connections in Redis:
            socket_keepalive=True,
            retry_on_timeout=True,
            health_check_interval=30,
            socket_connect_timeout=2,
        )

    app.redis = create_robust_redis_client()

    # Register your Blueprints
    app.register_blueprint(chat_message_api_bp)
    app.register_blueprint(friendship_api_bp)
    app.register_blueprint(saved_movie_api_bp)
    app.register_blueprint(user_api_bp)

    # Ensure DB tables exist
    with app.app_context():
        db.create_all()

    # Start the background thread for inactive user cleanup
    thread = threading.Thread(
        target=background_inactive_checker, args=(app,), daemon=True
    )
    thread.start()

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=6003, debug=True)
