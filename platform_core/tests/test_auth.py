import pytest

from platform_core.auth import AuthError, hash_password, log_in, reset_password, sign_up


def test_sign_up_and_login():
    doc = {"users": {}, "rooms": {}}
    sign_up(doc, "alice", "secret", "secret")
    assert "alice" in doc["users"]
    assert doc["users"]["alice"]["password_hash"] == hash_password("secret")
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


def test_legacy_hash_compatibility():
    # Existing accounts use plain sha256 — verify we match.
    import hashlib

    expected = hashlib.sha256("hunter2".encode()).hexdigest()
    assert hash_password("hunter2") == expected
