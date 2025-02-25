from flask import request, jsonify
from models import db, User, Friendship
from datetime import datetime, timezone


def init_routes(app):
    @app.route("/api/friends/request", methods=["POST"])
    def send_friend_request():
        data = request.json
        user_id = data.get("user_id")
        friend_id = data.get("friend_id")

        # Check if the friendship already exists
        existing_friendship = Friendship.query.filter_by(
            user_id=user_id, friend_id=friend_id
        ).first()
        if existing_friendship:
            return jsonify(
                {"message": "Friend request already sent or exists"}
            ), 400

        # Create a new friendship
        friendship = Friendship(
            user_id=user_id, friend_id=friend_id, status="pending"
        )
        db.session.add(friendship)
        db.session.commit()

        return jsonify({"message": "Friend request sent successfully"}), 201

    @app.route("/api/friends/accept", methods=["PUT"])
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

    @app.route("/api/friends/list", methods=["GET"])
    def get_friend_list():
        user_id = request.args.get("user_id")

        # TODO: add error handling
        # try:
        #     user_id = int(user_id)
        # except ValueError:
        #     return jsonify({"error": f"Invalid user id!"}), 500
        user_id = int(user_id)

        # Get all accepted friendships
        friendships = Friendship.query.filter(
            (Friendship.user_id == user_id)
            | (Friendship.friend_id == user_id),
            Friendship.status == "accepted",
        ).all()

        # Extract friend IDs
        friend_ids = []
        for friendship in friendships:
            if friendship.user_id == user_id:
                friend_ids.append(friendship.friend_id)
            else:
                friend_ids.append(friendship.user_id)

        # Get friend details
        friends = User.query.filter(User.id.in_(friend_ids)).all()
        friend_list = [
            {"id": friend.id, "username": friend.username}
            for friend in friends
        ]

        return jsonify({"friends": friend_list}), 200
