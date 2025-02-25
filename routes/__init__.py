from flask import Blueprint, jsonify, current_app

from datetime import datetime
import json

from models import db
from models.chat_message import ChatMessage
from models.user import User


other_api_bp = Blueprint("other", __name__)


@other_api_bp.route("/", methods=["GET"])
def health_check():
    return jsonify({"status": "Chatbot Database Service is running!"}), 200


# =================================
#         Helper Functions
# =================================


def get_user_id(username):
    """
    Helper to retrieve the user_id given a username.
    """
    user = User.query.filter_by(username=username).first()
    return user.id if user else None


def sync_redis_session_to_postgres(username, session_id):
    """
    Reads all messages for (username, session_id) from Redis,
    writes them into the chat_messages table (if not already present).
    """
    user_id = get_user_id(username)
    if not user_id:
        return  # No such user in DB

    conversation_key = f"bot-{username}-{session_id}"
    raw_data = current_app.redis.zrange(
        conversation_key, 0, -1, withscores=True
    )

    for msg_json, score in raw_data:
        msg_obj = json.loads(msg_json)
        sender = msg_obj.get("sender", "")
        text = msg_obj.get("text", "")
        # If 'time' was your canonical timestamp, parse it; otherwise use 'score'.
        # Example uses the 'time' field:
        ts_str = msg_obj.get("time")
        try:
            # Attempt to parse the original timestamp string:
            timestamp = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
        except Exception:
            # Fallback: Use 'score' to create a timestamp
            timestamp = datetime.fromtimestamp(score)

        # Insert only if not exists (simple approach: try-except for duplicates):
        existing = ChatMessage.query.filter_by(
            user_id=user_id,
            session_id=session_id,
            sender=sender,
            message=text,
            timestamp=timestamp,
        ).first()
        if existing:
            continue

        chat_msg = ChatMessage(
            user_id=user_id,
            session_id=session_id,
            sender=sender,
            message=text,
            timestamp=timestamp,
        )
        db.session.add(chat_msg)

    db.session.commit()
