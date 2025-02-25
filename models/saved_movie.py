from datetime import datetime, timezone

from . import db


class SavedMovie(db.Model):
    __tablename__ = "saved_movies"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    movie_id = db.Column(
        db.String(20), nullable=False
    )  # External movie ID (e.g. TMDB or IMDB ID)
    title = db.Column(db.String(255), nullable=False)
    poster_path = db.Column(db.String(255), nullable=True)
    rating = db.Column(db.Float, nullable=True)  # Optional user rating
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Define relationship with User
    user = db.relationship(
        "User", backref=db.backref("saved_movies", lazy=True)
    )

    # Unique constraint to prevent a user from saving the same movie twice
    __table_args__ = (
        db.UniqueConstraint("user_id", "movie_id", name="unique_user_movie"),
    )

    def __repr__(self):
        return f"<SavedMovie id={self.id}, user_id={self.user_id}, movie_id={self.movie_id}, title={self.title}>"
