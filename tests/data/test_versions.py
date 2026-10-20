import datetime as dt
import os
import re
import subprocess
import sys

import duckdb
import pytest

from siba.data import config, loader, versions

NAME_RE = re.compile(r"^\d{8}_\d{6}__(load|snapshot)__siba\.duckdb$")


@pytest.fixture(autouse=True)
def _fast_clock(monkeypatch):
    """Horloge qui avance d'une seconde par appel : deux versions jamais homonymes."""
    t = [dt.datetime(2026, 10, 20, 9, 0, 0)]

    def _now():
        t[0] += dt.timedelta(seconds=1)
        return t[0]

    monkeypatch.setattr(versions, "_now", _now)


def _mk(link, kind, marker, **kw):
    with versions.new_version(link, kind, **kw) as con:
        con.execute("CREATE TABLE IF NOT EXISTS t(v INT)")
        con.execute("DELETE FROM t")
        con.execute("INSERT INTO t VALUES (?)", [marker])


def _files(link):
    return sorted(p.name for p in (link.parent / "versions").iterdir())


def _read_v(path):
    con = duckdb.connect(str(path), read_only=True)
    try:
        return con.execute("SELECT v FROM t").fetchone()[0]
    finally:
        con.close()


def _stub_loads(monkeypatch):
    monkeypatch.setattr(loader, "_load_nappe", lambda con, years, **kw: (0, None, None))
    monkeypatch.setattr(loader, "_load_meteo", lambda con, keys, **kw: (0, None, None))


@pytest.mark.functional
def test_update_on_fresh_path_creates_load_version_and_link(tmp_path, monkeypatch):
    _stub_loads(monkeypatch)
    link = tmp_path / "siba.duckdb"
    loader.update(db_path=link)
    assert link.is_symlink()
    names = _files(link)
    assert len(names) == 1 and NAME_RE.match(names[0])
    assert "__load__" in names[0]
    assert os.readlink(link) == f"versions/{names[0]}"  # lien relatif


@pytest.mark.functional
def test_second_update_creates_new_version_and_keeps_first(tmp_path, monkeypatch):
    _stub_loads(monkeypatch)
    link = tmp_path / "siba.duckdb"
    loader.update(db_path=link)
    first = tmp_path / "versions" / _files(link)[0]
    before = first.read_bytes()
    loader.update(db_path=link)
    names = _files(link)
    assert len(names) == 2
    assert os.readlink(link) == f"versions/{names[-1]}"
    assert first.read_bytes() == before


@pytest.mark.functional
def test_failed_update_leaves_no_version_and_link_unchanged(tmp_path, monkeypatch):
    _stub_loads(monkeypatch)
    link = tmp_path / "siba.duckdb"
    loader.update(db_path=link)
    target = os.readlink(link)

    def _boom(con, keys, **kw):
        raise RuntimeError("meteo down")

    monkeypatch.setattr(loader, "_load_meteo", _boom)
    with pytest.raises(RuntimeError):
        loader.update(db_path=link)
    assert len(_files(link)) == 1  # ni nouvelle version, ni .tmp, ni .tmp.wal
    assert os.readlink(link) == target


@pytest.mark.functional
def test_new_version_refuses_when_wal_exists(tmp_path):
    link = tmp_path / "siba.duckdb"
    _mk(link, "load", 1)
    target = os.readlink(link)
    cur = versions.current(link)
    cur.with_name(cur.name + ".wal").touch()
    with pytest.raises(RuntimeError, match="wal"):
        with versions.new_version(link, "load"):
            pass
    assert not [n for n in _files(link) if n.endswith(".tmp")]
    assert os.readlink(link) == target


@pytest.mark.functional
def test_new_version_without_copy_starts_empty(tmp_path):
    link = tmp_path / "siba.duckdb"
    _mk(link, "load", 1)
    with versions.new_version(link, "load", copy=False) as con:
        tables = con.execute("SELECT table_name FROM information_schema.tables").fetchall()
    assert tables == []
    assert len(_files(link)) == 2


@pytest.mark.functional
def test_rebuild_starts_from_empty_version(tmp_path, monkeypatch):
    # rebuild ne copie pas la version courante : une table étrangère au schéma
    # n'y survit pas, et le fichier ne traîne pas les blocs libérés.
    monkeypatch.setattr(loader, "_load_nappe", lambda con, years, **kw: (7, None, None))
    monkeypatch.setattr(loader, "_load_meteo", lambda con, keys, **kw: (9, None, None))
    monkeypatch.setattr(loader.sources, "download_meteo_descriptor", lambda dest: None)
    link = tmp_path / "siba.duckdb"
    _mk(link, "load", 1)
    loader.rebuild(db_path=link)
    con = duckdb.connect(str(link), read_only=True)
    tables = {r[0] for r in con.execute("SELECT table_name FROM information_schema.tables").fetchall()}
    con.close()
    assert "t" not in tables
    assert "nappe_mesure" in tables


