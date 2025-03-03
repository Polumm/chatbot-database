from datetime import datetime, timezone
from . import db

class SavedMovie(db.Model):
    __tablename__ = "saved_movies"

    id = db.Column(db.Integer, primary_key=True)  # Unique ID for saved movies
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)  # Reference to User table
    movie_id = db.Column(db.String(20), nullable=False)  # TMDB Movie ID
    title = db.Column(db.String(255), nullable=False)  # Movie title
    poster_path = db.Column(db.String(255), nullable=True)  # Poster image URL
    release_date = db.Column(db.String(10), nullable=True)  # YYYY-MM-DD format
    vote_average = db.Column(db.Float, nullable=True)  # TMDB rating (0-10)
    vote_count = db.Column(db.Integer, nullable=True)  # Number of ratings on TMDB
    overview = db.Column(db.Text, nullable=True)  # Movie description
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    user = db.relationship("User", backref=db.backref("saved_movies", lazy=True))

    # Prevent duplicate saves by the same user
    __table_args__ = (db.UniqueConstraint("user_id", "movie_id", name="unique_user_movie"),)

    def __repr__(self):
        return f"<SavedMovie id={self.id}, user_id={self.user_id}, movie_id={self.movie_id}, title={self.title}>"
