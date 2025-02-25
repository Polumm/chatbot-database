from flask import Flask

import os
import unittest

from models import db, User, Friendship
from routes import init_routes


class TestFriendSystem(unittest.TestCase):
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
        init_routes(self.app)

        # Create a test client
        self.client = self.app.test_client()

    def tearDown(self):
        # Clean up the database
        with self.app.app_context():
            db.drop_all()  # Drop all tables

    def test_send_friend_request(self):
        # Create two users
        with self.app.app_context():
            user1 = User(
                username="alice",
                email="alice@example.com",
                password_hash="hash1",
            )
            user2 = User(
                username="bob", email="bob@example.com", password_hash="hash2"
            )
            db.session.add(user1)
            db.session.add(user2)
            db.session.commit()

            # Send a friend request
            response = self.client.post(
                "/api/friends/request",
                json={"user_id": user1.id, "friend_id": user2.id},
            )
            self.assertEqual(response.status_code, 201)
            self.assertIn("message", response.json)
            self.assertEqual(
                response.json["message"], "Friend request sent successfully"
            )

    def test_accept_friend_request(self):
        # Create two users
        with self.app.app_context():
            user1 = User(
                username="alice",
                email="alice@example.com",
                password_hash="hash1",
            )
            user2 = User(
                username="bob", email="bob@example.com", password_hash="hash2"
            )
            db.session.add(user1)
            db.session.add(user2)
            db.session.commit()

            # Send a friend request
            friendship = Friendship(
                user_id=user1.id, friend_id=user2.id, status="pending"
            )
            db.session.add(friendship)
            db.session.commit()

            # Accept the friend request
            response = self.client.put(
                "/api/friends/accept", json={"friendship_id": friendship.id}
            )
            self.assertEqual(response.status_code, 200)
            self.assertIn("message", response.json)
            self.assertEqual(
                response.json["message"], "Friend request accepted"
            )

    def test_get_friend_list(self):
        # Create two users
        with self.app.app_context():
            user1 = User(
                username="alice",
                email="alice@example.com",
                password_hash="hash1",
            )
            user2 = User(
                username="bob", email="bob@example.com", password_hash="hash2"
            )
            db.session.add(user1)
            db.session.add(user2)
            db.session.commit()

            # Establish a friendship
            friendship = Friendship(
                user_id=user1.id, friend_id=user2.id, status="accepted"
            )
            db.session.add(friendship)
            db.session.commit()

            # Get the friend list
            response = self.client.get(f"/api/friends/list?user_id={user1.id}")
            self.assertEqual(response.status_code, 200)
            self.assertIn("friends", response.json)
            for _ in range(10):
                print()
            print(response.json)
            for _ in range(10):
                print()
            self.assertEqual(len(response.json["friends"]), 1)
            self.assertEqual(response.json["friends"][0]["username"], "bob")


if __name__ == "__main__":
    unittest.main()
