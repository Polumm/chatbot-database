from sqlalchemy import text  # Import text from SQLAlchemy
import sys
import os

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
)

from app import create_app, db


app = create_app()
with app.app_context():

    def rollback_test_data():
        try:
            # Ensure raw SQL queries use text()
            db.session.execute(
                text(
                    "DELETE FROM chat_messages WHERE session_id LIKE 'test_session_%';"
                )
            )
            db.session.execute(
                text("DELETE FROM users WHERE username LIKE 'mock-%';")
            )
            db.session.commit()
            print("✅ Test data successfully rolled back.")
        except Exception as e:
            db.session.rollback()
            print(f"❌ Rollback failed: {e}")

    rollback_test_data()
