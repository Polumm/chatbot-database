from flask import Blueprint, request, jsonify, current_app
from werkzeug.security import generate_password_hash
import json
import time
import random
from datetime import datetime
from models import db, User, ChatMessage  # + (Optional) Session model

database_bp = Blueprint("database", __name__)

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
        except:
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


# =================================
#       User Endpoints
# =================================


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


# =================================
#    Bot Chat / Session Endpoints
# =================================


@database_bp.route("/botchat/sessions", methods=["POST"])
def new_session():
    """
    Create a new chat session in Redis.
    Optionally, you can defer writing to PostgreSQL until session ends or user logs out.
    """
    data = request.get_json()
    username = data.get("username")
    session_name = data.get("session_name", "").strip().lower()
    if not username or not session_name:
        return jsonify(
            {"error": "Username and session_name are required."}
        ), 400

    # Make sure user actually exists in the DB:
    user_id = get_user_id(username)
    if not user_id:
        return jsonify(
            {"error": f"User '{username}' does not exist in DB."}
        ), 400

    session_list_key = f"bot-sessions-{username}"
    # Check uniqueness (case-insensitive)
    existing_sessions = {
        s.lower() for s in current_app.redis.smembers(session_list_key)
    }
    if session_name in existing_sessions:
        return jsonify(
            {
                "error": f"Session '{session_name}' already exists for user '{username}'."
            }
        ), 400

    # Add session to Redis
    current_app.redis.sadd(session_list_key, session_name)

    return jsonify({"message": f"New session '{session_name}' created!"}), 201


@database_bp.route("/botchat/sessions/<username>", methods=["GET"])
def get_sessions(username):
    """
    Return all session IDs for a given user.
    1) Check Redis first.
    2) If Redis is empty, fallback to PostgreSQL (chat_messages).
    3) Repopulate Redis so the next time we won't need the fallback.
    """
    session_list_key = f"bot-sessions-{username}"
    redis_sessions = current_app.redis.smembers(session_list_key)

    if redis_sessions:
        # Redis has data
        session_ids = sorted(list(redis_sessions))
    else:
        # Fallback to PostgreSQL
        user_id = get_user_id(username)
        if not user_id:
            return jsonify({"sessions": []}), 200

        # Query distinct session_ids from chat_messages
        session_records = (
            db.session.query(ChatMessage.session_id)
            .filter_by(user_id=user_id)
            .distinct()
            .all()
        )
        session_ids = [row.session_id for row in session_records]

        # Repopulate Redis so future requests are fast
        for sid in session_ids:
            current_app.redis.sadd(session_list_key, sid)

    return jsonify({"sessions": session_ids}), 200


