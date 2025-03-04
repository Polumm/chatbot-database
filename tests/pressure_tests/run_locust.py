import sys
import os
from locust.main import main as locust_main

# Ensure the correct path to locustfile.py
LOCUSTFILE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "locustfile.py"))

if __name__ == "__main__":
    sys.argv = [
        "locust",
        "-f", LOCUSTFILE_PATH,  # Explicit path to locustfile.py
        "--host", "url",
        "--users", "1",
        "--spawn-rate", "1",
        "--run-time", "5m",
        # "--headless",
    ]
    locust_main()
