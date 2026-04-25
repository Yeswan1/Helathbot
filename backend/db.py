from pathlib import Path
import sqlite3
import hashlib
import hmac
import secrets
from typing import List, Dict, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "appointments.db"


def _hash_password(password: str, salt: str) -> str:
    """Derive a password hash using PBKDF2 for simple local auth."""
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100_000,
    )
    return derived.hex()


def _create_password_record(password: str) -> Dict[str, str]:
    salt = secrets.token_hex(16)
    return {
        "salt": salt,
        "password_hash": _hash_password(password, salt),
    }


def _get_connection() -> sqlite3.Connection:
    """Return a SQLite connection with row access by column name."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create the appointments table if it does not already exist."""
    with _get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS appointments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                appointment_date TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                password_salt TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()


def create_user(username: str, display_name: str, password: str) -> Dict:
    """Create a new user with a hashed password."""
    record = _create_password_record(password)
    with _get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO users (username, display_name, password_hash, password_salt)
            VALUES (?, ?, ?, ?)
            """,
            (username.lower().strip(), display_name.strip(), record["password_hash"], record["salt"]),
        )
        conn.commit()

    return {
        "id": cursor.lastrowid,
        "username": username.lower().strip(),
        "display_name": display_name.strip(),
    }


def get_user_by_username(username: str) -> Optional[Dict]:
    """Fetch a user record by username."""
    with _get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, username, display_name, password_hash, password_salt, created_at
            FROM users
            WHERE username = ?
            """,
            (username.lower().strip(),),
        ).fetchone()

    return dict(row) if row else None


def verify_user_password(username: str, password: str) -> Optional[Dict]:
    """Return the user record if the password matches."""
    user = get_user_by_username(username)
    if not user:
        return None

    expected = user["password_hash"]
    actual = _hash_password(password, user["password_salt"])
    if not hmac.compare_digest(expected, actual):
        return None

    return user


def create_appointment(name: str, appointment_date: str) -> Dict:
    """Insert a new appointment and return the created record."""
    with _get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO appointments (name, appointment_date)
            VALUES (?, ?)
            """,
            (name, appointment_date),
        )
        conn.commit()
        appointment_id = cursor.lastrowid

    return {
        "id": appointment_id,
        "name": name,
        "appointment_date": appointment_date,
    }


def list_appointments() -> List[Dict]:
    """Return all appointments ordered by appointment date."""
    with _get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, name, appointment_date, created_at
            FROM appointments
            ORDER BY appointment_date ASC
            """
        ).fetchall()

    return [dict(row) for row in rows]
