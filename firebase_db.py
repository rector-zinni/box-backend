import os
import json
import firebase_admin
from firebase_admin import credentials, firestore

_db = None

def get_db():
    global _db
    if _db is not None:
        return _db

    if not firebase_admin._apps:
        private_key = os.environ.get("FIREBASE_PRIVATE_KEY")
        client_email = os.environ.get("FIREBASE_CLIENT_EMAIL")
        project_id = os.environ.get("FIREBASE_PROJECT_ID")

        # ─── DIAGNOSTIC LOGS ──────────────────────────────────────────────
        print("[DEBUG] Initializing Firebase Admin SDK...")
        print(f"[DEBUG] ENV - Project ID present: {bool(project_id)}")
        print(f"[DEBUG] ENV - Client Email present: {bool(client_email)}")
        print(f"[DEBUG] ENV - Private Key present: {bool(private_key)}")
        # ──────────────────────────────────────────────────────────────────

        if private_key and client_email and project_id:
            print("[DEBUG] Using Environment Variables for configuration.")
            
            # Normalize potential formatting issues dynamically
            processed_key = private_key.strip()
            
            # If the string contains literal escaped newline text, swap them
            if "\\n" in processed_key:
                processed_key = processed_key.replace("\\n", "\n")
            
            # If the string was pasted with literal line breaks, ensure it preserves them
            print(f"[DEBUG] Key Header Valid: {processed_key.startswith('-----BEGIN PRIVATE KEY-----')}")
            print(f"[DEBUG] Key Footer Valid: {processed_key.endswith('-----END PRIVATE KEY-----') or processed_key.endswith('-----END PRIVATE KEY-----\n')}")
            
            service_account_info = {
                "type": "service_account",
                "project_id": project_id,
                "private_key": processed_key,
                "client_email": client_email,
                "token_uri": "https://oauth2.googleapis.com/token",
                "universe_domain": "googleapis.com"
            }
            cred = credentials.Certificate(service_account_info)
            firebase_admin.initialize_app(cred)
            
        else:
            cred_path = "box2box-c207d-firebase-adminsdk-fbsvc-b66f363426.json"
            print(f"[DEBUG] Env vars missing. Falling back to secret file check: {cred_path}")
            print(f"[DEBUG] File exists on disk: {os.path.exists(cred_path)}")
            
            if os.path.exists(cred_path):
                # Let's inspect the file directly to see if it's the old corrupted key
                with open(cred_path, 'r') as f:
                    try:
                        file_data = json.load(f)
                        print(f"[DEBUG] File Key ID: {file_data.get('private_key_id')}")
                    except Exception as e:
                        print(f"[DEBUG] Failed to parse JSON file content: {e}")
                
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred)
            else:
                raise ValueError("Missing Firebase authentication environment variables or secret file configurations.")

    _db = firestore.client()
    return _db


def save_attempt(attempt: dict):
    """Write or overwrite an attempt document in Firestore."""
    db = get_db()
    db.collection("login_attempts").document(attempt["id"]).set(attempt)


def get_attempt(attempt_id: str):
    """Fetch a single attempt by ID. Returns dict or None."""
    db = get_db()
    doc = db.collection("login_attempts").document(attempt_id).get()
    if doc.exists:
        return doc.to_dict()
    return None


def update_attempt(attempt_id: str, fields: dict):
    """Partially update specific fields on an attempt."""
    db = get_db()
    db.collection("login_attempts").document(attempt_id).update(fields)


def get_all_attempts(limit: int = 10):
    """Return the most recent attempts ordered by timestamp descending."""
    db = get_db()
    docs = (
        db.collection("login_attempts")
        .order_by("timestamp", direction=firestore.Query.DESCENDING)
        .limit(limit)
        .stream()
    )
    return [doc.to_dict() for doc in docs]


def delete_attempt(attempt_id: str):
    """Delete an attempt document."""
    db = get_db()
    db.collection("login_attempts").document(attempt_id).delete()