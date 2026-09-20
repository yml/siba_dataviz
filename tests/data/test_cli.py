import pytest

from siba.data import cli


def test_db_path_before_subcommand_is_not_silently_ignored(monkeypatch):
    # Regression: `siba --db-path X rebuild` used to run rebuild(db_path=None)
    # and wipe the default DB. With --db-path declared only on the subparsers,
    # the pre-subcommand form must fail loudly instead of silently mis-targeting.
    monkeypatch.setattr(cli.loader, "update", lambda db_path=None: None)
    monkeypatch.setattr(cli.loader, "rebuild", lambda db_path=None: None)
    with pytest.raises(SystemExit):
        cli.main(["--db-path", "/tmp/x.duckdb", "rebuild"])


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
