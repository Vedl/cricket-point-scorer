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

# Each isolated Firebase node has a local-mode fallback file (dev / no Firebase URL).
_LOCAL_FILES = {
    "push_subscriptions": os.environ.get("PUSH_SUBSCRIPTIONS_FILE", "push_subscriptions.json"),
    "push_deadlines": os.environ.get("PUSH_DEADLINES_FILE", "push_deadlines.json"),
    "push_fired": os.environ.get("PUSH_FIRED_FILE", "push_fired.json"),
}

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


def _rest_url(node: str, path: str = "") -> str:
    base = f"{_db_base()}/{node}{path}.json"
    sec = _secret()
    return f"{base}?auth={sec}" if sec else base


def _node_url(path: str = "") -> str:
    """Subscriptions node URL (used by the subscription helpers below)."""
    return _rest_url("push_subscriptions", path)


def _use_remote() -> bool:
    return bool(_db_base()) and requests is not None


def _load_node_local(node: str) -> dict:
    try:
        with open(_LOCAL_FILES.get(node, f"{node}.json"), "r", encoding="utf-8") as fh:
            return json.load(fh) or {}
    except Exception:
        return {}


def _save_node_local(node: str, data: dict) -> None:
    try:
        with open(_LOCAL_FILES.get(node, f"{node}.json"), "w", encoding="utf-8") as fh:
            json.dump(data, fh)
    except Exception as exc:  # pragma: no cover
        print(f"[push] local save error ({node}): {exc}")


def _load_local() -> dict:
    return _load_node_local("push_subscriptions")


def _save_local(data: dict) -> None:
    _save_node_local("push_subscriptions", data)


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


# ── deadline index + fired-markers (isolated nodes for the cron-driven scheduler) ──

def set_deadline_index(code: str, dl_iso: str, gw: str = "") -> None:
    """Record a room's current bidding deadline so the tick can find it WITHOUT ever
    reading the auction document. Written once when the admin sets the deadline."""
    if not code or not dl_iso:
        return
    rec = {"dl": dl_iso, "gw": gw or ""}
    if _use_remote():
        try:
            requests.put(_rest_url("push_deadlines", f"/{code}"), data=json.dumps(rec),
                         headers={"Content-Type": "application/json"}, timeout=10)
            return
        except Exception as exc:  # pragma: no cover
            print(f"[push] deadline index put error: {exc}")
            return
    data = _load_node_local("push_deadlines")
    data[code] = rec
    _save_node_local("push_deadlines", data)


def load_deadline_index() -> dict:
    """{room_code: {"dl": iso, "gw": str}} — the only thing the tick reads to find work."""
    if _use_remote():
        try:
            resp = requests.get(_rest_url("push_deadlines"), timeout=10)
            if resp.ok:
                return resp.json() or {}
        except Exception as exc:  # pragma: no cover
            print(f"[push] deadline index load error: {exc}")
        return {}
    return _load_node_local("push_deadlines")


def delete_deadline_index(code: str) -> None:
    if not code:
        return
    if _use_remote():
        try:
            requests.delete(_rest_url("push_deadlines", f"/{code}"), timeout=10)
        except Exception:  # pragma: no cover
            pass
        return
    data = _load_node_local("push_deadlines")
    if code in data:
        del data[code]
        _save_node_local("push_deadlines", data)


def load_fired(code: str) -> set[str]:
    """Set of dedup keys already fired for this room's current deadline."""
    if not code:
        return set()
    if _use_remote():
        try:
            resp = requests.get(_rest_url("push_fired", f"/{code}"), timeout=10)
            if resp.ok and isinstance(resp.json(), dict):
                return set(resp.json().keys())
        except Exception as exc:  # pragma: no cover
            print(f"[push] fired load error: {exc}")
        return set()
    return set((_load_node_local("push_fired").get(code) or {}).keys())


def mark_fired(code: str, key: str) -> None:
    if not code or not key:
        return
    if _use_remote():
        try:
            requests.put(_rest_url("push_fired", f"/{code}/{key}"), data="true",
                         headers={"Content-Type": "application/json"}, timeout=10)
        except Exception as exc:  # pragma: no cover
            print(f"[push] mark_fired error: {exc}")
        return
    data = _load_node_local("push_fired")
    data.setdefault(code, {})[key] = True
    _save_node_local("push_fired", data)


def clear_fired(code: str) -> None:
    """Drop all fired markers for a room (called when a fresh deadline is set, and on prune)."""
    if not code:
        return
    if _use_remote():
        try:
            requests.delete(_rest_url("push_fired", f"/{code}"), timeout=10)
        except Exception:  # pragma: no cover
            pass
        return
    data = _load_node_local("push_fired")
    if code in data:
        del data[code]
        _save_node_local("push_fired", data)


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


def _notify_blocking(match, title: str, body: str, url: str) -> None:
    subs = load_subscriptions()
    payload = {"title": title, "body": body, "url": url or "/"}
    for sid, rec in subs.items():
        if not isinstance(rec, dict):
            continue
        if match(rec):
            _send_one(sid, rec, payload)


def _unconfigured_skip() -> bool:
    global _warned
    if not configured():
        if not _warned:
            print("[push] not configured (missing pywebpush or VAPID keys) — skipping")
            _warned = True
        return True
    return False


def notify_users(users: Iterable[str], title: str, body: str, url: str = "/") -> None:
    """Fire a push to every device of the given usernames, in a background thread so the
    caller's request returns immediately. No-op if push isn't configured."""
    targets = {u for u in (users or []) if u}
    if not targets or _unconfigured_skip():
        return
    threading.Thread(
        target=_notify_blocking,
        args=(lambda rec: rec.get("user") in targets, title, body, url),
        name="push-send", daemon=True,
    ).start()


def notify_room(code: str, title: str, body: str, url: str = "/") -> bool:
    """Push to every device subscribed within room ``code`` (room-wide alerts). Returns
    True if a send was dispatched, False if it was a no-op (unconfigured) — the caller
    uses this to decide whether to mark a milestone as fired."""
    if not code or _unconfigured_skip():
        return False
    threading.Thread(
        target=_notify_blocking,
        args=(lambda rec: rec.get("room") == code, title, body, url),
        name="push-send-room", daemon=True,
    ).start()
    return True