@pytest.mark.functional
def test_snapshot_copies_current_and_moves_link(tmp_path):
    link = tmp_path / "siba.duckdb"
    _mk(link, "load", 1)
    load_name = _files(link)[0]
    versions.snapshot(link)
    names = _files(link)
    assert len(names) == 2
    snap = [n for n in names if "__snapshot__" in n]
    assert len(snap) == 1
    assert os.readlink(link) == f"versions/{snap[0]}"
    assert _read_v(tmp_path / "versions" / snap[0]) == 1
    assert load_name in names


@pytest.mark.functional
def test_snapshot_without_database_raises(tmp_path):
    with pytest.raises(RuntimeError):
        versions.snapshot(tmp_path / "siba.duckdb")


@pytest.mark.functional
def test_restore_points_link_at_named_version(tmp_path):
    link = tmp_path / "siba.duckdb"
    _mk(link, "load", 1)
    _mk(link, "load", 2)
    first = _files(link)[0]
    versions.restore(link, first)
    assert os.readlink(link) == f"versions/{first}"
    assert len(_files(link)) == 2  # restaurer ne crée aucun fichier
    assert _read_v(link) == 1


@pytest.mark.functional
def test_restore_unknown_name_raises(tmp_path):
    link = tmp_path / "siba.duckdb"
    _mk(link, "load", 1)
    with pytest.raises(FileNotFoundError, match="Version inconnue"):
        versions.restore(link, "20000101_000000__load__siba.duckdb")


@pytest.mark.functional
def test_prune_keeps_newest_and_current_and_ignores_other_files(tmp_path):
    link = tmp_path / "siba.duckdb"
    vdir = tmp_path / "versions"
    vdir.mkdir()
    names = [f"2026101{i}_120000__load__siba.duckdb" for i in range(8)]
    for n in names:
        (vdir / n).touch()
    (vdir / "notes.txt").touch()
    (vdir / "x.duckdb.tmp").touch()
    # La plus ancienne est la courante ; la 2e a un .wal (client ouvert).
    versions.flip(link, vdir / names[0])
    (vdir / (names[1] + ".wal")).touch()
    removed = versions.prune(link, keep=5)
    assert sorted(p.name for p in removed) == [names[2]]
    left = set(_files(link))
    assert set(names[3:]) <= left  # les 5 plus récentes
    assert names[0] in left and names[1] in left
    assert {"notes.txt", "x.duckdb.tmp"} <= left


@pytest.mark.functional
def test_migrate_turns_regular_file_into_version_and_link(tmp_path):
    link = tmp_path / "siba.duckdb"
    con = duckdb.connect(str(link))
    con.execute("CREATE TABLE t(v INT)")
    con.execute("INSERT INTO t VALUES (7)")
    con.close()
    ts = dt.datetime(2026, 10, 18, 15, 52, 39).timestamp()
    os.utime(link, (ts, ts))
    target = versions.migrate(link)
    assert link.is_symlink()
    assert os.readlink(link) == "versions/20261018_155239__load__siba.duckdb"
    assert target == tmp_path / "versions" / "20261018_155239__load__siba.duckdb"
    assert _read_v(link) == 7


@pytest.mark.functional
def test_migrate_is_noop_on_link_or_missing(tmp_path):
    link = tmp_path / "siba.duckdb"
    assert versions.migrate(link) is None
    assert not link.exists()
    _mk(link, "load", 1)
    before = os.readlink(link)
    assert versions.migrate(link) is None
    assert os.readlink(link) == before


@pytest.mark.functional
def test_migrate_refuses_when_wal_exists(tmp_path):
    link = tmp_path / "siba.duckdb"
    duckdb.connect(str(link)).close()
    (tmp_path / "siba.duckdb.wal").touch()
    with pytest.raises(RuntimeError, match="wal"):
        versions.migrate(link)
    assert not link.is_symlink()


@pytest.mark.functional
def test_list_versions_marks_current(tmp_path):
    link = tmp_path / "siba.duckdb"
    _mk(link, "load", 1)
    versions.snapshot(link)
    first = _files(link)[0]
    versions.restore(link, first)
    rows = versions.list_versions(link)
    assert [r["name"] for r in rows] == _files(link)
    assert {r["kind"] for r in rows} == {"load", "snapshot"}
    assert all(r["size"] > 0 for r in rows)
    assert [r["name"] for r in rows if r["current"]] == [first]


SCRIPT = """
import sys, duckdb
con = duckdb.connect(sys.argv[1], read_only=True)
print(con.execute("SELECT v FROM t").fetchone()[0], flush=True)
sys.stdin.readline()
print(con.execute("SELECT v FROM t").fetchone()[0], flush=True)
"""


