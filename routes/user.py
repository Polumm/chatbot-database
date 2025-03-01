from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash

from models import db
from models.user import User


user_api_bp = Blueprint("user", __name__)


# =================================
#       User Endpoints
# =================================


@user_api_bp.route("/users", methods=["POST"])
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


@user_api_bp.route("/users/<username>", methods=["GET"])
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


@user_api_bp.route("/users/<username>", methods=["DELETE"])
def delete_user(username):
    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({"error": "User not found."}), 404
    db.session.delete(user)
    db.session.commit()
    return jsonify({"message": "User deleted successfully!"})
