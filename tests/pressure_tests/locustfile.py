import hashlib
import time
import random
from locust import HttpUser, task, between
import uuid
from datetime import datetime, timezone

# Pool of mock usernames that already exist in your DB
USER_POOL = [f"mock-{i}" for i in range(1, 1001)]


def generate_global_hash(username):
    """
    Generates a pseudo-unique session ID using the username, current time, and UUID.
    We truncate the SHA-256 hash to 16 characters for readability.
    """
    unique_string = f"{username}-{time.time()}-{uuid.uuid4()}"
    return hashlib.sha256(unique_string.encode()).hexdigest()[:16]


class ChatMessageUser(HttpUser):
    # Wait randomly between 0.5s and 1.0s after each task
    wait_time = between(0.5, 1.0)

    def on_start(self):
        """
        Runs once when this Locust user is spawned.
        We pick a username, create a brand-new session, and store that session name.
        """
        self.username = random.choice(USER_POOL)
        self.session_name = (
            f"test_session_{generate_global_hash(self.username)}".lower()
        )

        # 1) Create the session exactly once here
        create_resp = self.client.post(
            "/botchat/sessions",
            json={
                "username": self.username,
                "session_name": self.session_name,
            },
            name="create_session",
        )
        if create_resp.status_code not in (200, 201):
            # If it fails because the session already exists, you could
            # regenerate a new session_name or just log it.
            print(f"❌ Failed to create session: {create_resp.text}")

    @task(1)
    def get_sessions_list(self):
        """
        Task to simulate the user retrieving all their sessions,
        e.g. when they first load the chatbot page.
        """
        get_resp = self.client.get(
            f"/botchat/sessions/{self.username}",
            name="get_sessions",
        )
        if get_resp.status_code == 200:
            data = get_resp.json()
            sessions = data.get("sessions", [])
            print(
                f"✅ [User={self.username}] has {len(sessions)} sessions. "
                f"(Looking for '{self.session_name}' among them...)"
            )
        else:
            print(f"❌ Failed to fetch sessions: {get_resp.text}")

    @task(3)
    def send_and_get_messages(self):
        """
        Task to send a new message to our pre-created session,
        then fetch and verify the messages in that session.
        """
        # 1) Send message
        message_resp = self.client.post(
            "/botchat/messages",
            json={
                "username": self.username,
                "session_id": self.session_name,
                "sender": self.username,
                "message": f"Hello from locust user {self.username}",
                "time": datetime.now(timezone.utc).isoformat(),
            },
            name="send_message",
        )
        if message_resp.status_code not in (200, 201):
            print(f"❌ Failed to send message: {message_resp.text}")

        # 2) Get messages
        get_resp = self.client.get(
            f"/botchat/messages/{self.username}/{self.session_name}",
            name="get_messages",
        )
        if get_resp.status_code == 200:
            data = get_resp.json()
            msg_count = len(data.get("messages", []))
            print(
                f"✅ [User={self.username}, Session={self.session_name}] "
                f"Fetched {msg_count} messages."
            )
        else:
            print(f"❌ Failed to get messages: {get_resp.text}")
