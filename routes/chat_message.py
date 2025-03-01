from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, current_app
import redis
import json
import time
import random

from models import db

# Look up the User by username
from models.user import User
from models.active_user import ActiveUser
from models.chat_message import ChatMessage
from . import get_user_id
from routes import get_redis_connection, sync_redis_session_to_postgres 


chat_message_api_bp = Blueprint("chat_message", __name__)


def get_redis_connection():
    """
    Returns a valid Redis connection. If the existing connection
    is stale/closed, re-initialize and retry once.
    """
    # Attempt twice: first the existing client, then re-init if needed.
    for _ in range(2):
        try:
            current_app.redis.ping()
            # If ping succeeds, return the existing client
            return current_app.redis
        except redis.exceptions.RedisError:
            # Ping failed, or connection is stale => re-init
            # Access the same logic as in create_app or re-create here
            from app import create_app

            app = create_app()
            current_app.redis = app.redis

    # If it still fails, let the error bubble up
    # or you could raise a custom error
    raise redis.exceptions.ConnectionError("Could not reconnect to Redis.")


# =================================
#    Chat Message Endpoints
# =================================


@chat_message_api_bp.route("/botchat/sessions", methods=["POST"])
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

    r = get_redis_connection()  # <-- Ensure valid Redis connection
    session_list_key = f"bot-sessions-{username}"
    # Check uniqueness (case-insensitive)
    existing_sessions = {s.lower() for s in r.smembers(session_list_key)}
    if session_name in existing_sessions:
        return jsonify(
            {
                "error": f"Session '{session_name}' already exists for user '{username}'."
            }
        ), 400

    # Add session to Redis
    r.sadd(session_list_key, session_name)

    return jsonify({"message": f"New session '{session_name}' created!"}), 201


@chat_message_api_bp.route("/botchat/sessions/<username>", methods=["GET"])
def get_sessions(username):
    """
    Return all session IDs for a given user.
    1) Check Redis first.
    2) If Redis is empty, fallback to PostgreSQL (chat_messages).
    3) Repopulate Redis so the next time we won't need the fallback.
    """
    session_list_key = f"bot-sessions-{username}"
    r = get_redis_connection()
    redis_sessions = r.smembers(session_list_key)

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


@chat_message_api_bp.route("/botchat/messages", methods=["POST"])
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


