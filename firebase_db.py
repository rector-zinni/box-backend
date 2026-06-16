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
        service_account_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip()
        if not service_account_json:
            raise ValueError("FIREBASE_SERVICE_ACCOUNT_JSON environment variable is not set.")
        service_account_info = json.loads(service_account_json)
        cred = credentials.Certificate(service_account_info)
        firebase_admin.initialize_app(cred)

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