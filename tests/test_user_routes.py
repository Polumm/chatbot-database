from flask import Flask
import os
import unittest

from models import db
from models.user import User

from routes.user import user_api_bp


class TestUserSystem(unittest.TestCase):
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
        self.app.register_blueprint(user_api_bp)

        # Create a test client
        self.client = self.app.test_client()

    def tearDown(self):
        # Clean up the database
        with self.app.app_context():
            db.drop_all()  # Drop all tables

    def test_create_user(self):
        # Test creating a new user
        response = self.client.post(
            "/users",
            json={"username": "alice", "password": "password123"},
        )
        self.assertEqual(response.status_code, 201)
        self.assertIn("message", response.json)
        self.assertEqual(
            response.json["message"], "User created successfully!"
        )

        # Verify the user was added to the database
        with self.app.app_context():
            user = User.query.filter_by(username="alice").first()
            self.assertIsNotNone(user)
            self.assertEqual(user.username, "alice")

    def test_get_user(self):
        # Create a user first
        self.client.post(
            "/users",
            json={"username": "alice", "password": "password123"},
        )

        # Test getting the user
        response = self.client.get("/users/alice")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["username"], "alice")

    def test_delete_user(self):
        # Create a user first
        self.client.post(
            "/users",
            json={"username": "alice", "password": "password123"},
        )

        # Test deleting the user
        response = self.client.delete("/users/alice")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json["message"], "User deleted successfully!"
        )

        # Verify the user was deleted from the database
        with self.app.app_context():
            user = User.query.filter_by(username="alice").first()
            self.assertIsNone(user)


if __name__ == "__main__":
    unittest.main()