@database_bp.route("/botchat/messages", methods=["POST"])
def send_message():
    """
    Add a new message to a session in Redis.
    """
    data = request.get_json()
    username = data.get("username", "").strip()
    sender = data.get("sender", username).strip()
    session_id = data.get("session_id", "").strip().lower()
    message = data.get("message", "").strip()
    timestamp = data.get("time", "").strip()

    if not timestamp:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    if not username or not session_id or not message:
        return jsonify(
            {"error": "username, session_id, and message are required."}
        ), 400

    # Ensure session exists in Redis
    session_list_key = f"bot-sessions-{username}"
    if not current_app.redis.sismember(session_list_key, session_id):
        return jsonify(
            {
                "error": f"Session '{session_id}' does not exist for user '{username}'."
            }
        ), 400

    # Store in Redis
    conversation_key = f"bot-{username}-{session_id}"
    message_data = {"sender": sender, "text": message, "time": timestamp}

    # Use (time.time() + random fraction) for the ZSET score
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
    Retrieve messages for (username, session_id) from Redis first.
    If Redis is empty, fallback to PostgreSQL and repopulate Redis.
    """
    session_id = session_id.lower()
    conversation_key = f"bot-{username}-{session_id}"
    raw_data = current_app.redis.zrange(
        conversation_key, 0, -1, withscores=True
    )

    if raw_data:
        # Found in Redis
        messages = [json.loads(msg_json) for msg_json, _ in raw_data]
    else:
        # Fallback to PostgreSQL
        user_id = get_user_id(username)
        if not user_id:
            return jsonify({"messages": []}), 200

        records = (
            ChatMessage.query.filter_by(user_id=user_id, session_id=session_id)
            .order_by(ChatMessage.timestamp.asc())
            .all()
        )
        messages = []
        for r in records:
            message_obj = {
                "sender": r.sender,
                "text": r.message,
                "time": r.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            }
            messages.append(message_obj)

            # Re-insert into Redis for future lookups
            # Use the Unix timestamp as the ZSET score (or add small random fraction to break ties)
            score = r.timestamp.timestamp()
            current_app.redis.zadd(
                conversation_key, {json.dumps(message_obj): score}
            )

    return jsonify({"messages": messages}), 200


@database_bp.route(
    "/botchat/delete/<username>/<session_id>", methods=["DELETE"]
)
def delete_session(username, session_id):
    """
    Delete a specific session (and its messages) from Redis.
    If you also want to remove from PostgreSQL, do it here or on sync.
    """
    session_id = session_id.lower()
    session_list_key = f"bot-sessions-{username}"

    # Ensure the session belongs to the user
    if not current_app.redis.sismember(session_list_key, session_id):
        return jsonify(
            {
                "error": f"Session '{session_id}' not found for user '{username}'."
            }
        ), 404

    # Remove from Redis
    current_app.redis.srem(session_list_key, session_id)
    conversation_key = f"bot-{username}-{session_id}"
    current_app.redis.delete(conversation_key)

    user_id = get_user_id(username)
    if user_id:
        ChatMessage.query.filter_by(
            user_id=user_id, session_id=session_id
        ).delete()
        db.session.commit()

    return jsonify(
        {"message": f"Session '{session_id}' deleted for user '{username}'."}
    ), 200


@database_bp.route("/botchat/search/<username>", methods=["GET"])
def search_messages(username):
    """
    Fuzzy search across all chat sessions for the specified user in Redis only.
    If not found in Redis, optionally fallback to PostgreSQL (you decide).
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

    # (Optional) Fallback to PostgreSQL if nothing found:
    # if not results:
    #     user_id = get_user_id(username)
    #     if user_id:
    #         # Simple LIKE query:
    #         records = ChatMessage.query.filter(
    #             ChatMessage.user_id == user_id,
    #             ChatMessage.message.ilike(f"%{query}%")
    #         ).all()
    #         for r in records:
    #             results.append({
    #                 "session_id": r.session_id,
    #                 "sender": r.sender,
    #                 "text": r.message,
    #                 "time": r.timestamp.strftime("%Y-%m-%d %H:%M:%S")
    #             })

    return jsonify({"results": results, "query": query}), 200


# =================================
#   New Sync / Logout Endpoints
# =================================


@database_bp.route("/botchat/sync/<username>/<session_id>", methods=["POST"])
def sync_session(username, session_id):
    """
    Force a single session to be synced from Redis to PostgreSQL.
    """
    session_id = session_id.lower()
    sync_redis_session_to_postgres(username, session_id)
    return jsonify(
        {"message": f"Session '{session_id}' synced to Postgres."}
    ), 200


@database_bp.route("/botchat/logout/<username>", methods=["POST"])
def logout_user(username):
    """
    Example endpoint that syncs all sessions for a user, then (optionally) clears them from Redis.
    """
    # 1) Sync each session individually
    session_list_key = f"bot-sessions-{username}"
    session_ids = current_app.redis.smembers(session_list_key)
    for session_id in session_ids:
        sync_redis_session_to_postgres(username, session_id)

    # 2) (Optional) Clear them from Redis if you like
    #    for session_id in session_ids:
    #        conversation_key = f"bot-{username}-{session_id}"
    #        current_app.redis.delete(conversation_key)
    #    current_app.redis.delete(session_list_key)

    return jsonify(
        {"message": f"All sessions for user '{username}' synced to Postgres."}
    ), 200
