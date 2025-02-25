from datetime import datetime, timezone

from . import db


class ChatMessage(db.Model):
    __tablename__ = "chat_messages"
    user_id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Text, primary_key=True)
    sender = db.Column(
        db.Text, primary_key=True
    )  # or remove primary_key here if you prefer
    message = db.Column(db.Text, nullable=False)
    timestamp = db.Column(
        db.DateTime,
        primary_key=True,
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self):
        return f"<ChatMessage user_id={self.user_id}, session_id={self.session_id}, sender={self.sender}, message={self.message}, timestamp={self.timestamp}>"
