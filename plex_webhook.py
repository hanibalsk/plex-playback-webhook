import json
import logging
import os
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler

import pytz
import requests
from flask import Flask, request, jsonify

from config_loader import load_config

app = Flask(__name__)

# Load configuration from the environment variable CONFIG_PATH or default to "config.yml"
config_path = os.getenv("CONFIG_PATH", "config.yaml")
config = load_config(config_path)

# Configure logging
log_file = config.get('log_file', '/data/logging.log')

# Create logfile if it does not exist
if not os.path.exists(log_file):
    with open(log_file, "w") as f:
        f.write("")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set up logging to console and log file
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
file_handler = RotatingFileHandler(log_file, maxBytes=5 * 1024 * 1024, backupCount=3)
file_handler.setLevel(logging.INFO)

# Define the logging format and add handlers to the logger
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
file_handler.setFormatter(formatter)

logger.addHandler(console_handler)
logger.addHandler(file_handler)

# Define the webhook URLs for play and pause/stop events
webhook_play_resume = config['webhooks']['play_resume']
webhook_pause_stop = config['webhooks']['pause_stop']
devices = config['webhooks']['devices']
webhook_method = config['webhooks'].get('method', 'POST').upper()  # Default to POST if not specified

# Configure login credentials and token variables
auth_url = config['webhooks'].get('auth_url', 'http://localhost:8000/login')
auth_password = config['webhooks'].get('auth_password')  # Remove default password
auth_token = None


def parse_time_string(time_string, sunrise, sunset):
    """
    Parse the time string into a datetime object based on sunrise or sunset.
    """
    if time_string == "sunrise":
        return sunrise
    elif time_string == "sunset":
        return sunset
    else:
        # Assuming format "HH:mm"
        hour, minute = map(int, time_string.split(":"))
        return datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)


def is_within_schedule():
    """
    Check if the current time is within the defined schedule based on config.
    """
    if not config.get("schedule", {}).get("enabled", False):
        return True  # No schedule restriction enabled, always allow

    try:
        api_url = config["sunlight"]["api_url"]
        latitude = config["sunlight"]["latitude"]
        longitude = config["sunlight"]["longitude"]

        # Fetch sunlight data from API
        response = requests.get(api_url, params={"lat": latitude, "lng": longitude, "formatted": 0})
        response.raise_for_status()
        data = response.json()["results"]

        # Parse sunrise and sunset times
        sunrise = datetime.fromisoformat(data["sunrise"])
        sunset = datetime.fromisoformat(data["sunset"])

        # Apply offset
        sunrise_offset = timedelta(minutes=config["sunlight"].get("sunrise_offset_minutes", 0))
        sunset_offset = timedelta(minutes=config["sunlight"].get("sunset_offset_minutes", 0))

        local_tz = pytz.timezone("Europe/Bratislava")
        now = datetime.now(tz=local_tz)

        # Adjust sunrise and sunset times based on offset
        sunrise_local = (sunrise + sunrise_offset).astimezone(local_tz)
        sunset_local = (sunset + sunset_offset).astimezone(local_tz)

        # Parse start and end times from the schedule
        schedule = config.get("schedule", {})
        start_time_str = schedule.get("start", "00:00")
        end_time_str = schedule.get("end", "23:59")

        start_time = parse_time_string(start_time_str, sunrise_local, sunset_local).astimezone(local_tz)
        end_time = parse_time_string(end_time_str, sunrise_local, sunset_local).astimezone(local_tz)

        # Determine if the current time falls within the start and end time
        if start_time <= now <= end_time:
            return True
        elif start_time > end_time:  # Overnight schedule (e.g., 21:00 to 06:00)
            return now >= start_time or now <= end_time
        else:
            return False

    except requests.RequestException as e:
        logger.error(f"Failed to fetch sunlight data: {e}")
        return False


def login():
    """
    Authenticate to obtain a token by sending a POST request to the auth_url.
    """
    global auth_token
    if not auth_password:
        # Skip authentication if no password is provided
        logger.info("No password provided, skipping authentication.")
        return
    try:
        response = requests.post(auth_url, json={"password": auth_password})
        response.raise_for_status()
        auth_token = response.text.strip()
        if not auth_token:
            logger.error("Failed to retrieve token from login response")
    except requests.exceptions.RequestException as e:
        logger.error(f"Login request failed: {e}")


