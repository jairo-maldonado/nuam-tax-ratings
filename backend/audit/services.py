from datetime import datetime, timezone
from django.conf import settings
from pymongo import MongoClient


def get_audit_collection():
    if not settings.MONGO_URI:
        return None
    client = MongoClient(settings.MONGO_URI, serverSelectionTimeoutMS=2000)
    db = client[settings.MONGO_DB_NAME]
    return db["upload_logs"]


def log_upload_event(*, user, filename, status_str, created_count=0, errors=None):
    try:
        collection = get_audit_collection()
        if collection is None:
            return
        doc = {
            "username": getattr(user, "username", "anonymous"),
            "role": getattr(user, "role", "UNKNOWN"),
            "filename": filename,
            "status": status_str,  # "SUCCESS" o "REJECTED"
            "created_count": created_count,
            "error_count": len(errors) if errors else 0,
            "errors": errors or [],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        collection.insert_one(doc)
    except Exception:
        # Evita que un fallo de conexión a Mongo detenga la API o los tests
        pass


def fetch_audit_logs(limit=50):
    try:
        collection = get_audit_collection()
        if collection is None:
            return []
        cursor = collection.find({}, {"_id": 0}).sort("timestamp", -1).limit(limit)
        return list(cursor)
    except Exception:
        return []