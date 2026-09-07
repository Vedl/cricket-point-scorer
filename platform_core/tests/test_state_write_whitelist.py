"""set_field must not be an arbitrary state-write primitive.

Every state exposed ``set_field(name, value)`` doing ``setattr(self, name, value)``
with a client-supplied name, so anyone could set ANY var on that state over the
websocket — ``is_admin`` on the room states, ``auth_user`` on AppState. These
assert the whitelists stay in place and stay closed over the dangerous names.
"""

import ast
import pathlib

import pytest

FA = pathlib.Path(__file__).resolve().parents[2] / "fantasy_auction"
STATES = sorted(p for p in FA.glob("*state*.py"))
FORBIDDEN = {"is_admin", "auth_user", "_auth_user", "is_spectator", "my_team",
             "_identity_room", "room_code", "me"}


def _whitelist_names(path):
    """The frozenset literal guarding set_field in this module, if any."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            fn = node.value.func
            if getattr(fn, "id", "") != "frozenset":
                continue
            if not node.value.args:
                return frozenset()          # deliberately writable-by-nothing
            arg = node.value.args[0]
            if isinstance(arg, ast.Set):
                return {e.value for e in arg.elts if isinstance(e, ast.Constant)}
    return None


def _has_set_field(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == "set_field"
               for n in ast.walk(tree))


@pytest.mark.parametrize("path", STATES, ids=lambda p: p.name)
def test_set_field_is_whitelisted(path):
    if not _has_set_field(path):
        pytest.skip("no set_field on this state")
    names = _whitelist_names(path)
    assert names is not None, f"{path.name}: set_field has no whitelist"


@pytest.mark.parametrize("path", STATES, ids=lambda p: p.name)
def test_whitelist_never_admits_a_privilege_field(path):
    names = _whitelist_names(path)
    if names is None:
        pytest.skip("no whitelist on this state")
    leaked = names & FORBIDDEN
    assert not leaked, f"{path.name}: set_field would allow writing {leaked}"


def test_set_field_bodies_actually_consult_the_whitelist():
    for path in STATES:
        src = path.read_text(encoding="utf-8")
        if not _has_set_field(path):
            continue
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "set_field":
                body = ast.unparse(node)
                assert "not in" in body and "return" in body, \
                    f"{path.name}: set_field does not gate on its whitelist"


# --- the whitelists must match the UI, or inputs silently stop working ------ #
# Field names passed into shared components as variables rather than literals.
_DYNAMIC_ARGS = {"picker_field": ["give_player", "get_player"],
                 "cash_field": ["give_cash", "get_cash"]}
_STATE_MODULE = {"AdminState": "admin_state", "AppState": "state",
                 "SeasonState": "season_state", "RoomState": "room_state",
                 "BiddingState": "bidding_state", "TradeState": "trade_state",
                 "ScheduleState": "schedule_state", "WhoScoredState": "whoscored_state"}


def test_every_set_field_call_site_is_permitted():
    """A whitelist that misses a field makes that input silently do nothing —
    which is exactly how an admin panel breaks in the middle of a gameweek."""
    import re
    ui = "\n".join(p.read_text(encoding="utf-8") for p in FA.glob("*.py"))
    whitelists = {p.stem: _whitelist_names(p) for p in STATES}
    missing = []
    for m in re.finditer(r'(\w+State)\.set_field\(\s*("([^"]+)"|(\w+))', ui):
        state, literal, var = m.group(1), m.group(3), m.group(4)
        allowed = whitelists.get(_STATE_MODULE.get(state, ""))
        if allowed is None:
            continue
        for name in ([literal] if literal else _DYNAMIC_ARGS.get(var, [])):
            if name not in allowed:
                missing.append(f"{state}.set_field({name!r})")
    assert not missing, "whitelist does not permit: " + ", ".join(sorted(set(missing)))
