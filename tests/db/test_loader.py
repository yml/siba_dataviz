import pandas as pd

from siba.db import config, loader, schema, sources


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


def test_load_nappe_upserts_all_piezos(tmp_path):
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


def test_load_meteo_upserts_and_cleans_temp(tmp_path, meteo_csv):
    con = _con(tmp_path)
    seen = {}

    def _dl(url, dest_dir):
        # simulate download by copying fixture into the temp dir
        import shutil
        from pathlib import Path
        dest = Path(dest_dir) / "Q_33.csv"
        shutil.copy(meteo_csv, dest)
        seen["dir"] = Path(dest_dir)
        return dest

    n = loader._load_meteo(con, ["latest"], download=_dl, read=sources.read_meteo_csv)
    assert n == 3
    count = con.execute("SELECT COUNT(*) FROM meteo_jour").fetchone()[0]
    assert count == 3
    # temp dir cleaned
    assert not seen["dir"].exists()
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
