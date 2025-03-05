import sys
import os
import argparse
from locust.main import main as locust_main

# Ensure the correct path to locustfile.py
LOCUSTFILE_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "locustfile.py")
)


def parse_arguments():
    """Parses command-line arguments for dynamic Locust configuration."""
    parser = argparse.ArgumentParser(
        description="Run Locust load tests with dynamic settings."
    )

    # Define arguments with default values
    parser.add_argument(
        "--host",
        type=str,
        default="http://localhost:port",
        help="Target host URL",
    )
    parser.add_argument(
        "--users", type=int, default=10, help="Number of concurrent users"
    )
    parser.add_argument(
        "--spawn-rate", type=int, default=1, help="User spawn rate per second"
    )
    parser.add_argument(
        "--run-time",
        type=str,
        default="5m",
        help="Total test duration (e.g., 5m, 1h)",
    )
    parser.add_argument(
        "--headless", action="store_true", help="Run Locust in headless mode"
    )

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_arguments()

    # Build sys.argv dynamically based on input parameters
    sys.argv = [
        "locust",
        "-f",
        LOCUSTFILE_PATH,
        "--host",
        args.host,
        "--users",
        str(args.users),
        "--spawn-rate",
        str(args.spawn_rate),
        "--run-time",
        args.run_time,
    ]

    # Add headless mode only if specified
    if args.headless:
        sys.argv.append("--headless")

    locust_main()
