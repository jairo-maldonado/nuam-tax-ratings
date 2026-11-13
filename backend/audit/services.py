import json
from datetime import datetime, timezone
from pathlib import Path
from django.conf import settings
from pymongo import MongoClient

FALLBACK_FILE = Path(settings.BASE_DIR) / "audit_logs_nosql.json"


def get_audit_collection():
    db_name = getattr(settings, "MONGO_DB_NAME", None) or "nuam_audit"
    uris = [
        getattr(settings, "MONGO_URI", None),
        "mongodb://jairo:javier123@localhost:27017/?authSource=admin",
        "mongodb://admin:admin@localhost:27017/?authSource=admin",
        "mongodb://root:example@localhost:27017/?authSource=admin",
    ]
    for uri in uris:
        if not uri:
            continue
        try:
            client = MongoClient(uri, serverSelectionTimeoutMS=800)
            col = client[db_name]["upload_logs"]
            col.find_one()
            return col
        except Exception:
            continue
    return None


def log_upload_event(*, user, filename, status_str, created_count=0, errors=None):
    doc = {
        "username": getattr(user, "username", "anonymous"),
        "role": getattr(user, "role", "UNKNOWN"),
        "filename": filename,
        "status": status_str,
        "created_count": created_count,
        "error_count": len(errors) if errors else 0,
        "errors": errors or [],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    collection = get_audit_collection()
    if collection is not None:
        try:
            collection.insert_one(dict(doc))
            return
        except Exception:
            pass

    logs = []
    if FALLBACK_FILE.exists():
        try:
            logs = json.loads(FALLBACK_FILE.read_text(encoding="utf-8"))
        except Exception:
            logs = []
    logs.insert(0, doc)
    FALLBACK_FILE.write_text(json.dumps(logs[:100], indent=2), encoding="utf-8")


def fetch_audit_logs(limit=50):
    collection = get_audit_collection()
    if collection is not None:
        try:
            cursor = collection.find({}, {"_id": 0}).sort("timestamp", -1).limit(limit)
            return list(cursor)
        except Exception:
            pass

    if FALLBACK_FILE.exists():
        try:
            return json.loads(FALLBACK_FILE.read_text(encoding="utf-8"))[:limit]
        except Exception:
            return []
    return []