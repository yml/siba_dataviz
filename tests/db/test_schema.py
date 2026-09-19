import pandas as pd

from siba.db import config, schema


def _tables(con):
    rows = con.execute(
        "SELECT table_name FROM information_schema.tables"
    ).fetchall()
    return {r[0] for r in rows}


def test_create_all_makes_tables_and_view(con):
    # `con` already ran create_all once; a second call must be idempotent.
    schema.create_all(con)
    names = _tables(con)
    assert {"station", "nappe_mesure", "meteo_jour", "ingest_log"} <= names
    # view is queryable
    con.execute("SELECT * FROM v_meteo_interest LIMIT 0")


def test_create_all_makes_event_tables(con):
    names = _tables(con)
    assert {"hc_period", "interdiction_period"} <= names
    hc = {r[1]: r[2] for r in con.execute("PRAGMA table_info('hc_period')").fetchall()}
    assert hc["communes"] == "VARCHAR[]"
    assert hc["verified"] == "BOOLEAN"
    assert hc["start_date"] == "DATE"
    it = {r[1]: r[2] for r in con.execute("PRAGMA table_info('interdiction_period')").fetchall()}
    assert it["especes"] == "VARCHAR[]"
    assert it["peche_loisir"] == "BOOLEAN"


def test_drop_all_removes_event_tables(tmp_path):
    c = schema.connect(tmp_path / "d.duckdb")
    schema.create_all(c)
    schema.drop_all(c)
    names = _tables(c)
    assert "hc_period" not in names
    assert "interdiction_period" not in names
    c.close()


def test_meteo_jour_has_all_raw_columns_plus_date(con):
    cols = [r[1] for r in con.execute("PRAGMA table_info('meteo_jour')").fetchall()]
    assert "date" in cols
    for raw in config.METEO_COLUMNS:
        assert raw in cols


def test_upsert_dataframe_inserts_then_updates(con):
    df = pd.DataFrame(
        {"code_bss": ["A/F"], "date_mesure": ["2020-01-01"],
         "profondeur_nappe": [1.0]}
    )
    n = schema.upsert_dataframe(con, "nappe_mesure", df, keys=["code_bss", "date_mesure"])
    assert n == 1
    # re-insert same key, changed value → update, not duplicate
    df2 = df.assign(profondeur_nappe=[2.0])
    schema.upsert_dataframe(con, "nappe_mesure", df2, keys=["code_bss", "date_mesure"])
    rows = con.execute("SELECT COUNT(*), MAX(profondeur_nappe) FROM nappe_mesure").fetchone()
    assert rows == (1, 2.0)


def test_upsert_dataframe_dedups_within_batch_keep_last(con):
    # Two rows with the same key in ONE batch: DuckDB ON CONFLICT keeps the
    # first, so a requalified later duplicate would be lost. We must keep last.
    df = pd.DataFrame(
        {"code_bss": ["A/F", "A/F"],
         "date_mesure": ["2020-01-01", "2020-01-01"],
         "profondeur_nappe": [1.0, 2.0]}
    )
    n = schema.upsert_dataframe(con, "nappe_mesure", df, keys=["code_bss", "date_mesure"])
    assert n == 1
    rows = con.execute("SELECT COUNT(*), MAX(profondeur_nappe) FROM nappe_mesure").fetchone()
    assert rows == (1, 2.0)


def test_seed_stations_marks_of_interest(con):
    schema.seed_stations(con)
    n_interest = con.execute(
        "SELECT COUNT(*) FROM station WHERE of_interest"
    ).fetchone()[0]
    assert n_interest == len(config.METEO_STATIONS_OF_INTEREST)
    n_piezo = con.execute(
        "SELECT COUNT(*) FROM station WHERE source = 'hubeau'"
    ).fetchone()[0]
    assert n_piezo == len(config.PIEZOMETERS)
