import os
import pytz
from datetime import datetime
from dotenv import load_dotenv

from apps.core.sandbox import SandboxClient

load_dotenv()
SANDBOX_API_KEY = os.getenv("SANDBOX_API_KEY")

def refresh_gst_token(current_token):
    # Determine log file path (in the same directory as the script)
    log_file_path = os.path.join(os.path.dirname(__file__), "cronlog.txt")

    sandbox_instance = SandboxClient()

    # Log token refresh attempt
    with open(log_file_path, "a") as log_file:
        log_file.write(
            f"[{datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%Y-%m-%d %H:%M:%S %Z')}] Attempting to refresh GST token\n"
        )

    sandbox_response = sandbox_instance._refresh_gst_jwt(current_token)

    # Log the raw sandbox response
    with open(log_file_path, "a") as log_file:
        log_file.write(
            f"[\n{datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%Y-%m-%d %H:%M:%S %Z')}] Sandbox response: {sandbox_response}\n"
        )

    if sandbox_response.get("code") == 200:
        new_token = sandbox_response.get("data").get("access_token")

        # Log successful token refresh
        with open(log_file_path, "a") as log_file:
            log_file.write(
                f"[{datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%Y-%m-%d %H:%M:%S %Z')}] Token refresh successful\n"
            )

        return new_token, 200

    # Log token refresh failure
    with open(log_file_path, "a") as log_file:
        log_file.write(
            f"[{datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%Y-%m-%d %H:%M:%S %Z')}] Token refresh failed. Returning current token.\n"
        )

    return current_token, 400


