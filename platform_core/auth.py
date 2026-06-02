"""User account auth (sign-up / login / password reset) over the doc dict.

Per the owner's decision (PLAN.md §6.2): site accounts with username + password.
Password hashing is **SHA-256**, kept identical to the legacy app so the 16
existing accounts in ``auction_data.json`` keep working after migration.

These are pure functions on the in-memory ``{"users": {...}, "rooms": {...}}``
document — the caller persists via the repository/store.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

MIN_PASSWORD_LEN = 4  # legacy rule


class AuthError(Exception):
    """Sign-up / login / reset failed (message is user-facing)."""


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def sign_up(doc: dict, username: str, password: str, confirm: str | None = None) -> dict:
    """Create a new account. Returns the new user record. Raises AuthError."""
    username = (username or "").strip()
    users = doc.setdefault("users", {})
    if not username or not password:
        raise AuthError("Username and password are required.")
    if len(password) < MIN_PASSWORD_LEN:
        raise AuthError(f"Password must be at least {MIN_PASSWORD_LEN} characters.")
    if confirm is not None and password != confirm:
        raise AuthError("Passwords do not match.")
    if username in users:
        raise AuthError("Username already taken. Choose another.")
    record = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "password_hash": hash_password(password),
        "rooms_created": [],
        "rooms_joined": [],
    }
    users[username] = record
    return record


def log_in(doc: dict, username: str, password: str) -> str:
    """Verify credentials. Returns the username on success, else raises AuthError."""
    username = (username or "").strip()
    users = doc.get("users", {})
    if username not in users:
        raise AuthError("Username not found. Please sign up first.")
    if users[username].get("password_hash") != hash_password(password):
        raise AuthError("Incorrect password.")
    return username


def reset_password(doc: dict, username: str, room_code: str, new_password: str) -> None:
    """Reset a password, verified by membership of a room the user belongs to."""
    username = (username or "").strip()
    room_code = (room_code or "").strip().upper()
    users = doc.get("users", {})
    rooms = doc.get("rooms", {})
    if username not in users:
        raise AuthError("Username not found.")
    if len(new_password) < MIN_PASSWORD_LEN:
        raise AuthError(f"Password must be at least {MIN_PASSWORD_LEN} characters.")
    if room_code not in rooms:
        raise AuthError("Invalid room code.")
    if username not in rooms[room_code].get("members", []):
        raise AuthError("You are not a member of that room. Verification failed.")
    users[username]["password_hash"] = hash_password(new_password)
