from datetime import datetime, timezone
from flask import Blueprint, request, jsonify, current_app
from sqlalchemy.exc import SQLAlchemyError
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
from routes import sync_redis_session_to_postgres


chat_message_api_bp = Blueprint("chat_message", __name__)


def get_redis_connection():
    """
    Returns a valid Redis connection. If the existing connection
    is stale/closed, re-initialize and retry once.
    """
    for attempt in range(2):
        try:
            current_app.redis.ping()
            print("Debug: Successfully pinged")
            # If ping succeeds, return it
            return current_app.redis
        except redis.exceptions.RedisError:
            print(
                f"Debug: Unsuccessfully pinged, re-initialising redis client, {attempt = }"
            )
            # Re-init just the Redis client, NOT the entire Flask app
            current_app.redis = redis.Redis(
                host=current_app.config["REDIS_HOST"],
                port=current_app.config["REDIS_PORT"],
                db=current_app.config["REDIS_DB"],
                decode_responses=current_app.config["REDIS_DECODE_RESPONSES"],
                socket_keepalive=True,
                retry_on_timeout=True,
                health_check_interval=30,
                socket_connect_timeout=2,
            )
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
    1) Check Redis first with a timeout limit.
    2) If Redis is empty or times out, fallback to PostgreSQL (chat_messages).
    3) Repopulate Redis for faster future requests.
    """
    session_list_key = f"bot-sessions-{username}"
    r = get_redis_connection()
    redis_timeout_limit = 1  # Max 1 seconds for Redis to respond

    session_ids = []

    try:
        # Time-bound Redis request to avoid cold start delay
        start_time = time.time()
        redis_sessions = r.smembers(session_list_key)
        elapsed_time = time.time() - start_time

        if elapsed_time > redis_timeout_limit:
            raise redis.exceptions.TimeoutError(
                f"Redis request took too long ({elapsed_time:.2f}s)"
            )

        if redis_sessions:
            session_ids = sorted(list(redis_sessions))
            current_app.logger.info(
                f"Fetched sessions from Redis for {username} in {elapsed_time:.2f}s"
            )

    except (
        redis.exceptions.ConnectionError,
        redis.exceptions.TimeoutError,
    ) as e:
        current_app.logger.warning(
            f"Redis unavailable or slow for {username}, falling back to PostgreSQL: {str(e)}"
        )

    if not session_ids:
        # Fallback to PostgreSQL
        user_id = get_user_id(username)
        if not user_id:
            return jsonify({"sessions": []}), 200

        try:
            # Query distinct session_ids from chat_messages
            session_records = (
                db.session.query(ChatMessage.session_id)
                .filter_by(user_id=user_id)
                .distinct()
                .all()
            )
            session_ids = [row.session_id for row in session_records]

            # Repopulate Redis so future requests are faster
            for sid in session_ids:
                r.sadd(session_list_key, sid)

            current_app.logger.info(
                f"Repopulated Redis with sessions for {username}"
            )

        except SQLAlchemyError as e:
            current_app.logger.error(
                f"Database query error for {username}: {str(e)}"
            )
            return jsonify({"error": "Database error"}), 500

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

    last_seen_dt = datetime.now(timezone.utc)

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
