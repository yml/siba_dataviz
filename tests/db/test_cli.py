from siba.db import cli


def test_update_is_default(monkeypatch):
    called = {}
    monkeypatch.setattr(cli.loader, "update", lambda db_path=None: called.setdefault("update", db_path))
    monkeypatch.setattr(cli.loader, "rebuild", lambda db_path=None: called.setdefault("rebuild", True))
    rc = cli.main([])
    assert rc == 0
    assert "update" in called and "rebuild" not in called


def test_rebuild_with_db_path(monkeypatch):
    called = {}
    monkeypatch.setattr(cli.loader, "update", lambda db_path=None: called.setdefault("update", True))
    monkeypatch.setattr(cli.loader, "rebuild", lambda db_path=None: called.setdefault("db", db_path))
    rc = cli.main(["rebuild", "--db-path", "/tmp/x.duckdb"])
    assert rc == 0
    assert called["db"] == "/tmp/x.duckdb"