@chat_message_api_bp.route(
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


@chat_message_api_bp.route(
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


@chat_message_api_bp.route("/botchat/search/<username>", methods=["GET"])
def search_messages(username):
    """
    Fuzzy search across all chat sessions for the specified user in Redis only.
    If not found in Redis, optionally fallback to PostgreSQL (you decide).
    """
    query = request.args.get("query", "").strip().lower()
    if not query:
        return jsonify({"error": "No query provided."}), 400

    r = get_redis_connection()  # <-- Ensure a valid Redis connection
    session_list_key = f"bot-sessions-{username}"
    session_ids = r.smembers(session_list_key)
    results = []

    for session_id in session_ids:
        conversation_key = f"bot-{username}-{session_id}"
        messages_with_score = r.zrange(
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
    #         for rcd in records:
    #             results.append({
    #                 "session_id": rcd.session_id,
    #                 "sender": rcd.sender,
    #                 "text": rcd.message,
    #                 "time": rcd.timestamp.strftime("%Y-%m-%d %H:%M:%S")
    #             })

    return jsonify({"results": results, "query": query}), 200


# =================================
#   New Sync / Logout Endpoints
# =================================


@chat_message_api_bp.route(
    "/botchat/sync/<username>/<session_id>", methods=["POST"]
)
def sync_session(username, session_id):
    """
    Force a single session to be synced from Redis to PostgreSQL.
    """
    session_id = session_id.lower()
    sync_redis_session_to_postgres(username, session_id)
    return jsonify(
        {"message": f"Session '{session_id}' synced to Postgres."}
    ), 200


@chat_message_api_bp.route("/botchat/logout/<username>", methods=["POST"])
def logout_user(username):
    """
    Example endpoint that syncs all sessions for a user, then (optionally) clears them from Redis.
    """
    # 1) Sync each session individually
    r = get_redis_connection()  # <-- Use the helper to ensure valid Redis conn
    session_list_key = f"bot-sessions-{username}"
    session_ids = r.smembers(session_list_key)  # fetch sessions from Redis

    for session_id in session_ids:
        sync_redis_session_to_postgres(username, session_id)

    # 2) (Optional) Clear them from Redis if you want to remove them after syncing
    # for session_id in session_ids:
    #     conversation_key = f"bot-{username}-{session_id}"
    #     r.delete(conversation_key)
    # r.delete(session_list_key)

    return jsonify(
        {"message": f"All sessions for user '{username}' synced to Postgres."}
    ), 200


def update_active_user(user_id, last_seen=None, session_expiry=None):
    """
    Finds or creates an ActiveUser entry for user_id.
    Updates 'last_seen' and 'session_expiry' if provided.
    """
    active_user = ActiveUser.query.filter_by(user_id=user_id).first()
    if not active_user:
        active_user = ActiveUser(user_id=user_id)
        db.session.add(active_user)

    if last_seen:
        active_user.last_seen = last_seen
    if session_expiry:
        active_user.session_expiry = session_expiry

    db.session.commit()
    return active_user


@chat_message_api_bp.route("/botchat/update_session_expiry", methods=["POST"])
def update_session_expiry():
    """
    Update active-user record in DB with last_seen or session_expiry.
    """
    data = request.get_json()
    username = data.get("username")
    exp = data.get("exp")  # Typically seconds since epoch

    if not username or exp is None:
        return jsonify({"error": "username and exp are required."}), 400

    # Convert exp -> Python datetime
    from datetime import datetime

    last_seen_dt = datetime.fromtimestamp(datetime.timezone.utc)

    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({"error": f"User '{username}' not found."}), 404

    # Update or create the ActiveUser entry
    active_record = ActiveUser.query.filter_by(user_id=user.id).first()
    if not active_record:
        active_record = ActiveUser(user_id=user.id)
        db.session.add(active_record)

    active_record.last_seen = last_seen_dt
    db.session.commit()

    return jsonify({"status": "updated", "last_seen": str(last_seen_dt)}), 200


INACTIVITY_THRESHOLD = 15  # minutes


@chat_message_api_bp.task
def check_for_inactive_users():
    # 1) Calculate cutoff
    cutoff = datetime.now(datetime.timezone.utc) - timedelta(
        minutes=INACTIVITY_THRESHOLD
    )

    # 2) Query all active_user rows whose last_seen < cutoff
    inactive_records = ActiveUser.query.filter(
        ActiveUser.last_seen < cutoff
    ).all()

    # 3) For each user, sync sessions to Postgres
    for record in inactive_records:
        username = record.user.username
        # Approach A: direct sync all sessions for that user
        #    sync_redis_session_to_postgres(username, session_id=None)
        # or approach B: call the logout endpoint you already have:
        #    requests.post(f"{DB_SERVICE_URL}/botchat/logout/{username}")
        # (Note: careful with circular calls if you're inside the same service!)

        r = get_redis_connection()
        session_list_key = f"bot-sessions-{username}"
        session_ids = r.smembers(session_list_key)
        for s_id in session_ids:
            sync_redis_session_to_postgres(username, s_id)

        # 4) Optionally, remove them from Redis entirely
        # r.delete(session_list_key)
        # for s_id in session_ids:
        #     conversation_key = f"bot-{username}-{s_id}"
        #     r.delete(conversation_key)

        # 5) Remove or update the active_user record. (e.g. if you want to mark them as truly 'inactive')
        db.session.delete(record)

    db.session.commit()
