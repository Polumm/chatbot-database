from flask import Flask
import os
import unittest
from datetime import datetime, timezone
import redis

from models import db
from models.user import User
from config import Config

from routes.chat_message import chat_message_api_bp


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


class TestChatMessageSystem(unittest.TestCase):
    def setUp(self):
        # Create a test Flask application
        self.app = Flask(__name__)
        self.app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
            "TEST_FLASK_DB_URL"
        )
        self.app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
        self.app.config["TESTING"] = True

        # Initialize the database
        db.init_app(self.app)
        with self.app.app_context():
            db.create_all()  # Create all tables

        # Initialize routes
        self.app.register_blueprint(chat_message_api_bp)

        self.app.redis = create_robust_redis_client()

        # Create a test client
        self.client = self.app.test_client()

    def tearDown(self):
        # Clean up the database
        with self.app.app_context():
            db.drop_all()  # Drop all tables

    @unittest.skip("session name exists")
    def test_new_session(self):
        # Create a user
        with self.app.app_context():
            user = User(username="alice", password_hash="hash1")
            db.session.add(user)
            db.session.commit()

            # Create a new session
            response = self.client.post(
                "/botchat/sessions",
                json={"username": "alice", "session_name": "session1"},
            )
            print(response.text)
            self.assertEqual(response.status_code, 201)
            self.assertIn("message", response.json)
            self.assertEqual(
                response.json["message"], "New session 'session1' created!"
            )

    def test_get_sessions(self):
        # Create a user
        with self.app.app_context():
            user = User(username="alice", password_hash="hash1")
            db.session.add(user)
            db.session.commit()

            # Create a session
            self.client.post(
                "/botchat/sessions",
                json={"username": "alice", "session_name": "session1"},
            )

            # Get sessions
            response = self.client.get("/botchat/sessions/alice")
            self.assertEqual(response.status_code, 200)
            self.assertIn("sessions", response.json)
            self.assertEqual(len(response.json["sessions"]), 1)
            self.assertEqual(response.json["sessions"][0], "session1")

    def test_send_message(self):
        # Create a user
        with self.app.app_context():
            user = User(username="alice", password_hash="hash1")
            db.session.add(user)
            db.session.commit()

            # Create a session
            self.client.post(
                "/botchat/sessions",
                json={"username": "alice", "session_name": "session1"},
            )

            # Send a message
            response = self.client.post(
                "/botchat/messages",
                json={
                    "username": "alice",
                    "session_id": "session1",
                    "message": "Hello, world!",
                    "sender": "alice",
                    "time": datetime.now(timezone.utc).isoformat(),
                },
            )
            self.assertEqual(response.status_code, 201)
            self.assertIn("message", response.json)
            self.assertEqual(
                response.json["message"], "Message stored successfully!"
            )

    def test_get_messages(self):
        # Create a user
        with self.app.app_context():
            user = User(username="alice", password_hash="hash1")
            db.session.add(user)
            db.session.commit()

            # Create a session
            self.client.post(
                "/botchat/sessions",
                json={"username": "alice", "session_name": "session1"},
            )

            # Send a message
            self.client.post(
                "/botchat/messages",
                json={
                    "username": "alice",
                    "session_id": "session1",
                    "message": "Hello, world!",
                    "sender": "alice",
                    "time": datetime.now(timezone.utc).isoformat(),
                },
            )

            # Get messages
            response = self.client.get("/botchat/messages/alice/session1")
            self.assertEqual(response.status_code, 200)
            self.assertIn("messages", response.json)
            self.assertEqual(len(response.json["messages"]), 1)
            self.assertEqual(
                response.json["messages"][0]["text"], "Hello, world!"
            )

    def test_delete_session(self):
        # Create a user
        with self.app.app_context():
            user = User(username="alice", password_hash="hash1")
            db.session.add(user)
            db.session.commit()

            # Create a session
            self.client.post(
                "/botchat/sessions",
                json={"username": "alice", "session_name": "session1"},
            )

            # Send a message
            self.client.post(
                "/botchat/messages",
                json={
                    "username": "alice",
                    "session_id": "session1",
                    "message": "Hello, world!",
                    "sender": "alice",
                    "time": datetime.now(timezone.utc).isoformat(),
                },
            )

            # Delete the session
            response = self.client.delete("/botchat/delete/alice/session1")
            self.assertEqual(response.status_code, 200)
            self.assertIn("message", response.json)
            self.assertEqual(
                response.json["message"],
                "Session 'session1' deleted for user 'alice'.",
            )

            # Verify the session was deleted
            response = self.client.get("/botchat/messages/alice/session1")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(response.json["messages"]), 0)


if __name__ == "__main__":
    unittest.main()
