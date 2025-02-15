from flask import Blueprint, request, jsonify, current_app
from werkzeug.security import generate_password_hash
import json
import time
import random
from datetime import datetime
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
    Create a new chat session (stored in Redis) while ensuring uniqueness per user.
    """
    data = request.get_json()
    username = data.get("username")
    session_name = (
        data.get("session_name", "").strip().lower()
    )  # Normalize session name

    if not username or not session_name:
        return jsonify(
            {"error": "Username and session_name are required."}
        ), 400

    session_list_key = f"bot-sessions-{username}"

    # Ensure uniqueness: Check if session already exists for this user (case-insensitive)
    existing_sessions = {s.lower() for s in current_app.redis.smembers(session_list_key)}  # Convert to lowercase set

    if session_name.lower() in existing_sessions:
        return jsonify(
            {
                "error": f"Session '{session_name}' already exists for user '{username}'."
            }
        ), 400

    # Add new session name under user's session list
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
    username = data.get("username", "").strip()
    sender = data.get("sender", username).strip()
    session_id = (
        data.get("session_id", "").strip().lower()
    )  # Normalize session ID
    message = data.get("message", "").strip()
    timestamp = data.get("time", "").strip()

    if not timestamp:
        timestamp = time.strftime(
            "%Y-%m-%d %H:%M:%S", time.localtime()
        )  # Fallback timestamp

    if not username or not session_id or not message:
        return jsonify(
            {"error": "username, session_id, and message are required."}
        ), 400

    # Ensure session exists before storing messages
    session_list_key = f"bot-sessions-{username}"
    if not current_app.redis.sismember(session_list_key, session_id):
        return jsonify(
            {
                "error": f"Session '{session_id}' does not exist for user '{username}'."
            }
        ), 400

    # Store messages uniquely per (username, session_id)
    conversation_key = f"bot-{username}-{session_id}"
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
    session_id = session_id.lower()  # Normalize session ID
    conversation_key = f"bot-{username}-{session_id}"

    raw_data = current_app.redis.zrange(
        conversation_key, 0, -1, withscores=True
    )
    messages = [json.loads(msg_json) for msg_json, _ in raw_data]

    return jsonify({"messages": messages}), 200


@database_bp.route(
    "/botchat/delete/<username>/<session_id>", methods=["DELETE"]
)
def delete_session(username, session_id):
    """
    Delete a specific session (and its messages) from Redis.
    """
    session_id = session_id.lower()  # Normalize session ID
    session_list_key = f"bot-sessions-{username}"

    # Ensure the session belongs to the user
    if not current_app.redis.sismember(session_list_key, session_id):
        return jsonify(
            {
                "error": f"Session '{session_id}' not found for user '{username}'."
            }
        ), 404

    # Remove session from user's session list
    current_app.redis.srem(session_list_key, session_id)

    # Delete messages associated with the session
    conversation_key = f"bot-{username}-{session_id}"
    current_app.redis.delete(conversation_key)

    return jsonify(
        {"message": f"Session '{session_id}' deleted for user '{username}'."}
    ), 200


@database_bp.route("/botchat/search/<username>", methods=["GET"])
def search_messages(username):
    """
    Fuzzy search across all chat sessions for the specified user.
    Usage: GET /botchat/search/<username>?query=xxx
    """
    query = request.args.get("query", "").strip().lower()
    if not query:
        return jsonify({"error": "No query provided."}), 400

    session_list_key = f"bot-sessions-{username}"
    session_ids = current_app.redis.smembers(session_list_key)
    results = []

    for session_id in session_ids:
        conversation_key = f"bot-{username}-{session_id}"
        messages_with_score = current_app.redis.zrange(
            conversation_key, 0, -1, withscores=True
        )

        for msg_json, score in messages_with_score:
            msg_obj = json.loads(msg_json)
            if query in msg_obj.get("text", "").lower():
                msg_time = time.strftime(
                    "%Y-%m-%d %H:%M:%S", time.localtime(score)
                )
                results.append(
                    {
                        "session_id": session_id,
                        "sender": msg_obj.get("sender", "unknown"),
                        "text": msg_obj.get("text", ""),
                        "time": msg_time,
                    }
                )

    return jsonify({"results": results, "query": query}), 200
