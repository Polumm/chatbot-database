from datetime import datetime, timezone
from . import db


class ActiveUser(db.Model):
    __tablename__ = "active_users"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    last_seen = db.Column(
        db.DateTime,
        default=datetime.now(timezone.utc),
        nullable=False,
    )
    session_expiry = db.Column(db.DateTime, nullable=True)

    # Relationship back to the User model
    user = db.relationship("User", backref="active_user_entries", lazy=True)

    def __repr__(self):
        return (
            f"<ActiveUser user_id={self.user_id} last_seen={self.last_seen}>"
        )
