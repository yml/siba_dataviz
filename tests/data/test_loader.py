import datetime as dt
import shutil
from pathlib import Path

import pandas as pd
import pytest

from siba.data import config, loader, schema


def _con(tmp_path):
    c = schema.connect(tmp_path / "t.duckdb")
    schema.create_all(c)
    schema.seed_stations(c)
    return c


def _fake_nappe(code_bss, year, **kwargs):
    return pd.DataFrame({
        "code_bss": [code_bss],
        "date_mesure": [pd.Timestamp(f"{year}-06-01")],
        "niveau_nappe_eau": [10.0], "profondeur_nappe": [1.0],
        "statut": ["s"], "qualification": ["Correcte"], "mode_obtention": ["m"],
        "code_producteur": ["327"], "nom_producteur": ["p"],
        "code_nature_mesure": ["N"], "urn_bss": ["u"], "timestamp_mesure": [1],
    })


def test_load_nappe_prints_progress(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(config, "NAPPE_REQUEST_DELAY", 0)
    con = _con(tmp_path)
    loader._load_nappe(con, [2024], fetch=_fake_nappe)
    out = capsys.readouterr().out
    assert "Blagon (Lanton)" in out  # per piézo
    assert "2024" in out             # per year
    assert "1 ligne" in out          # row count
    con.close()


def test_update_prints_start_and_build_lines(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(loader, "_load_nappe", lambda con, years, **kw: (0, None, None))
    monkeypatch.setattr(loader, "_load_meteo", lambda con, keys, **kw: (0, None, None))
    dbp = tmp_path / "p.duckdb"
    loader.update(db_path=dbp)
    out = capsys.readouterr().out
    assert "update" in out          # start line names the mode
    assert str(dbp) in out          # start line names the DB path
    assert "nappe_pluie_daily" in out  # "building the derived table" line
    con = schema.connect(dbp)
    con.close()


def _run_update_with_fakes(dbp, monkeypatch, meteo_csv):
    """Run a real update() but with fake network (nappe fetch + meteo download)."""
    monkeypatch.setattr(config, "NAPPE_REQUEST_DELAY", 0)
    real_nappe = loader._load_nappe
    real_meteo = loader._load_meteo
    monkeypatch.setattr(
        loader, "_load_nappe",
        lambda con, years, **kw: real_nappe(con, years, fetch=_fake_nappe),
    )
    monkeypatch.setattr(
        loader, "_load_meteo",
        lambda con, keys, **kw: real_meteo(con, keys, download=_copy_download(meteo_csv)),
    )
    loader.update(db_path=dbp)


def test_format_summary_reports_counts_and_ranges(tmp_path, monkeypatch, meteo_csv):
    dbp = tmp_path / "s.duckdb"
    _run_update_with_fakes(dbp, monkeypatch, meteo_csv)
    con = schema.connect(dbp)
    s = loader.format_summary(con, "update")
    con.close()
    # mode + all three table names + their counts (4 nappe rows, 3 meteo rows)
    assert "update" in s
    assert "nappe_mesure=4" in s
    assert "meteo_jour=3" in s
    assert "nappe_pluie_daily=" in s
    # ingest_log rows from this run, with a date range arrow
    assert "hubeau" in s
    assert "meteofrance" in s
    assert "→" in s


def test_update_prints_summary(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(loader, "_load_nappe", lambda con, years, **kw: (0, None, None))
    monkeypatch.setattr(loader, "_load_meteo", lambda con, keys, **kw: (0, None, None))
    loader.update(db_path=tmp_path / "p.duckdb")
    out = capsys.readouterr().out
    assert "Résumé" in out
    assert "nappe_mesure=" in out


def test_load_nappe_upserts_all_piezos(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "NAPPE_REQUEST_DELAY", 0)
    con = _con(tmp_path)
    n, dmin, dmax = loader._load_nappe(con, [2024], fetch=_fake_nappe)
    assert n == len(config.PIEZOMETERS)
    # the loader reports the date range actually loaded (fed to ingest_log)
    assert dmin == dt.date(2024, 6, 1)
    assert dmax == dt.date(2024, 6, 1)
    count = con.execute("SELECT COUNT(*) FROM nappe_mesure").fetchone()[0]
    assert count == len(config.PIEZOMETERS)
    # idempotent: re-run does not duplicate
    loader._load_nappe(con, [2024], fetch=_fake_nappe)
    count2 = con.execute("SELECT COUNT(*) FROM nappe_mesure").fetchone()[0]
    assert count2 == len(config.PIEZOMETERS)
    con.close()


def _copy_download(meteo_csv, seen=None):
    def _dl(url, dest_dir):
        dest = Path(dest_dir) / "Q_33.csv"
        shutil.copy(meteo_csv, dest)
        if seen is not None:
            seen["dir"] = Path(dest_dir)
        return dest

    return _dl


def test_load_meteo_upserts_all_rows_and_columns(tmp_path, meteo_csv):
    con = _con(tmp_path)
    seen = {}
    n, dmin, dmax = loader._load_meteo(con, ["latest"], download=_copy_download(meteo_csv, seen))
    assert n == 3  # all Gironde stations kept, not just Cap-Ferret
    assert dmin == dt.date(2025, 1, 1)
    assert dmax == dt.date(2025, 1, 2)
    count = con.execute("SELECT COUNT(*) FROM meteo_jour").fetchone()[0]
    assert count == 3
    # every raw column landed; a column absent from the file is present as NULL
    cols = [r[1] for r in con.execute("PRAGMA table_info('meteo_jour')").fetchall()]
    for raw in config.METEO_COLUMNS:
        assert raw in cols
    assert con.execute("SELECT COUNT(*) FROM meteo_jour WHERE TX IS NOT NULL").fetchone()[0] == 0
    # date typed as DATE and the (NUM_POSTE, date) key holds (2 Cap-Ferret days)
    date_type = con.execute(
        "SELECT data_type FROM information_schema.columns "
        "WHERE table_name = 'meteo_jour' AND column_name = 'date'"
    ).fetchone()[0]
    assert date_type == "DATE"
    n_cf = con.execute(
        "SELECT COUNT(*) FROM meteo_jour WHERE NUM_POSTE = ?",
        [config.CAP_FERRET_NUM_POSTE],
    ).fetchone()[0]
    assert n_cf == 2
    # temp dir cleaned up
    assert not seen["dir"].exists()
    con.close()


def test_load_meteo_idempotent(tmp_path, meteo_csv):
    con = _con(tmp_path)
    loader._load_meteo(con, ["latest"], download=_copy_download(meteo_csv))
    loader._load_meteo(con, ["latest"], download=_copy_download(meteo_csv))
    assert con.execute("SELECT COUNT(*) FROM meteo_jour").fetchone()[0] == 3
    con.close()


def test_v_meteo_interest_only_returns_stations_of_interest(tmp_path, meteo_csv):
    con = _con(tmp_path)
    loader._load_meteo(con, ["latest"], download=_copy_download(meteo_csv))
    rows = con.execute("SELECT num_poste, rr FROM v_meteo_interest ORDER BY date").fetchall()
    # only Cap-Ferret (of_interest), station 33999999 excluded; TRY_CAST maps rr
    assert rows == [("33236002", 0.0), ("33236002", 5.5)]
    con.close()


def _seed_meteo_range(con, start, days, rr_value=1.0):
    dates = pd.date_range(start, periods=days, freq="D")
    df = pd.DataFrame({c: pd.NA for c in config.METEO_COLUMNS}, index=range(days))
    df["NUM_POSTE"] = config.CAP_FERRET_NUM_POSTE
    df["NOM_USUEL"] = "CAP-FERRET"
    df["AAAAMMJJ"] = dates.strftime("%Y%m%d")
    df["RR"] = str(rr_value)
    df["date"] = dates
    schema.upsert_dataframe(con, "meteo_jour", df, keys=["NUM_POSTE", "date"])


def test_rain_windows_null_until_full(tmp_path):
    con = _con(tmp_path)
    # 60 days from DAILY_START so a 56-day window can complete
    _seed_meteo_range(con, config.DAILY_START, 60, rr_value=1.0)
    out = loader.build_nappe_pluie_daily(con)
    out = out.set_index("date")
    first = pd.Timestamp(config.DAILY_START)
    # rr_7d: NULL for first 6 days, then 7.0
    assert pd.isna(out.loc[first + pd.Timedelta(days=5), "rr_7d"])
    assert out.loc[first + pd.Timedelta(days=6), "rr_7d"] == 7.0
    # rr_56d completes on day 56 (index 55)
    assert pd.isna(out.loc[first + pd.Timedelta(days=54), "rr_56d"])
    assert out.loc[first + pd.Timedelta(days=55), "rr_56d"] == 56.0


def test_nappe_interpolation_limit(tmp_path):
    con = _con(tmp_path)
    _seed_meteo_range(con, config.DAILY_START, 10)
    code = config.PIEZOMETERS[0]["code_bss"]
    col = config.PIEZOMETERS[0]["col"]
    start = pd.Timestamp(config.DAILY_START)
    # two points 5 days apart → gap of 4 interior days > limit 3
    df = pd.DataFrame({
        "code_bss": [code, code],
        "date_mesure": [start, start + pd.Timedelta(days=5)],
        "niveau_nappe_eau": [10.0, 10.0], "profondeur_nappe": [1.0, 6.0],
        "statut": ["s", "s"], "qualification": ["c", "c"], "mode_obtention": ["m", "m"],
        "code_producteur": ["1", "1"], "nom_producteur": ["p", "p"],
        "code_nature_mesure": ["N", "N"], "urn_bss": ["u", "u"],
        "timestamp_mesure": [1, 2],
    })
    schema.upsert_dataframe(con, "nappe_mesure", df, keys=["code_bss", "date_mesure"])
    out = loader.build_nappe_pluie_daily(con).set_index("date")
    # endpoints present
    assert out.loc[start, col] == 1.0
    assert out.loc[start + pd.Timedelta(days=5), col] == 6.0
    # interior gap of 4 days exceeds limit=3 → at least one NaN remains
    interior = out.loc[start + pd.Timedelta(days=1):start + pd.Timedelta(days=4), col]
    assert interior.isna().any()
    con.close()


def test_empty_build_has_stable_column_types(tmp_path):
    # An empty DB must still produce DOUBLE value columns and a DATE date column,
    # not INTEGER/TIMESTAMP from scalar pd.NA fills and a datetime64 index.
    con = _con(tmp_path)
    loader.build_nappe_pluie_daily(con)
    types = {
        r[1]: r[2]
        for r in con.execute("PRAGMA table_info('nappe_pluie_daily')").fetchall()
    }
    assert types["date"] == "DATE"
    assert types["rr"] == "DOUBLE"
    for w in config.RAIN_WINDOWS:
        assert types[f"rr_{w}d"] == "DOUBLE"
    for p in config.PIEZOMETERS:
        assert types[p["col"]] == "DOUBLE"
    con.close()


def test_build_creates_table(tmp_path):
    con = _con(tmp_path)
    _seed_meteo_range(con, config.DAILY_START, 10)
    loader.build_nappe_pluie_daily(con)
    cols = [r[1] for r in con.execute("PRAGMA table_info('nappe_pluie_daily')").fetchall()]
    assert "date" in cols and "rr" in cols
    for w in config.RAIN_WINDOWS:
        assert f"rr_{w}d" in cols
    for p in config.PIEZOMETERS:
        assert p["col"] in cols
    con.close()


def _seed_meteo_on_dates(con, dates):
    df = pd.DataFrame({c: pd.NA for c in config.METEO_COLUMNS}, index=range(len(dates)))
    df["NUM_POSTE"] = config.CAP_FERRET_NUM_POSTE
    df["NOM_USUEL"] = "CAP-FERRET"
    df["AAAAMMJJ"] = [d.replace("-", "") for d in dates]
    df["RR"] = "1.0"
    df["date"] = pd.to_datetime(dates)
    schema.upsert_dataframe(con, "meteo_jour", df, keys=["NUM_POSTE", "date"])


def test_load_events_populates_tables(tmp_path):
    con = _con(tmp_path)
    loader._load_events(con)
    assert con.execute("SELECT COUNT(*) FROM hc_period").fetchone()[0] == 9
    assert con.execute("SELECT COUNT(*) FROM interdiction_period").fetchone()[0] == 4
    types = {r[1]: r[2] for r in con.execute("PRAGMA table_info('hc_period')").fetchall()}
    assert types["verified"] == "BOOLEAN"
    assert types["start_date"] == "DATE"
    con.close()


def test_event_list_columns_roundtrip(tmp_path):
    con = _con(tmp_path)
    loader._load_events(con)
    rows = con.execute(
        "SELECT UNNEST(communes) FROM hc_period WHERE label LIKE 'HC 2023%'"
    ).fetchall()
    assert {r[0] for r in rows} == {
        "Andernos", "Lanton", "Arès", "Gujan-Mestras", "La Teste", "Audenge",
    }
    con.close()


def test_load_events_idempotent(tmp_path):
    con = _con(tmp_path)
    loader._load_events(con)
    loader._load_events(con)
    assert con.execute("SELECT COUNT(*) FROM hc_period").fetchone()[0] == 9
    assert con.execute("SELECT COUNT(*) FROM interdiction_period").fetchone()[0] == 4
    con.close()


def test_v_nappe_pluie_events_flags(tmp_path):
    con = _con(tmp_path)
    # daily index must span the event dates (up to early 2024)
    _seed_meteo_on_dates(con, ["2015-01-01", "2024-02-01"])
    loader.build_nappe_pluie_daily(con)
    loader._load_events(con)
    schema.create_event_views(con)

    def flags(d):
        return con.execute(
            "SELECT in_hc, in_interdiction FROM v_nappe_pluie_events WHERE date = ?",
            [dt.date.fromisoformat(d)],
        ).fetchone()

    assert flags("2023-11-15") == (True, False)   # inside HC 2023, no interdiction then
    assert flags("2019-07-01") == (False, False)  # normal day
    assert flags("2024-01-05") == (False, True)   # inside 2023-12-27→2024-01-19 interdiction
    con.close()


def test_update_loads_current_year_and_latest(tmp_path, monkeypatch):
    calls = {}

    def fake_load_nappe(con, years, **kw):
        calls["nappe_years"] = list(years)
        return 0, None, None

    def fake_load_meteo(con, keys, **kw):
        calls["meteo_keys"] = list(keys)
        return 0, None, None

    monkeypatch.setattr(loader, "_load_nappe", fake_load_nappe)
    monkeypatch.setattr(loader, "_load_meteo", fake_load_meteo)

    year = dt.date.today().year
    loader.update(db_path=tmp_path / "u.duckdb")
    # previous + current year, so January runs still catch late-December points
    # and prior-year requalifications.
    assert calls["nappe_years"] == [year - 1, year]
    assert calls["meteo_keys"] == ["latest"]


def test_rebuild_loads_all_years_and_files(tmp_path, monkeypatch):
    calls = {}
    # Non-zero counts: zero now means "source down" and aborts the rebuild.
    monkeypatch.setattr(
        loader, "_load_nappe",
        lambda con, years, **kw: calls.__setitem__("years", list(years)) or (7, None, None),
    )
    monkeypatch.setattr(
        loader, "_load_meteo",
        lambda con, keys, **kw: calls.__setitem__("keys", list(keys)) or (9, None, None),
    )
    # Keep the test hermetic: the success path refreshes the field descriptor.
    monkeypatch.setattr(loader.sources, "download_meteo_descriptor", lambda dest: None)

    loader.rebuild(db_path=tmp_path / "r.duckdb")
    assert calls["years"][0] == config.NAPPE_START_YEAR
    assert calls["years"][-1] == dt.date.today().year
    assert set(calls["keys"]) == set(config.METEO_URLS)


def test_rebuild_is_atomic_on_failure(tmp_path, monkeypatch):
    # A rebuild that fails mid-fetch must not leave an emptied DB: it drops
    # everything first, so without a transaction a flaky fetch wipes the data.
    dbp = tmp_path / "atomic.duckdb"
    con = schema.connect(dbp)
    schema.create_all(con)
    schema.seed_stations(con)
    schema.upsert_dataframe(
        con, "nappe_mesure", _fake_nappe("Z/F", 2020),
        keys=["code_bss", "date_mesure"],
    )
    before = con.execute("SELECT COUNT(*) FROM nappe_mesure").fetchone()[0]
    con.close()
    assert before == 1

    def _boom(con, years, **kw):
        raise RuntimeError("network down")

    monkeypatch.setattr(loader, "_load_nappe", _boom)

    with pytest.raises(RuntimeError):
        loader.rebuild(db_path=dbp)

    con = schema.connect(dbp)
    after = con.execute("SELECT COUNT(*) FROM nappe_mesure").fetchone()[0]
    con.close()
    assert after == before  # prior data preserved by rollback


def test_rebuild_aborts_when_source_returns_nothing(tmp_path, monkeypatch):
    # A source outage can answer HTTP 200 with zero rows (Hub'eau did exactly
    # that). Since rebuild drops before reloading, committing that would replace
    # good data with an empty table. It must abort and roll back instead.
    dbp = tmp_path / "empty_source.duckdb"
    con = schema.connect(dbp)
    schema.create_all(con)
    schema.seed_stations(con)
    schema.upsert_dataframe(
        con, "nappe_mesure", _fake_nappe("Z/F", 2020),
        keys=["code_bss", "date_mesure"],
    )
    before = con.execute("SELECT COUNT(*) FROM nappe_mesure").fetchone()[0]
    con.close()
    assert before == 1

    # fetch "succeeds" but yields nothing, as during the outage
    monkeypatch.setattr(loader, "_load_nappe", lambda con, years, **kw: (0, None, None))
    monkeypatch.setattr(loader, "_load_meteo", lambda con, keys, **kw: (5, None, None))

    with pytest.raises(RuntimeError, match="aucune mesure de nappe"):
        loader.rebuild(db_path=dbp)

    con = schema.connect(dbp)
    after = con.execute("SELECT COUNT(*) FROM nappe_mesure").fetchone()[0]
    con.close()
    assert after == before  # existing data survived the outage


def test_rebuild_aborts_when_meteo_returns_nothing(tmp_path, monkeypatch):
    dbp = tmp_path / "empty_meteo.duckdb"
    con = schema.connect(dbp)
    schema.create_all(con)
    schema.seed_stations(con)
    schema.upsert_dataframe(
        con, "nappe_mesure", _fake_nappe("Z/F", 2020),
        keys=["code_bss", "date_mesure"],
    )
    con.close()

    monkeypatch.setattr(loader, "_load_nappe", lambda con, years, **kw: (3, None, None))
    monkeypatch.setattr(loader, "_load_meteo", lambda con, keys, **kw: (0, None, None))

    with pytest.raises(RuntimeError, match="Météo-France"):
        loader.rebuild(db_path=dbp)

    con = schema.connect(dbp)
    assert con.execute("SELECT COUNT(*) FROM nappe_mesure").fetchone()[0] == 1
    con.close()


def test_update_is_atomic_on_failure(tmp_path, monkeypatch):
    # If meteo fails after nappe succeeded, an un-transactional update would
    # commit the raw nappe change while leaving nappe_pluie_daily and ingest_log
    # stale -> raw/derived go inconsistent. The whole update must be atomic.
    dbp = tmp_path / "atomic_update.duckdb"
    code = config.PIEZOMETERS[0]["code_bss"]
    con = schema.connect(dbp)
    schema.create_all(con)
    schema.seed_stations(con)
    schema.upsert_dataframe(
        con, "nappe_mesure", _fake_nappe(code, 2020),  # profondeur_nappe = 1.0
        keys=["code_bss", "date_mesure"],
    )
    loader.build_nappe_pluie_daily(con)
    loader._log(con, "hubeau", "seed", "update", 1, dt.date(2020, 6, 1), dt.date(2020, 6, 1))
    before_nappe = con.execute(
        "SELECT COUNT(*), COALESCE(SUM(profondeur_nappe), 0) FROM nappe_mesure"
    ).fetchone()
    before_daily = con.execute("SELECT COUNT(*) FROM nappe_pluie_daily").fetchone()[0]
    before_log = con.execute("SELECT COUNT(*) FROM ingest_log").fetchone()[0]
    con.close()

    def _mutate_nappe(con, years, **kw):
        changed = _fake_nappe(code, 2020).assign(profondeur_nappe=[2.0])
        n = schema.upsert_dataframe(
            con, "nappe_mesure", changed, keys=["code_bss", "date_mesure"]
        )
        return n, dt.date(2020, 6, 1), dt.date(2020, 6, 1)

    def _boom(con, keys, **kw):
        raise RuntimeError("meteo down")

    monkeypatch.setattr(loader, "_load_nappe", _mutate_nappe)
    monkeypatch.setattr(loader, "_load_meteo", _boom)

    with pytest.raises(RuntimeError):
        loader.update(db_path=dbp)

    con = schema.connect(dbp)
    after_nappe = con.execute(
        "SELECT COUNT(*), COALESCE(SUM(profondeur_nappe), 0) FROM nappe_mesure"
    ).fetchone()
    after_daily = con.execute("SELECT COUNT(*) FROM nappe_pluie_daily").fetchone()[0]
    after_log = con.execute("SELECT COUNT(*) FROM ingest_log").fetchone()[0]
    con.close()
    # No partial commit: nappe depth still 1.0, daily and log untouched.
    assert after_nappe == before_nappe
    assert after_daily == before_daily
    assert after_log == before_log


def test_update_writes_ingest_log_with_date_range(tmp_path, monkeypatch):
    monkeypatch.setattr(
        loader, "_load_nappe",
        lambda con, years, **kw: (5, dt.date(2024, 1, 1), dt.date(2024, 6, 1)),
    )
    monkeypatch.setattr(
        loader, "_load_meteo",
        lambda con, keys, **kw: (3, dt.date(2025, 1, 1), dt.date(2025, 1, 2)),
    )
    year = dt.date.today().year
    dbp = tmp_path / "l.duckdb"
    loader.update(db_path=dbp)
    con = schema.connect(dbp)
    rows = con.execute(
        "SELECT source, scope, mode, rows_upserted, date_min, date_max "
        "FROM ingest_log ORDER BY source"
    ).fetchall()
    assert rows == [
        ("hubeau", f"nappe {year - 1}-{year}", "update", 5, dt.date(2024, 1, 1), dt.date(2024, 6, 1)),
        ("meteofrance", "meteo latest", "update", 3, dt.date(2025, 1, 1), dt.date(2025, 1, 2)),
    ]
    con.close()


ENKI_HEADER = (
    "ID,Date début,Date fin,Point,Latitude,Longitude,Sonde ou laboratoire,"
    "Profondeur,Heure début,Heure fin,Étendue d’eau,Bassin versant,"
    "Justification du point d’échantillonnage,Entérocoques,Escherichia coli\n"
)
ENKI_UNITS = ",,,,,,,,,,,,,UFC/100mL,UFC/100mL\n"


def _enki_csv(path, rows):
    path.write_text(ENKI_HEADER + ENKI_UNITS + "".join(rows), encoding="utf-8")


def test_load_enki_parses_and_skips_units_row(tmp_path):
    d = tmp_path / "enki"
    d.mkdir()
    _enki_csv(d / "Export_siba_2023.csv", [
        "1,2023-01-19,2023-01-19,0804-CDL,44.6,-1.1,LPL,,09:00,09:05,E,BV,ND,63.0,327.0\n",
        "2,2023-02-02,2023-02-02,0805-RDB,44.7,-1.0,SIBA,,10:00,10:05,E,BV,ND,<10.0,>2419.6\n",
    ])
    con = schema.connect(tmp_path / "e.duckdb")
    schema.create_all(con)
    n, lo, hi = loader._load_enki(con, d)
    assert n == 2  # la ligne d'unités n'est pas une donnée
    assert (lo, hi) == (dt.date(2023, 1, 19), dt.date(2023, 2, 2))
    rows = con.execute(
        "SELECT ecoli, ecoli_censure, entero, entero_censure FROM analyse_bacterio "
        "ORDER BY date_prelevement"
    ).fetchall()
    con.close()
    assert rows[0] == (327.0, "=", 63.0, "=")
    # valeurs censurées : la borne est conservée ET signalée
    assert rows[1] == (2419.6, ">", 10.0, "<")


def test_load_enki_replaces_year_and_is_idempotent(tmp_path):
    d = tmp_path / "enki"
    d.mkdir()
    f = d / "Export_siba_2023.csv"
    _enki_csv(f, ["1,2023-01-19,2023-01-19,P,44.6,-1.1,LPL,,09:00,09:05,E,BV,ND,63.0,327.0\n"])
    con = schema.connect(tmp_path / "e.duckdb")
    schema.create_all(con)
    loader._load_enki(con, d)
    loader._load_enki(con, d)  # rejouer ne duplique pas
    assert con.execute("SELECT COUNT(*) FROM analyse_bacterio").fetchone()[0] == 1

    # un export corrigé remplace l'année au lieu de s'y ajouter
    _enki_csv(f, [
        "1,2023-01-19,2023-01-19,P,44.6,-1.1,LPL,,09:00,09:05,E,BV,ND,63.0,999.0\n",
        "2,2023-03-01,2023-03-01,Q,44.7,-1.0,SIBA,,10:00,10:05,E,BV,ND,20.0,50.0\n",
    ])
    loader._load_enki(con, d)
    n, ecoli = con.execute(
        "SELECT COUNT(*), max(ecoli) FROM analyse_bacterio"
    ).fetchone()
    con.close()
    assert (n, ecoli) == (2, 999.0)


def test_load_enki_tolerates_missing_measure_columns(tmp_path):
    # Le portail omet les colonnes de mesure pour les années sans analyse.
    d = tmp_path / "enki"
    d.mkdir()
    (d / "Export_siba_2012.csv").write_text(
        "ID,Date début,Date fin,Point,Latitude,Longitude,Sonde ou laboratoire,"
        "Profondeur,Heure début,Heure fin,Étendue d’eau,Bassin versant,"
        "Justification du point d’échantillonnage\n"
        "9,2012-05-05,2012-05-05,P,44.6,-1.1,LPL,,09:00,09:05,E,BV,ND\n",
        encoding="utf-8",
    )
    con = schema.connect(tmp_path / "e.duckdb")
    schema.create_all(con)
    n, _, _ = loader._load_enki(con, d)
    got = con.execute("SELECT ecoli, entero FROM analyse_bacterio").fetchone()
    con.close()
    assert n == 1 and got == (None, None)


def test_load_enki_missing_directory_deletes_nothing(tmp_path):
    con = schema.connect(tmp_path / "e.duckdb")
    schema.create_all(con)
    con.execute("INSERT INTO analyse_bacterio (annee, point) VALUES (2023, 'P')")
    n, lo, hi = loader._load_enki(con, tmp_path / "absent")
    kept = con.execute("SELECT COUNT(*) FROM analyse_bacterio").fetchone()[0]
    con.close()
    assert (n, lo, hi) == (0, None, None)
    assert kept == 1  # pas de dossier : on ne touche à rien
