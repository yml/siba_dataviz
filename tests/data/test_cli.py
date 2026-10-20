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


@pytest.mark.internal
def test_rebuild_with_db_path(monkeypatch):
    called = {}
    monkeypatch.setattr(cli.loader, "update", lambda db_path=None: called.setdefault("update", True))
    monkeypatch.setattr(
        cli.loader, "rebuild", lambda db_path=None, refresh=False: called.setdefault("db", db_path)
    )
    rc = cli.main(["rebuild", "--db-path", "/tmp/x.duckdb"])
    assert rc == 0
    assert called["db"] == "/tmp/x.duckdb"


@pytest.mark.internal
def test_rebuild_parses_refresh(monkeypatch):
    called = []
    monkeypatch.setattr(
        cli.loader, "rebuild", lambda db_path=None, refresh=False: called.append(refresh)
    )
    cli.main(["rebuild", "--refresh"])
    cli.main(["rebuild"])
    assert called == [True, False]


@pytest.mark.internal
def test_versions_subcommand_lists(monkeypatch):
    called = {}
    monkeypatch.setattr(cli.loader, "list_versions", lambda db_path=None: called.setdefault("db", db_path))
    cli.main(["versions", "--db-path", "/x"])
    assert called == {"db": "/x"}


@pytest.mark.internal
def test_snapshot_subcommand(monkeypatch):
    called = {}
    monkeypatch.setattr(cli.loader, "snapshot", lambda db_path=None: called.setdefault("db", db_path))
    cli.main(["snapshot", "--db-path", "/x"])
    assert called == {"db": "/x"}


@pytest.mark.internal
def test_restore_subcommand_passes_name(monkeypatch):
    called = {}
    monkeypatch.setattr(
        cli.loader, "restore", lambda name, db_path=None: called.update(name=name, db=db_path)
    )
    cli.main(["restore", "20261018_155239__load__siba.duckdb"])
    assert called == {"name": "20261018_155239__load__siba.duckdb", "db": None}
    with pytest.raises(SystemExit):
        cli.main(["restore"])


@pytest.mark.functional
def test_restore_unknown_name_prints_error_and_exits_1(tmp_path, capsys):
    rc = cli.main(["restore", "20000101_000000__load__siba.duckdb",
                   "--db-path", str(tmp_path / "siba.duckdb")])
    err = capsys.readouterr().err
    assert rc == 1
    assert "Version inconnue" in err
    assert "Traceback" not in err


@pytest.mark.functional
def test_update_refused_by_wal_prints_error_and_exits_1(tmp_path, monkeypatch, capsys):
    from siba.data import versions

    monkeypatch.setattr(cli.loader, "_load_nappe", lambda con, years, **kw: (0, None, None))
    monkeypatch.setattr(cli.loader, "_load_meteo", lambda con, keys, **kw: (0, None, None))
    link = tmp_path / "siba.duckdb"
    assert cli.main(["update", "--db-path", str(link)]) == 0
    cur = versions.current(link)
    cur.with_name(cur.name + ".wal").touch()
    rc = cli.main(["update", "--db-path", str(link)])
    err = capsys.readouterr().err
    assert rc == 1
    assert ".wal" in err and err.count("\n") == 1  # une seule ligne
