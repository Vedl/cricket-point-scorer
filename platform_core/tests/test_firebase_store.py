from platform_core.firebase_store import FirebaseStore


def test_local_mode_save_and_load(tmp_path):
    path = str(tmp_path / "data.json")
    store = FirebaseStore(local_file_path=path, database_url="")
    assert store.use_remote is False
    store.save({"users": {"a": {}}, "rooms": {}})
    loaded = store.load()
    assert loaded["users"] == {"a": {}}
    assert "rooms" in loaded


def test_load_missing_returns_empty_doc(tmp_path):
    store = FirebaseStore(local_file_path=str(tmp_path / "none.json"), database_url="")
    doc = store.load()
    assert doc == {"users": {}, "rooms": {}}


def test_ensure_schema_fixes_missing_squad():
    doc = {"rooms": {"A": {"participants": [{"name": "x"}]}}}
    fixed = FirebaseStore._ensure_schema(doc)
    assert fixed["rooms"]["A"]["participants"][0]["squad"] == []
    assert "users" in fixed


def test_normalize_sparse_list_to_dict():
    # Firebase turns {"1": x, "3": y} into [None, x, None, y].
    out = FirebaseStore._normalize([None, {"v": 1}, None, {"v": 2}])
    assert out == {"1": {"v": 1}, "3": {"v": 2}}


def test_normalize_keeps_dense_lists():
    out = FirebaseStore._normalize([{"v": 1}, {"v": 2}])
    assert out == [{"v": 1}, {"v": 2}]
