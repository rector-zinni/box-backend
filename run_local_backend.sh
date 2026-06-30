#!/bin/bash
# Script to run the Flask backend locally with the Firebase Service Account credentials loaded.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
KEY_FILE="$SCRIPT_DIR/box2box-c207d-firebase-adminsdk-fbsvc-b66f363426.json"

if [ ! -f "$KEY_FILE" ]; then
    echo "Error: Firebase credentials file not found at $KEY_FILE"
    exit 1
fi

# Load the JSON file into the environment variable
export FIREBASE_SERVICE_ACCOUNT_JSON=$(cat "$KEY_FILE")
export FLASK_PORT=5000
export FLASK_ENV=development

echo "Starting local Flask server with Firebase credentials..."
python3 "$SCRIPT_DIR/server.py"
