import pytest

from platform_core.auth import (
    AuthError, hash_password, log_in, reset_password, sign_up, verify_password,
)


def test_sign_up_and_login():
    doc = {"users": {}, "rooms": {}}
    sign_up(doc, "alice", "secret", "secret")
    assert "alice" in doc["users"]
    assert verify_password(doc["users"]["alice"]["password_hash"], "secret")
    assert log_in(doc, "alice", "secret") == "alice"


def test_sign_up_rejects_short_password():
    doc = {"users": {}}
    with pytest.raises(AuthError, match="at least 4"):
        sign_up(doc, "bob", "ab")


def test_sign_up_rejects_mismatch_and_duplicate():
    doc = {"users": {}}
    with pytest.raises(AuthError, match="do not match"):
        sign_up(doc, "bob", "abcd", "abce")
    sign_up(doc, "bob", "abcd")
    with pytest.raises(AuthError, match="already taken"):
        sign_up(doc, "bob", "abcd")


def test_login_errors():
    doc = {"users": {}}
    with pytest.raises(AuthError, match="not found"):
        log_in(doc, "ghost", "x")
    sign_up(doc, "bob", "abcd")
    with pytest.raises(AuthError, match="Incorrect password"):
        log_in(doc, "bob", "wrong")


def test_reset_password_requires_room_membership():
    doc = {"users": {}, "rooms": {"ABC123": {"members": ["bob"]}}}
    sign_up(doc, "bob", "abcd")
    # wrong room membership
    doc["rooms"]["ABC123"]["members"] = ["someone_else"]
    with pytest.raises(AuthError, match="not a member"):
        reset_password(doc, "bob", "ABC123", "newpass")
    # correct membership
    doc["rooms"]["ABC123"]["members"] = ["bob"]
    reset_password(doc, "bob", "abc123", "newpass")  # case-insensitive code
    assert log_in(doc, "bob", "newpass") == "bob"


def test_new_hashes_are_pbkdf2_and_verify():
    from platform_core.auth import needs_rehash, verify_password
    h = hash_password("hunter2")
    assert h.startswith("pbkdf2_sha256$")
    assert h != hash_password("hunter2")          # random salt → different each time
    assert verify_password(h, "hunter2")
    assert not verify_password(h, "wrong")
    assert not needs_rehash(h)


def test_legacy_sha256_login_still_works_and_migrates():
    import hashlib

    from platform_core.auth import log_in, needs_rehash, verify_password
    legacy = hashlib.sha256("hunter2".encode()).hexdigest()
    doc = {"users": {"sam": {"password_hash": legacy, "rooms_created": [], "rooms_joined": []}},
           "rooms": {}}
    assert needs_rehash(legacy)
    assert verify_password(legacy, "hunter2")
    # login succeeds against the legacy hash...
    assert log_in(doc, "sam", "hunter2") == "sam"
    # ...and transparently upgrades the stored hash to PBKDF2.
    upgraded = doc["users"]["sam"]["password_hash"]
    assert upgraded.startswith("pbkdf2_sha256$")
    assert verify_password(upgraded, "hunter2")
