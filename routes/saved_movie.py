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
    user_id = data.get("user_id")
    movie_id = data.get("movie_id")
    title = data.get("title")
    poster_path = data.get("poster_path")
    rating = data.get("rating")
    notes = data.get("notes")

    # Check if the movie is already saved by this user
    existing_saved = SavedMovie.query.filter_by(
        user_id=user_id, movie_id=movie_id
    ).first()

    if existing_saved:
        return jsonify({"message": "Movie already saved"}), 400

    # Create a new saved movie entry
    saved_movie = SavedMovie(
        user_id=user_id,
        movie_id=movie_id,
        title=title,
        poster_path=poster_path,
        rating=rating,
        notes=notes,
    )

    db.session.add(saved_movie)
    db.session.commit()

    return jsonify(
        {"message": "Movie saved successfully", "id": saved_movie.id}
    ), 201


@saved_movie_api_bp.route("/movies/list", methods=["GET"])
def get_saved_movies():
    user_id = request.args.get("user_id")

    # Add basic error handling for user_id
    try:
        user_id = int(user_id)
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid user ID"}), 400

    # Get all saved movies for this user
    saved_movies = SavedMovie.query.filter_by(user_id=user_id).all()

    # Format the results
    movie_list = [
        {
            "id": movie.id,
            "movie_id": movie.movie_id,
            "title": movie.title,
            "poster_path": movie.poster_path,
            "rating": movie.rating,
            "notes": movie.notes,
            "created_at": movie.created_at.isoformat()
            if movie.created_at
            else None,
        }
        for movie in saved_movies
    ]

    return jsonify({"saved_movies": movie_list}), 200


@saved_movie_api_bp.route("/movies/remove", methods=["DELETE"])
def remove_saved_movie():
    data = request.json
    saved_id = data.get("saved_id")
    user_id = data.get(
        "user_id"
    )  # For security, ensure the user owns this saved movie

    # Find the saved movie
    saved_movie = SavedMovie.query.filter_by(
        id=saved_id, user_id=user_id
    ).first()

    if not saved_movie:
        return jsonify(
            {"message": "Saved movie not found or access denied"}
        ), 404

    # Remove it
    db.session.delete(saved_movie)
    db.session.commit()

    return jsonify({"message": "Movie removed from saved list"}), 200


@saved_movie_api_bp.route("/movies/update", methods=["PUT"])
def update_saved_movie():
    data = request.json
    saved_id = data.get("saved_id")
    user_id = data.get("user_id")
    rating = data.get("rating")
    notes = data.get("notes")

    # Find the saved movie
    saved_movie = SavedMovie.query.filter_by(
        id=saved_id, user_id=user_id
    ).first()

    if not saved_movie:
        return jsonify(
            {"message": "Saved movie not found or access denied"}
        ), 404

    # Update fields if provided
    if rating is not None:
        saved_movie.rating = rating
    if notes is not None:
        saved_movie.notes = notes

    db.session.commit()

    return jsonify({"message": "Saved movie updated successfully"}), 200
