"""Web Push (PWA) notifications.

Standalone of the auction document on purpose: push subscriptions live in their own
Firebase node (``/push_subscriptions``) — NOT in ``/auction_data`` — so sending a
notification never downloads or rewrites the big ~700 KB room document (egress + the
512 MB host's memory budget both matter).

Config (env):
    VAPID_PUBLIC_KEY     base64url, uncompressed P-256 point — also handed to the browser
    VAPID_PRIVATE_KEY    base64url, raw 32-byte P-256 scalar
    VAPID_SUBJECT        contact, e.g. mailto:you@example.com   (default below)
    FIREBASE_DATABASE_URL / FIREBASE_SECRET   reused from the main store

Degrades safely: if pywebpush or the VAPID keys are missing, ``notify_users`` is a
no-op (logged once) so the app keeps working without push configured.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
from typing import Iterable, Optional

try:
    import requests
except Exception:  # pragma: no cover
    requests = None  # type: ignore

try:
    from pywebpush import WebPushException, webpush
    _PUSH_OK = True
except Exception:  # pragma: no cover - optional dependency
    webpush = None  # type: ignore
    WebPushException = Exception  # type: ignore
    _PUSH_OK = False

_DEFAULT_SUBJECT = "mailto:laddavedant@gmail.com"
_LOCAL_FILE = os.environ.get("PUSH_SUBSCRIPTIONS_FILE", "push_subscriptions.json")

_warned = False


def public_key() -> str:
    return os.environ.get("VAPID_PUBLIC_KEY", "")


def _private_key() -> str:
    return os.environ.get("VAPID_PRIVATE_KEY", "")


def _subject() -> str:
    return os.environ.get("VAPID_SUBJECT", _DEFAULT_SUBJECT)


def configured() -> bool:
    """True when push can actually be sent (library + keys present)."""
    return _PUSH_OK and bool(public_key()) and bool(_private_key())


def sub_id(endpoint: str) -> str:
    """Stable Firebase-safe key for a subscription (a re-subscribe of the same device
    overwrites rather than duplicating)."""
    return hashlib.sha256(endpoint.encode("utf-8")).hexdigest()[:40]


# ── subscription storage (isolated Firebase node, with local fallback) ──────────────

def _db_base() -> str:
    return os.environ.get("FIREBASE_DATABASE_URL", "").rstrip("/")


def _secret() -> str:
    return (os.environ.get("FIREBASE_SECRET")
            or os.environ.get("FIREBASE_SECRET_KEY", ""))


def _node_url(path: str) -> str:
    base = f"{_db_base()}/push_subscriptions{path}.json"
    sec = _secret()
    return f"{base}?auth={sec}" if sec else base


def _use_remote() -> bool:
    return bool(_db_base()) and requests is not None


def _load_local() -> dict:
    try:
        with open(_LOCAL_FILE, "r", encoding="utf-8") as fh:
            return json.load(fh) or {}
    except Exception:
        return {}


def _save_local(data: dict) -> None:
    try:
        with open(_LOCAL_FILE, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
    except Exception as exc:  # pragma: no cover
        print(f"[push] local save error: {exc}")


def load_subscriptions() -> dict:
    if _use_remote():
        try:
            resp = requests.get(_node_url(""), timeout=10)
            if resp.ok:
                return resp.json() or {}
        except Exception as exc:  # pragma: no cover
            print(f"[push] load error: {exc}")
            return {}
    return _load_local()


def save_subscription(subscription: dict, *, user: str, room: str = "", team: str = "") -> None:
    """Upsert one browser subscription, tagged with the owning user (+ room/team ctx)."""
    endpoint = (subscription or {}).get("endpoint", "")
    if not endpoint:
        return
    sid = sub_id(endpoint)
    record = {
        "endpoint": endpoint,
        "keys": (subscription or {}).get("keys", {}),
        "user": user or "",
        "room": room or "",
        "team": team or "",
    }
    if _use_remote():
        try:
            requests.put(
                _node_url(f"/{sid}"),
                data=json.dumps(record),
                headers={"Content-Type": "application/json"},
                timeout=10,
            )
            return
        except Exception as exc:  # pragma: no cover
            print(f"[push] save error: {exc}")
            return
    data = _load_local()
    data[sid] = record
    _save_local(data)


def delete_subscription(endpoint: str) -> None:
    if not endpoint:
        return
    sid = sub_id(endpoint)
    if _use_remote():
        try:
            requests.delete(_node_url(f"/{sid}"), timeout=10)
            return
        except Exception as exc:  # pragma: no cover
            print(f"[push] delete error: {exc}")
            return
    data = _load_local()
    if sid in data:
        del data[sid]
        _save_local(data)


def _delete_by_sid(sid: str) -> None:
    if _use_remote():
        try:
            requests.delete(_node_url(f"/{sid}"), timeout=10)
        except Exception:  # pragma: no cover
            pass
    else:
        data = _load_local()
        if sid in data:
            del data[sid]
            _save_local(data)


# ── sending ─────────────────────────────────────────────────────────────────────────

def _send_one(sid: str, record: dict, payload: dict) -> None:
    info = {
        "endpoint": record.get("endpoint", ""),
        "keys": record.get("keys", {}),
    }
    try:
        webpush(
            subscription_info=info,
            data=json.dumps(payload),
            vapid_private_key=_private_key(),
            vapid_claims={"sub": _subject()},
            timeout=10,
        )
    except WebPushException as exc:  # pragma: no cover - network
        status = getattr(getattr(exc, "response", None), "status_code", None)
        # 404/410 → the browser dropped this subscription; prune it so the node
        # never accumulates dead endpoints.
        if status in (404, 410):
            _delete_by_sid(sid)
        else:
            print(f"[push] send failed ({status}): {exc}")
    except Exception as exc:  # pragma: no cover
        print(f"[push] send error: {exc}")


def _notify_blocking(users: set[str], title: str, body: str, url: str) -> None:
    subs = load_subscriptions()
    payload = {"title": title, "body": body, "url": url or "/"}
    for sid, rec in subs.items():
        if not isinstance(rec, dict):
            continue
        if rec.get("user") in users:
            _send_one(sid, rec, payload)


def notify_users(users: Iterable[str], title: str, body: str, url: str = "/") -> None:
    """Fire a push to every device of the given usernames, in a background thread so the
    caller's request returns immediately. No-op if push isn't configured."""
    global _warned
    targets = {u for u in (users or []) if u}
    if not targets:
        return
    if not configured():
        if not _warned:
            print("[push] not configured (missing pywebpush or VAPID keys) — skipping")
            _warned = True
        return
    threading.Thread(
        target=_notify_blocking,
        args=(targets, title, body, url),
        name="push-send",
        daemon=True,
    ).start()
