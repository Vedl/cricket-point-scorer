"""
Automated integration tests for the Cricket Auction API.

Runs the full linking flow end-to-end against a live server:
  1. Create room
  2. Generate claim token (admin)
  3. Link participant (claim token)
  4. Fetch user rooms

Usage:
    python tests/test_api.py                       # default: http://127.0.0.1:8000
    BASE_URL=http://example.com python tests/test_api.py
"""

import os
import sys
import requests

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000")
TEST_UID = "test_uid_123"


def _url(path: str) -> str:
    return f"{BASE_URL}{path}"


def _check(label: str, resp: requests.Response) -> dict:
    if resp.status_code >= 300:
        print(f"✗ {label}")
        print(f"  Status: {resp.status_code}")
        print(f"  Body:   {resp.text}")
        sys.exit(1)
    data = resp.json()
    print(f"✓ {label}")
    return data


def main():
    print(f"\n🏏 Cricket Auction API Tests — {BASE_URL}\n")

    # ── 1. Create room ──────────────────────────────────────
    resp = requests.post(
        _url("/auction/create-room"),
        json={
            "admin_name": "TestAdmin",
            "tournament_type": "t20_wc",
        },
    )
    data = _check("Room created", resp)
    room_code = data["room_code"]
    print(f"  room_code = {room_code}")

    # ── 2. Generate claim token ─────────────────────────────
    resp = requests.post(
        _url("/user/generate-claim-token"),
        json={
            "room_code": room_code,
            "participant_name": "TestAdmin",
            "admin_name": "TestAdmin",
        },
    )
    data = _check("Claim token generated", resp)
    claim_token = data["claim_token"]
    print(f"  claim_token = {claim_token}")

    # ── 3. Link participant ─────────────────────────────────
    resp = requests.post(
        _url("/user/link-participant"),
        json={
            "room_code": room_code,
            "participant_name": "TestAdmin",
            "claim_token": claim_token,
            "uid": TEST_UID,
        },
    )
    data = _check("Participant linked", resp)
    assert data.get("linked") is True, f"Expected linked=true, got {data}"

    # ── 4. Fetch user rooms ─────────────────────────────────
    resp = requests.get(_url("/user/rooms"), params={"uid": TEST_UID})
    data = _check("User rooms fetched", resp)
    rooms = data.get("rooms", [])
    found = any(r["room_code"] == room_code for r in rooms)
    assert found, f"Room {room_code} not found in user rooms: {rooms}"
    print(f"  rooms count = {len(rooms)}")

    # ── 5. Verify GET /players works ────────────────────────
    resp = requests.get(_url("/players"))
    data = _check("Players endpoint works", resp)
    print(f"  players count = {data.get('total', 0)}")

    # ── 6. Edge cases ───────────────────────────────────────
    # Re-using same token should fail (single-use)
    resp = requests.post(
        _url("/user/link-participant"),
        json={
            "room_code": room_code,
            "participant_name": "TestAdmin",
            "claim_token": claim_token,
            "uid": "different_uid",
        },
    )
    assert resp.status_code == 400, f"Expected 400 for reused token, got {resp.status_code}"
    print("✓ Reused token correctly rejected (400)")

    # Non-admin cannot generate token
    resp = requests.post(
        _url("/user/generate-claim-token"),
        json={
            "room_code": room_code,
            "participant_name": "TestAdmin",
            "admin_name": "NotAdmin",
        },
    )
    assert resp.status_code == 403, f"Expected 403:, got {resp.status_code}"
    print("✓ Non-admin token generation rejected (403)")

    print("\n🎉 ALL TESTS PASSED\n")


if __name__ == "__main__":
    main()