@app.route('/plex-webhook', methods=['POST'])
def plex_webhook():
    """
    Handle incoming webhook requests from Plex.
    Depending on the content type, parse the request data and trigger the appropriate webhook.
    """

    if not is_within_schedule():
        return jsonify({"status": "inactive due to schedule settings"}), 403

    # Log the content type for debugging
    logger.info("Content-Type: %s", request.content_type)

    # Handle different content types explicitly
    if request.content_type:
        if request.content_type.startswith('multipart/form-data'):
            # Extract the 'payload' field from the form data
            payload = request.form.get('payload')
            if payload:
                try:
                    data = json.loads(payload)  # Parse the JSON payload
                except json.JSONDecodeError:
                    return jsonify({"error": "Invalid JSON payload"}), 400
            else:
                return jsonify({"error": "No payload found"}), 400
        elif request.content_type == 'application/json':
            # Parse JSON directly from the request body
            data = request.get_json(force=True, silent=True)
            if data is None:
                return jsonify({"error": "Invalid JSON format"}), 400
        else:
            return jsonify({"error": "Unsupported Media Type"}), 415
    else:
        return jsonify({"error": "Missing Content-Type"}), 400

    # Extract event type and device from the incoming webhook payload
    event_type = data.get('event')
    # Get device name, default to 'Unknown Device' if missing
    device_name = data.get('Player', {}).get('title', 'Unknown Device')

    # Check if the event matches any of the target devices
    if device_name in devices:
        if event_type in ["media.play", "media.resume"]:
            # Trigger webhook for play or resume events
            result, code = trigger_webhook(webhook_play_resume, event_type, device_name)
            return result, code
        elif event_type in ["media.pause", "media.stop"]:
            # Trigger webhook for pause or stop events
            result, code = trigger_webhook(webhook_pause_stop, event_type, device_name)
            return result, code
    else:
        logger.info(f"Device {device_name} not in the list of devices to trigger webhooks for.")

    return jsonify({"status": "success"}), 200


def trigger_webhook(url, event_type, device_name):
    """
    Send a request to the specified webhook URL based on the configured method (GET or POST).
    Include the event type and device name in the request payload or parameters.
    """
    logging.info(f"Triggering webhook: {url} with event: {event_type}, device: {device_name}")
    global auth_token
    if auth_password and not auth_token:
        login()  # Authenticate if the token is not set and a password is provided

    headers = {}
    if auth_token:
        headers['Authorization'] = f'Bearer {auth_token}'  # Include the authorization token if available
    try:
        logger.info(f"Triggering webhook: {url} with event: {event_type}, device: {device_name}")
        if webhook_method == 'POST':
            # Send a POST request with JSON payload
            logging.info(
                f"Sending POST request to {url} Triggered by Plex event: {event_type} for device: {device_name}")
            response = requests.post(url, headers=headers,
                                     json={"webhook_message": f"Triggered by Plex event: {event_type}", "plex_device": device_name})
        elif webhook_method == 'GET':
            # Send a GET request with query parameters
            logging.info(
                f"Sending GET request to {url} Triggered by Plex event: {event_type} for device: {device_name}")
            response = requests.get(url, headers=headers,
                                    params={"webhook_message": f"Triggered by Plex event: {event_type}", "plex_device": device_name})
        else:
            logger.error(f"Unsupported webhook method: {webhook_method}")
            return jsonify({"status": "error", "message": "Unsupported webhook method"}), 400
        response.raise_for_status()
        return jsonify({"status": "success", "event": event_type, "device": device_name}), 200
    except requests.exceptions.RequestException as e:
        if response is not None and response.status_code == 403:  # Forbidden error
            logger.warning("Forbidden error encountered. Resetting auth token.")
            auth_token = None  # Reset the token if forbidden
        logger.error(f"Failed to trigger webhook: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == '__main__':
    # Set debug mode and port from environment variables
    debug_mode = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    port = int(os.getenv('FLASK_PORT', 4995))
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
