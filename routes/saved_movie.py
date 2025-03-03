from flask import Blueprint, request, jsonify

from models import db
from models.saved_movie import SavedMovie


saved_movie_api_bp = Blueprint("saved_movie", __name__)


# =================================
#       Saved Movie Endpoints
# =================================


@saved_movie_api_bp.route("/movies/save", methods=["POST"])
def save_movie():
    data = request.json

    # Validate required fields
    user_id = data.get("user_id")
    movie_id = data.get("movie_id")
    title = data.get("title")

    if not user_id or not movie_id or not title:
        return jsonify({"error": "Missing required fields (user_id, movie_id, title)."}), 400

    # Get TMDB attributes
    poster_path = data.get("poster_path")
    release_date = data.get("release_date")
    vote_average = data.get("vote_average")
    vote_count = data.get("vote_count")
    overview = data.get("overview")

    # Check if the movie is already saved by this user
    existing_saved = SavedMovie.query.filter_by(user_id=user_id, movie_id=movie_id).first()

    if existing_saved:
        return jsonify({"message": "Movie already saved"}), 400

    # Create a new saved movie entry
    saved_movie = SavedMovie(
        user_id=user_id,
        movie_id=str(movie_id),  # Ensure it's stored as a string
        title=title,
        poster_path=poster_path,
        release_date=release_date,
        vote_average=vote_average,
        vote_count=vote_count,
        overview=overview
    )

    db.session.add(saved_movie)
    db.session.commit()

    return jsonify({"message": "Movie saved successfully", "id": saved_movie.id}), 201


@saved_movie_api_bp.route("/movies/list", methods=["GET"])
def get_saved_movies():
    user_id = request.args.get("user_id")

    if not user_id:
        return jsonify({"error": "User ID is required"}), 400

    # Get saved movies
    saved_movies = SavedMovie.query.filter_by(user_id=user_id).all()

    # Format movies to match TMDB API format
    movie_list = [
        {
            "id": movie.movie_id,  # TMDB ID
            "title": movie.title,
            "poster_path": movie.poster_path,
            "release_date": movie.release_date,
            "vote_average": movie.vote_average,
            "vote_count": movie.vote_count,
            "overview": movie.overview
        }
        for movie in saved_movies
    ]

    return jsonify({"saved_movies": movie_list}), 200


@saved_movie_api_bp.route("/movies/remove", methods=["DELETE"])
def remove_saved_movie():
    data = request.json
    movie_id = data.get("movie_id")  # TMDB movie ID
    user_id = data.get("user_id")  # Ensure the user owns this saved movie

    if not movie_id or not user_id:
        return jsonify({"error": "Missing required fields (movie_id, user_id)."}), 400

    # Find the saved movie by user and TMDB movie ID
    saved_movie = SavedMovie.query.filter_by(movie_id=movie_id, user_id=user_id).first()

    if not saved_movie:
        return jsonify({"message": "Saved movie not found or access denied"}), 404

    # Remove the saved movie
    db.session.delete(saved_movie)
    db.session.commit()

    return jsonify({"message": "Movie removed from saved list"}), 200


@saved_movie_api_bp.route("/movies/update", methods=["PUT"])
def update_saved_movie():
    data = request.json
    movie_id = data.get("movie_id")  # TMDB movie ID
    user_id = data.get("user_id")

    if not movie_id or not user_id:
        return jsonify({"error": "Missing required fields (movie_id, user_id)."}), 400

    # Find the saved movie
    saved_movie = SavedMovie.query.filter_by(movie_id=movie_id, user_id=user_id).first()

    if not saved_movie:
        return jsonify({"message": "Saved movie not found or access denied"}), 404

    # Update fields if provided
    if "title" in data:
        saved_movie.title = data["title"]
    if "poster_path" in data:
        saved_movie.poster_path = data["poster_path"]
    if "release_date" in data:
        saved_movie.release_date = data["release_date"]

    db.session.commit()

    return jsonify({"message": "Saved movie updated successfully"}), 200