import datetime as dt
import shutil
from pathlib import Path

import pandas as pd

from siba.db import config, loader, schema


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


def test_load_nappe_upserts_all_piezos(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "NAPPE_REQUEST_DELAY", 0)
    con = _con(tmp_path)
    n = loader._load_nappe(con, [2024], fetch=_fake_nappe)
    assert n == len(config.PIEZOMETERS)
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
    n = loader._load_meteo(con, ["latest"], download=_copy_download(meteo_csv, seen))
    assert n == 3  # all Gironde stations kept, not just Cap-Ferret
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


def test_update_loads_current_year_and_latest(tmp_path, monkeypatch):
    calls = {}

    def fake_load_nappe(con, years, **kw):
        calls["nappe_years"] = list(years)
        return 0

    def fake_load_meteo(con, keys, **kw):
        calls["meteo_keys"] = list(keys)
        return 0

    monkeypatch.setattr(loader, "_load_nappe", fake_load_nappe)
    monkeypatch.setattr(loader, "_load_meteo", fake_load_meteo)

    loader.update(db_path=tmp_path / "u.duckdb")
    assert calls["nappe_years"] == [dt.date.today().year]
    assert calls["meteo_keys"] == ["latest"]


def test_rebuild_loads_all_years_and_files(tmp_path, monkeypatch):
    calls = {}
    monkeypatch.setattr(loader, "_load_nappe",
                        lambda con, years, **kw: calls.__setitem__("years", list(years)) or 0)
    monkeypatch.setattr(loader, "_load_meteo",
                        lambda con, keys, **kw: calls.__setitem__("keys", list(keys)) or 0)

    loader.rebuild(db_path=tmp_path / "r.duckdb")
    assert calls["years"][0] == config.NAPPE_START_YEAR
    assert calls["years"][-1] == dt.date.today().year
    assert set(calls["keys"]) == set(config.METEO_URLS)


def test_update_writes_ingest_log(tmp_path, monkeypatch):
    monkeypatch.setattr(loader, "_load_nappe", lambda con, years, **kw: 5)
    monkeypatch.setattr(loader, "_load_meteo", lambda con, keys, **kw: 3)
    dbp = tmp_path / "l.duckdb"
    loader.update(db_path=dbp)
    con = schema.connect(dbp)
    n = con.execute("SELECT COUNT(*) FROM ingest_log WHERE mode = 'update'").fetchone()[0]
    assert n >= 1
    con.close()
