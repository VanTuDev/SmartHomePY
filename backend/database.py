"""
database.py - MongoDB (pymongo sync)
"""
import os
import certifi
from datetime import datetime
from bson import ObjectId
from pymongo import MongoClient, DESCENDING
from dotenv import load_dotenv

load_dotenv()

_client: MongoClient = None
_db = None


def connect():
    global _client, _db
    uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    _client = MongoClient(uri, tlsCAFile=certifi.where())
    _db = _client[os.getenv("MONGODB_DB_NAME", "smarthome")]
    _db.users.create_index("name")
    _db.access_logs.create_index("timestamp")
    _db.fall_logs.create_index("timestamp")
    print("Da ket noi MongoDB.")


def close():
    global _client, _db
    if _client:
        _client.close()
        _client = None
        _db = None


def _ser(doc: dict) -> dict:
    if doc and "_id" in doc:
        doc["_id"] = str(doc["_id"])
    return doc


# ── Users ──────────────────────────────────────────────────────────────────────

def create_user(name: str, role: str, face_features: list) -> dict:
    doc = {
        "name": name,
        "role": role,
        "face_features": face_features,
        "created_at": datetime.utcnow(),
    }
    result = _db.users.insert_one(doc)
    doc["_id"] = str(result.inserted_id)
    return doc


def get_all_users() -> list:
    return [_ser(d) for d in _db.users.find({}, {"face_features": 0})]


def get_users_with_features() -> list:
    return [_ser(d) for d in _db.users.find({})]


def delete_user(user_id: str) -> bool:
    result = _db.users.delete_one({"_id": ObjectId(user_id)})
    return result.deleted_count > 0


# ── Access Logs ────────────────────────────────────────────────────────────────

def create_access_log(person_name: str, action: str, snapshot_b64: str, is_allowed: bool) -> dict:
    doc = {
        "timestamp": datetime.utcnow(),
        "person_name": person_name,
        "action": action,
        "snapshot_b64": snapshot_b64,
        "is_allowed": is_allowed,
    }
    result = _db.access_logs.insert_one(doc)
    doc["_id"] = str(result.inserted_id)
    return doc


def get_access_logs(limit: int = 50) -> list:
    docs = list(
        _db.access_logs.find({}, {"snapshot_b64": 0})
        .sort("timestamp", DESCENDING)
        .limit(limit)
    )
    for d in docs:
        d["timestamp"] = d["timestamp"].isoformat()
        _ser(d)
    return docs


# ── Fall Logs ──────────────────────────────────────────────────────────────────

def create_fall_log(image_b64: str, timestamp_str: str) -> dict:
    doc = {
        "timestamp": datetime.utcnow(),
        "timestamp_str": timestamp_str,
        "image_b64": image_b64,
        "status": "da_canh_bao",
    }
    result = _db.fall_logs.insert_one(doc)
    doc["_id"] = str(result.inserted_id)
    return doc


def get_fall_logs(limit: int = 50) -> list:
    docs = list(
        _db.fall_logs.find({}, {"image_b64": 0})
        .sort("timestamp", DESCENDING)
        .limit(limit)
    )
    for d in docs:
        d["timestamp"] = d["timestamp"].isoformat()
        _ser(d)
    return docs
