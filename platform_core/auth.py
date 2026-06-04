"""User account auth (sign-up / login / password reset) over the doc dict.

Per the owner's decision (PLAN.md §6.2): site accounts with username + password.

Passwords are stored as **salted PBKDF2-HMAC-SHA256** hashes
(``pbkdf2_sha256$<rounds>$<salt_hex>$<hash_hex>``). Legacy accounts were stored as
plain unsalted SHA-256 hex; ``verify_password`` still accepts those, and ``log_in``
transparently re-hashes a legacy password to PBKDF2 on the next successful login, so
existing users migrate automatically with no lockout.

These are pure functions on the in-memory ``{"users": {...}, "rooms": {...}}``
document — the caller persists via the repository/store.
"""

from __future__ import annotations

import binascii
import hashlib
import hmac
import os
from datetime import datetime, timezone

MIN_PASSWORD_LEN = 4  # legacy rule
_PBKDF2_ROUNDS = 200_000
_PBKDF2_PREFIX = "pbkdf2_sha256$"


class AuthError(Exception):
    """Sign-up / login / reset failed (message is user-facing)."""


def hash_password(password: str) -> str:
    """Salted PBKDF2-HMAC-SHA256 hash for storage."""
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", (password or "").encode(), salt, _PBKDF2_ROUNDS)
    return (f"{_PBKDF2_PREFIX}{_PBKDF2_ROUNDS}$"
            f"{binascii.hexlify(salt).decode()}${binascii.hexlify(dk).decode()}")


def needs_rehash(stored: str) -> bool:
    """True if the stored hash is a legacy (unsalted SHA-256) hash."""
    return not (stored or "").startswith(_PBKDF2_PREFIX)


def verify_password(stored: str, password: str) -> bool:
    """Check a password against a stored hash (PBKDF2 or legacy SHA-256)."""
    if not stored:
        return False
    if stored.startswith(_PBKDF2_PREFIX):
        try:
            _, rounds, salt_hex, hash_hex = stored.split("$")
            dk = hashlib.pbkdf2_hmac("sha256", (password or "").encode(),
                                     binascii.unhexlify(salt_hex), int(rounds))
            return hmac.compare_digest(binascii.hexlify(dk).decode(), hash_hex)
        except (ValueError, binascii.Error):
            return False
    # Legacy: plain unsalted SHA-256 hex.
    legacy = hashlib.sha256((password or "").encode()).hexdigest()
    return hmac.compare_digest(legacy, stored)


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
    """Verify credentials. Returns the username on success, else raises AuthError.

    Transparently upgrades a legacy SHA-256 hash to PBKDF2 in-place on success (the
    caller must persist the doc afterwards)."""
    username = (username or "").strip()
    users = doc.get("users", {})
    if username not in users:
        raise AuthError("Username not found. Please sign up first.")
    stored = users[username].get("password_hash", "")
    if not verify_password(stored, password):
        raise AuthError("Incorrect password.")
    if needs_rehash(stored):                       # migrate legacy → PBKDF2
        users[username]["password_hash"] = hash_password(password)
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
