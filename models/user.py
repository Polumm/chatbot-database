from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from . import db


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(128), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)

    @property
    def password(self):
        # Prevent reading the password attribute
        raise AttributeError("password is not a readable attribute")

    @password.setter
    def password(self, password):
        # Automatically hash on setting
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password):
        # Check hashed password
        return check_password_hash(self.password_hash, password)
