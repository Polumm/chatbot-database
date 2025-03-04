import sys
import os

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
)

from app import create_app, db

from models.user import User

# Create app context
app = create_app()
with app.app_context():

    def create_mock_users():
        users = []  # List to store user objects for bulk insert
        for i in range(1, 1001):  # Create users from mock-1 to mock-1000
            username = f"mock-{i}"
            password = "password123"  # Default password for testing

            user = User(username=username)  # Create user instance
            user.password = password  # This hashes the password

            users.append(user)  # Add to the list

        # Bulk insert for efficiency
        db.session.bulk_save_objects(users)
        db.session.commit()
        print(f"✅ Successfully created {len(users)} mock users.")

    # Run the function
    create_mock_users()
