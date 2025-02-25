from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(128), unique=True, nullable=False)
    email = db.Column(db.String(128), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    friendships = db.relationship(
        "Friendship",
        foreign_keys="Friendship.user_id",
        backref="user",
        lazy=True,
    )

    @property
    def password(self):
        # Prevent reading the password attribute
        raise AttributeError("password is not a readable attribute")

    @password.setter
    def password(self, password):
        # Automatically hash on setting
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password):
        # Check hashed password
        return check_password_hash(self.password_hash, password)


class ChatMessage(db.Model):
    __tablename__ = "chat_messages"
    user_id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Text, primary_key=True)
    sender = db.Column(
        db.Text, primary_key=True
    )  # or remove primary_key here if you prefer
    message = db.Column(db.Text, nullable=False)
    timestamp = db.Column(
        db.DateTime, primary_key=True, default=datetime.now()
    )

    def __repr__(self):
        return f"<ChatMessage user_id={self.user_id}, session_id={self.session_id}, sender={self.sender}, message={self.message}, timestamp={self.timestamp}>"


class Friendship(db.Model):
    __tablename__ = "friendships"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    friend_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False
    )
    status = db.Column(
        db.Enum("pending", "accepted", "blocked", name="friendship_status"),
        default="pending",
    )
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Unique constraint to prevent duplicate friendships
    __table_args__ = (
        db.UniqueConstraint("user_id", "friend_id", name="unique_friendship"),
    )
