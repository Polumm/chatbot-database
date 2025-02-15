from flask import Blueprint, request, jsonify, current_app
from werkzeug.security import generate_password_hash
import json
import time
import random

from models import db, User  # Your SQLAlchemy models

database_bp = Blueprint("database", __name__)


# ---------------------------
#       User Endpoints
# ---------------------------


@database_bp.route("/users", methods=["POST"])
def create_user():
    data = request.get_json()
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    if not username or not password:
        return jsonify({"error": "Username and password required."}), 400

    existing_user = User.query.filter_by(username=username).first()
    if existing_user:
        return jsonify({"error": "User already exists."}), 400

    new_user = User(
        username=username, password_hash=generate_password_hash(password)
    )
    db.session.add(new_user)
    db.session.commit()
    return jsonify({"message": "User created successfully!"}), 201


@database_bp.route("/users/<username>", methods=["GET"])
def get_user(username):
    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({"error": "User not found."}), 404
    return jsonify(
        {
            "id": user.id,
            "username": user.username,
            "password_hash": user.password_hash,
        }
    )


@database_bp.route("/users/<username>", methods=["DELETE"])
def delete_user(username):
    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({"error": "User not found."}), 404
    db.session.delete(user)
    db.session.commit()
    return jsonify({"message": "User deleted successfully!"})


# ---------------------------
#     Bot Chat Endpoints
# ---------------------------


@database_bp.route("/botchat/sessions", methods=["POST"])
def new_session():
    """
    Create a new chat session (stored in Redis).
    """
    data = request.get_json()
    username = data.get("username")
    session_name = data.get("session_name", "").strip()

    if not username or not session_name:
        return jsonify(
            {"error": "Username and session_name are required."}
        ), 400

    session_list_key = f"bot-sessions-{username}"
    current_app.redis.sadd(session_list_key, session_name)
    return jsonify({"message": f"New session '{session_name}' created!"}), 201


@database_bp.route("/botchat/sessions/<username>", methods=["GET"])
def get_sessions(username):
    """
    Return all sessions for a given user from Redis.
    """
    session_list_key = f"bot-sessions-{username}"
    session_ids = list(current_app.redis.smembers(session_list_key))
    return jsonify({"sessions": session_ids}), 200


@database_bp.route("/botchat/messages", methods=["POST"])
def send_message():
    """
    Add a new message to a session in Redis.
    This endpoint can store messages for both user and bot,
    but the conversation key is always tied to the real user's name.
    """
    data = request.get_json()

    # 'username' is the real user who "owns" the conversation
    username = data.get("username", "").strip()

    # 'sender' can be "user" or "bot" (or default to username if missing)
    sender = data.get("sender", username).strip()

    session_id = data.get("session_id", "").strip()
    message = data.get("message", "").strip()
    timestamp = data.get("time", "").strip()
    if not timestamp:
        # fallback if not provided
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    if not username or not session_id or not message:
        return jsonify(
            {"error": "username, session_id, and message are required."}
        ), 400

    # Make sure session exists if sender != 'bot'
    if sender != "bot":
        session_list_key = f"bot-sessions-{username}"
        if not current_app.redis.sismember(session_list_key, session_id):
            return jsonify(
                {"error": f"Session '{session_id}' does not exist."}
            ), 400

    # Always use the real 'username' for the conversation key
    conversation_key = f"bot-{username}-{session_id}"

    # Build the message data with 'sender' and 'text'
    message_data = {"sender": sender, "text": message, "time": timestamp}

    # Score for sorted insertion
    score = time.time() + random.random() / 10000
    current_app.redis.zadd(conversation_key, {json.dumps(message_data): score})

    return jsonify(
        {"message": "Message stored successfully!", "time": timestamp}
    ), 201


@database_bp.route(
    "/botchat/messages/<username>/<session_id>", methods=["GET"]
)
def get_messages(username, session_id):
    """
    Retrieve all messages for a given (username, session_id) from Redis.
    """
    conversation_key = f"bot-{username}-{session_id}"
    raw_data = current_app.redis.zrange(
        conversation_key, 0, -1, withscores=True
    )
    messages = []
    for msg_json, _score in raw_data:
        messages.append(json.loads(msg_json))
    return jsonify({"messages": messages}), 200


@database_bp.route(
    "/botchat/delete/<username>/<session_id>", methods=["DELETE"]
)
def delete_session(username, session_id):
    """
    Delete a specific session (and its messages) from Redis.
    """
    session_list_key = f"bot-sessions-{username}"
    if current_app.redis.sismember(session_list_key, session_id):
        current_app.redis.srem(session_list_key, session_id)
        conversation_key = f"bot-{username}-{session_id}"
        current_app.redis.delete(conversation_key)
        return jsonify({"message": f"Session '{session_id}' deleted."}), 200
    else:
        return jsonify({"error": f"Session '{session_id}' not found."}), 404
