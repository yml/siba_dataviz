"""Schéma DuckDB : tables de faits, dimension, vues, upsert idempotent."""

from __future__ import annotations

import os
from pathlib import Path

import duckdb
import pandas as pd

from . import config


def connect(db_path: str | os.PathLike) -> duckdb.DuckDBPyConnection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(db_path))


def _meteo_columns_ddl() -> str:
    # Toutes les colonnes brutes en VARCHAR (verbatim, sans perte) + date typée.
    cols = ['"date" DATE'] + [f'"{c}" VARCHAR' for c in config.METEO_COLUMNS]
    cols.append('PRIMARY KEY ("NUM_POSTE", "date")')
    return ",\n    ".join(cols)


def create_all(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS station (
            station_id  VARCHAR PRIMARY KEY,
            source      VARCHAR,
            name        VARCHAR,
            lat         DOUBLE,
            lon         DOUBLE,
            alti        DOUBLE,
            code_bss    VARCHAR,
            num_poste   VARCHAR,
            of_interest BOOLEAN DEFAULT FALSE
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS nappe_mesure (
            code_bss           VARCHAR,
            date_mesure        DATE,
            niveau_nappe_eau   DOUBLE,
            profondeur_nappe   DOUBLE,
            statut             VARCHAR,
            qualification      VARCHAR,
            mode_obtention     VARCHAR,
            code_producteur    VARCHAR,
            nom_producteur     VARCHAR,
            code_nature_mesure VARCHAR,
            urn_bss            VARCHAR,
            timestamp_mesure   BIGINT,
            PRIMARY KEY (code_bss, date_mesure)
        )
        """
    )
    con.execute(f"CREATE TABLE IF NOT EXISTS meteo_jour (\n    {_meteo_columns_ddl()}\n)")
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS ingest_log (
            source        VARCHAR,
            scope         VARCHAR,
            mode          VARCHAR,
            rows_upserted BIGINT,
            date_min      DATE,
            date_max      DATE,
            fetched_at    TIMESTAMP
        )
        """
    )
    con.execute(
        """
        CREATE OR REPLACE VIEW v_meteo_interest AS
        SELECT
            m."NUM_POSTE"                AS num_poste,
            m."NOM_USUEL"               AS name,
            m."date"                    AS date,
            TRY_CAST(m."RR"  AS DOUBLE) AS rr,
            TRY_CAST(m."QRR" AS INTEGER) AS qrr,
            TRY_CAST(m."TN"  AS DOUBLE) AS tn,
            TRY_CAST(m."TX"  AS DOUBLE) AS tx,
            TRY_CAST(m."TM"  AS DOUBLE) AS tm,
            TRY_CAST(m."FFM" AS DOUBLE) AS ffm,
            TRY_CAST(m."FXY" AS DOUBLE) AS fxy
        FROM meteo_jour m
        JOIN station s ON s.num_poste = m."NUM_POSTE" AND s.of_interest
        """
    )


def drop_all(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("DROP VIEW IF EXISTS v_meteo_interest")
    for t in ("ingest_log", "meteo_jour", "nappe_mesure", "station", "nappe_pluie_daily"):
        con.execute(f"DROP TABLE IF EXISTS {t}")


def upsert_dataframe(
    con: duckdb.DuckDBPyConnection,
    table: str,
    df: pd.DataFrame,
    keys: list[str],
) -> int:
    if df.empty:
        return 0
    # A same-key duplicate later in the same batch is a requalified value; keep
    # it. DuckDB ON CONFLICT keeps the first of two same-key rows in one INSERT
    # (and can even reject updating the same row twice), so dedup keep-last here.
    df = df.drop_duplicates(subset=keys, keep="last")
    cols = list(df.columns)
    con.register("_upsert_df", df)
    collist = ", ".join(f'"{c}"' for c in cols)
    keylist = ", ".join(f'"{c}"' for c in keys)
    update_cols = [c for c in cols if c not in keys]
    if update_cols:
        setlist = ", ".join(f'"{c}" = excluded."{c}"' for c in update_cols)
        conflict = f"DO UPDATE SET {setlist}"
    else:
        conflict = "DO NOTHING"
    con.execute(
        f'INSERT INTO {table} ({collist}) SELECT {collist} FROM _upsert_df '
        f'ON CONFLICT ({keylist}) {conflict}'
    )
    con.unregister("_upsert_df")
    return len(df)


def seed_stations(con: duckdb.DuckDBPyConnection) -> None:
    rows = []
    for p in config.PIEZOMETERS:
        rows.append({
            "station_id": p["station_id"], "source": "hubeau", "name": p["name"],
            "lat": None, "lon": None, "alti": None,
            "code_bss": p["code_bss"], "num_poste": None, "of_interest": False,
        })
    for s in config.METEO_STATIONS_OF_INTEREST:
        rows.append({
            "station_id": s["station_id"], "source": "meteofrance", "name": s["name"],
            "lat": None, "lon": None, "alti": None,
            "code_bss": None, "num_poste": s["num_poste"], "of_interest": True,
        })
    upsert_dataframe(con, "station", pd.DataFrame(rows), keys=["station_id"])
