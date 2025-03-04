from flask import Flask
import os
import unittest

from models import db
from models.saved_movie import SavedMovie
from models.user import User

from routes.saved_movie import saved_movie_api_bp


class TestSavedMovieSystem(unittest.TestCase):
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

            # Create a user first
            user = User(username="alice", password_hash="hash1")
            db.session.add(user)
            db.session.commit()

        # Initialize routes
        self.app.register_blueprint(saved_movie_api_bp)

        # Create a test client
        self.client = self.app.test_client()

    def tearDown(self):
        # Clean up the database
        with self.app.app_context():
            db.drop_all()  # Drop all tables

    def test_save_movie(self):
        # Test saving a movie
        response = self.client.post(
            "/movies/save",
            json={
                "user_id": 1,
                "movie_id": "123",
                "title": "Inception",
                "poster_path": "/inception.jpg",
                "rating": 8.8,
            },
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json["message"], "Movie saved successfully")

        # Verify the movie was saved in the database
        with self.app.app_context():
            saved_movie = SavedMovie.query.filter_by(
                user_id=1, movie_id="123"
            ).first()
            self.assertIsNotNone(saved_movie)
            self.assertEqual(saved_movie.title, "Inception")

    def test_get_saved_movies(self):
        # Save a movie
        self.client.post(
            "/movies/save",
            json={
                "user_id": 1,
                "movie_id": "123",
                "title": "Inception",
                "poster_path": "/inception.jpg",
                "rating": 8.8,
            },
        )

        # Test getting saved movies
        response = self.client.get("/movies/list?user_id=1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json["saved_movies"]), 1)
        self.assertEqual(
            response.json["saved_movies"][0]["title"], "Inception"
        )

    def test_remove_saved_movie(self):
        # Save a movie
        self.client.post(
            "/movies/save",
            json={
                "user_id": 1,
                "movie_id": "123",
                "title": "Inception",
                "poster_path": "/inception.jpg",
                "rating": 8.8,
            },
        )

        # Test removing the saved movie
        response = self.client.delete(
            "/movies/remove",
            json={"saved_id": 1, "user_id": 1},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json["message"], "Movie removed from saved list"
        )

        # Verify the movie was removed from the database
        with self.app.app_context():
            saved_movie = SavedMovie.query.filter_by(id=1).first()
            self.assertIsNone(saved_movie)

    def test_update_saved_movie(self):
        # Save a movie
        self.client.post(
            "/movies/save",
            json={
                "user_id": 1,
                "movie_id": "123",
                "title": "Inception",
                "poster_path": "/inception.jpg",
                "rating": 8.8,
            },
        )

        # Test updating the saved movie
        response = self.client.put(
            "/movies/update",
            json={
                "saved_id": 1,
                "user_id": 1,
                "rating": 9.0,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json["message"], "Saved movie updated successfully"
        )

        # Verify the movie was updated in the database
        with self.app.app_context():
            saved_movie = SavedMovie.query.filter_by(id=1).first()
            self.assertEqual(saved_movie.rating, 9.0)


if __name__ == "__main__":
    unittest.main()
