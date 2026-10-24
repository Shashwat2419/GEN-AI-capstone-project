"""Trip persistence using the standard-library sqlite3 module.

Zero external database dependencies: a single local file ``data/trips.db`` is
created on first use.  (On Streamlit Community Cloud the filesystem is
ephemeral, so saved trips last until the app restarts - perfect for a demo.
Swap this module for Supabase later without touching the UI.)
"""
import json
import os
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DB_PATH = os.path.join(DB_DIR, "trips.db")


class StorageError(Exception):
    pass


def _connect() -> sqlite3.Connection:
    try:
        os.makedirs(DB_DIR, exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute(
            """CREATE TABLE IF NOT EXISTS trips (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   name TEXT NOT NULL,
                   destination TEXT NOT NULL,
                   num_days INTEGER NOT NULL,
                   created_at TEXT NOT NULL,
                   updated_at TEXT NOT NULL,
                   payload TEXT NOT NULL)"""
        )
        return conn
    except (OSError, sqlite3.Error) as exc:
        raise StorageError("Could not open the local trip database: %s" % exc)


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def save_trip(name: str, itinerary: Dict, trip_id: Optional[int] = None) -> int:
    """Insert a new trip, or update ``trip_id`` when given. Returns the row id."""
    payload = json.dumps(itinerary)
    try:
        with _connect() as conn:
            if trip_id:
                cur = conn.execute(
                    "UPDATE trips SET name=?, destination=?, num_days=?, updated_at=?, payload=? WHERE id=?",
                    (name, itinerary["destination"], len(itinerary["days"]), _now(), payload, trip_id))
                if cur.rowcount:
                    return trip_id
            cur = conn.execute(
                "INSERT INTO trips (name, destination, num_days, created_at, updated_at, payload) "
                "VALUES (?,?,?,?,?,?)",
                (name, itinerary["destination"], len(itinerary["days"]), _now(), _now(), payload))
            return int(cur.lastrowid)
    except sqlite3.Error as exc:
        raise StorageError("Could not save the trip: %s" % exc)


def list_trips() -> List[Dict]:
    try:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT id, name, destination, num_days, created_at, updated_at "
                "FROM trips ORDER BY updated_at DESC, id DESC").fetchall()
        return [dict(r) for r in rows]
    except sqlite3.Error as exc:
        raise StorageError("Could not read saved trips: %s" % exc)


def load_trip(trip_id: int) -> Dict:
    try:
        with _connect() as conn:
            row = conn.execute("SELECT payload FROM trips WHERE id=?", (trip_id,)).fetchone()
    except sqlite3.Error as exc:
        raise StorageError("Could not load the trip: %s" % exc)
    if row is None:
        raise StorageError("That trip no longer exists.")
    return json.loads(row["payload"])


def delete_trip(trip_id: int) -> None:
    try:
        with _connect() as conn:
            conn.execute("DELETE FROM trips WHERE id=?", (trip_id,))
    except sqlite3.Error as exc:
        raise StorageError("Could not delete the trip: %s" % exc)