@pytest.mark.functional
def test_reader_keeps_its_version_across_flip(tmp_path):
    # Sous-processus : dans un même processus DuckDB resservirait la même instance.
    link = tmp_path / "siba.duckdb"
    _mk(link, "load", 1)
    proc = subprocess.Popen(
        [sys.executable, "-c", SCRIPT, str(link)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
    )
    try:
        assert proc.stdout.readline().strip() == "1"
        _mk(link, "load", 2)  # bascule le lien pendant que le lecteur est ouvert
        proc.stdin.write("\n")
        proc.stdin.flush()
        assert proc.stdout.readline().strip() == "1"
    finally:
        proc.stdin.close()
        assert proc.wait(timeout=30) == 0
    assert _read_v(link) == 2


def _dangling(tmp_path):
    """Lien dont la cible a disparu (version supprimée à la main)."""
    link = tmp_path / "siba.duckdb"
    _mk(link, "load", 1)
    versions.current(link).unlink()
    return link, os.readlink(link)


@pytest.mark.functional
def test_update_on_dangling_link_raises_and_keeps_link(tmp_path, monkeypatch):
    _stub_loads(monkeypatch)
    link, target = _dangling(tmp_path)
    with pytest.raises(RuntimeError, match="version absente"):
        loader.update(db_path=link)
    assert os.readlink(link) == target
    assert _files(link) == []  # ni version ni .tmp


@pytest.mark.functional
def test_snapshot_on_dangling_link_raises(tmp_path):
    link, target = _dangling(tmp_path)
    with pytest.raises(RuntimeError, match="version absente"):
        versions.snapshot(link)
    assert os.readlink(link) == target


@pytest.mark.functional
def test_rebuild_on_dangling_link_still_works(tmp_path, monkeypatch):
    monkeypatch.setattr(loader, "_load_nappe", lambda con, years, **kw: (7, None, None))
    monkeypatch.setattr(loader, "_load_meteo", lambda con, keys, **kw: (9, None, None))
    monkeypatch.setattr(loader.sources, "download_meteo_descriptor", lambda dest: None)
    link, target = _dangling(tmp_path)
    loader.rebuild(db_path=link)
    assert os.readlink(link) != target
    assert versions.current(link).exists()


@pytest.mark.functional
def test_successive_loads_keep_all_versions(tmp_path, monkeypatch):
    # Aucune suppression automatique : la rétention passe par `prune`.
    _stub_loads(monkeypatch)
    link = tmp_path / "siba.duckdb"
    n = config.VERSIONS_KEEP + 2
    for _ in range(n):
        loader.update(db_path=link)
    assert len(_files(link)) == n


@pytest.mark.functional
def test_prune_command_keeps_n_and_spares_current(tmp_path, capsys):
    from siba.data import cli

    link = tmp_path / "siba.duckdb"
    for i in range(4):
        _mk(link, "load", i)
    names = _files(link)
    versions.restore(link, names[0])  # la courante est la plus ancienne
    capsys.readouterr()
    assert cli.main(["prune", "--keep", "2", "--db-path", str(link)]) == 0
    out = capsys.readouterr().out
    assert _files(link) == [names[0], names[2], names[3]]
    assert names[1] in out
    assert os.readlink(link) == f"versions/{names[0]}"


@pytest.mark.functional
def test_prune_command_defaults_to_versions_keep(tmp_path, monkeypatch):
    from siba.data import cli

    monkeypatch.setattr(config, "VERSIONS_KEEP", 1)
    link = tmp_path / "siba.duckdb"
    for i in range(3):
        _mk(link, "load", i)
    names = _files(link)
    assert cli.main(["prune", "--db-path", str(link)]) == 0
    assert _files(link) == [names[-1]]


@pytest.mark.functional
def test_prune_command_without_versions_dir(tmp_path, capsys):
    from siba.data import cli

    rc = cli.main(["prune", "--db-path", str(tmp_path / "siba.duckdb")])
    assert rc == 0
    assert "Rien à supprimer." in capsys.readouterr().out


@pytest.mark.functional
def test_prune_command_rejects_negative_keep(tmp_path, capsys):
    from siba.data import cli

    link = tmp_path / "siba.duckdb"
    for i in range(3):
        _mk(link, "load", i)
    before = _files(link)
    capsys.readouterr()
    rc = cli.main(["prune", "--keep", "-1", "--db-path", str(link)])
    err = capsys.readouterr().err
    assert rc == 1
    assert "Traceback" not in err and err.count("\n") == 1
    assert _files(link) == before


@pytest.mark.functional
def test_update_with_corrupt_current_leaves_no_tmp(tmp_path, monkeypatch):
    _stub_loads(monkeypatch)
    link = tmp_path / "siba.duckdb"
    _mk(link, "load", 1)
    target = os.readlink(link)
    versions.current(link).write_bytes(b"pas une base duckdb" * 100)
    with pytest.raises(Exception):
        loader.update(db_path=link)
    assert not [n for n in _files(link) if ".tmp" in n]
    assert os.readlink(link) == target
