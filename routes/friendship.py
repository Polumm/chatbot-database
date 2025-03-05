from flask import Blueprint, request, jsonify

from datetime import datetime, timezone

from models import db
from models.user import User
from models.friendship import Friendship


friendship_api_bp = Blueprint("friendship", __name__)


# =================================
#       Friendship Endpoints
# =================================


@friendship_api_bp.route("/friends/request", methods=["POST"])
def send_friend_request():
    data = request.json
    user_id = data.get("user_id")
    friend_id = data.get("friend_id")

    # Prevent self-friendship
    if user_id == friend_id:
        return jsonify({"message": "You cannot add yourself as a friend"}), 400

    # Check if friendship already exists
    existing_friendship = Friendship.query.filter(
        ((Friendship.user_id == user_id) & (Friendship.friend_id == friend_id)) |
        ((Friendship.user_id == friend_id) & (Friendship.friend_id == user_id))
    ).first()

    if existing_friendship:
        return jsonify({"message": "Friend request already exists"}), 400

    # Create new friendship request
    friendship = Friendship(user_id=user_id, friend_id=friend_id, status="pending")
    db.session.add(friendship)
    db.session.commit()

    return jsonify({"message": "Friend request sent successfully"}), 201

@friendship_api_bp.route("/friends/requests", methods=["GET"])
def get_friend_requests():
    user_id = request.args.get("user_id", type=int)

    if not user_id:
        return jsonify({"error": "Invalid user ID"}), 400

    # Get all pending friend requests where user_id is the recipient
    friend_requests = Friendship.query.filter_by(
        friend_id=user_id, status="pending"
    ).all()

    requests_list = [
        {
            "friendship_id": req.id,
            "from_user_id": req.user_id,
            "from_username": User.query.get(req.user_id).username,
        }
        for req in friend_requests
    ]

    return jsonify({"requests": requests_list}), 200

@friendship_api_bp.route("/friends/accept", methods=["PUT"])
def accept_friend_request():
    data = request.json
    friendship_id = data.get("friendship_id")

    # Update the friendship status to 'accepted'
    friendship = Friendship.query.get(friendship_id)
    if not friendship:
        return jsonify({"message": "Friendship not found"}), 404

    friendship.status = "accepted"
    friendship.updated_at = datetime.now(timezone.utc)
    db.session.commit()

    return jsonify({"message": "Friend request accepted"}), 200

@friendship_api_bp.route("/friends/remove", methods=["DELETE"])
def remove_friendship():
    data = request.json
    user_id = data.get("user_id")
    friend_id = data.get("friend_id")

    # Find the friendship in either direction
    friendship = Friendship.query.filter(
        ((Friendship.user_id == user_id) & (Friendship.friend_id == friend_id)) |
        ((Friendship.user_id == friend_id) & (Friendship.friend_id == user_id))
    ).first()

    if not friendship:
        return jsonify({"message": "Friendship not found"}), 404

    db.session.delete(friendship)
    db.session.commit()

    return jsonify({"message": "Friend removed successfully"}), 200

@friendship_api_bp.route("/friends/list", methods=["GET"])
def get_friend_list():
    user_id = request.args.get("user_id", type=int)

    if not user_id:
        return jsonify({"error": "Invalid user ID"}), 400

    # Fetch accepted friendships where the user is either side
    friendships = Friendship.query.filter(
        ((Friendship.user_id == user_id) | (Friendship.friend_id == user_id)),
        Friendship.status == "accepted"
    ).all()

    friend_ids = set()
    for friendship in friendships:
        if friendship.user_id == user_id:
            friend_ids.add(friendship.friend_id)
        else:
            friend_ids.add(friendship.user_id)

    # Retrieve user details for friends
    friends = User.query.filter(User.id.in_(friend_ids)).all()
    friend_list = [{"id": friend.id, "username": friend.username} for friend in friends]

    return jsonify({"friends": friend_list}), 200