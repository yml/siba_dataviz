"""Orchestration du chargement DuckDB (faits, dérivé, journal)."""

from __future__ import annotations

import datetime as dt
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from . import config, schema, sources


def _load_nappe(con, years, *, fetch=sources.fetch_nappe_year) -> int:
    total = 0
    for p in config.PIEZOMETERS:
        for year in years:
            df = fetch(p["code_bss"], year)
            total += schema.upsert_dataframe(
                con, "nappe_mesure", df, keys=["code_bss", "date_mesure"]
            )
    return total


def _load_meteo(
    con,
    url_keys,
    *,
    download=sources.download_meteo_file,
    read=sources.read_meteo_csv,
) -> int:
    total = 0
    for key in url_keys:
        url = config.METEO_URLS[key]
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = download(url, tmp)
            df = read(csv_path)
            total += schema.upsert_dataframe(
                con, "meteo_jour", df, keys=["NUM_POSTE", "date"]
            )
    return total


def build_nappe_pluie_daily(con):
    """Reconstruit la table matérialisée nappe + pluie (basée Cap-Ferret)."""
    meteo = con.execute(
        'SELECT "date", TRY_CAST("RR" AS DOUBLE) AS rr '
        'FROM meteo_jour WHERE "NUM_POSTE" = ? ORDER BY "date"',
        [config.CAP_FERRET_NUM_POSTE],
    ).df()
    nappe = con.execute(
        "SELECT code_bss, date_mesure, profondeur_nappe "
        "FROM nappe_mesure ORDER BY date_mesure"
    ).df()

    start = pd.Timestamp(config.DAILY_START)

    # Fin = dernière date disponible (météo ou nappe).
    ends = [d for d in (
        pd.to_datetime(meteo["date"]).max() if not meteo.empty else None,
        pd.to_datetime(nappe["date_mesure"]).max() if not nappe.empty else None,
    ) if pd.notna(d)]
    if not ends:
        end = start
    else:
        end = max(ends)

    idx = pd.date_range(start, end, freq="D")
    out = pd.DataFrame(index=idx)
    out.index.name = "date"

    # Nappes : resample journalier + interpolation temporelle (limit).
    for p in config.PIEZOMETERS:
        sub = nappe[nappe["code_bss"] == p["code_bss"]]
        if sub.empty:
            out[p["col"]] = pd.Series(np.nan, index=idx, dtype="float64")
            continue
        ts = sub.set_index(pd.to_datetime(sub["date_mesure"]))["profondeur_nappe"]
        ts = ts[~ts.index.duplicated(keep="last")]
        ts_daily = ts.resample("D").mean().interpolate(method="time", limit=config.INTERP_LIMIT)
        out[p["col"]] = ts_daily.reindex(idx)

    # Pluie : fenêtres calculées sur la série complète Cap-Ferret, puis découpe.
    if meteo.empty:
        out["rr"] = pd.Series(np.nan, index=idx, dtype="float64")
        for w in config.RAIN_WINDOWS:
            out[f"rr_{w}d"] = pd.Series(np.nan, index=idx, dtype="float64")
    else:
        rr_full = meteo.set_index(pd.to_datetime(meteo["date"]))["rr"].sort_index()
        rr_full = rr_full[~rr_full.index.duplicated(keep="last")]
        full_idx = pd.date_range(rr_full.index.min(), end, freq="D")
        rr_full = rr_full.reindex(full_idx)
        windows = {f"rr_{w}d": rr_full.rolling(w, min_periods=w).sum() for w in config.RAIN_WINDOWS}
        out["rr"] = rr_full.reindex(idx)
        for name, series in windows.items():
            out[name] = series.reindex(idx)

    out = out.reset_index()

    # Cast `date` to a real DATE in the materialized table (a datetime64 index
    # otherwise lands as TIMESTAMP); the returned DataFrame keeps Timestamps.
    select_cols = ", ".join(
        'CAST("date" AS DATE) AS "date"' if c == "date" else f'"{c}"'
        for c in out.columns
    )
    con.execute("DROP TABLE IF EXISTS nappe_pluie_daily")
    con.register("_daily_df", out)
    con.execute(f"CREATE TABLE nappe_pluie_daily AS SELECT {select_cols} FROM _daily_df")
    con.unregister("_daily_df")
    return out


def _enrich_stations(con) -> None:
    """Complète name/lat/lon/alti des stations météo depuis les données."""
    con.execute(
        """
        UPDATE station AS s
        SET name = m.name, lat = m.lat, lon = m.lon, alti = m.alti
        FROM (
            SELECT "NUM_POSTE" AS num_poste,
                   any_value("NOM_USUEL") AS name,
                   any_value(TRY_CAST("LAT"  AS DOUBLE)) AS lat,
                   any_value(TRY_CAST("LON"  AS DOUBLE)) AS lon,
                   any_value(TRY_CAST("ALTI" AS DOUBLE)) AS alti
            FROM meteo_jour GROUP BY "NUM_POSTE"
        ) AS m
        WHERE s.num_poste = m.num_poste
        """
    )


def _log(con, source, scope, mode, rows) -> None:
    con.execute(
        "INSERT INTO ingest_log (source, scope, mode, rows_upserted, "
        "date_min, date_max, fetched_at) VALUES (?, ?, ?, ?, NULL, NULL, ?)",
        [source, scope, mode, rows, dt.datetime.now()],
    )


def update(db_path=None) -> None:
    db_path = config.DB_PATH if db_path is None else db_path
    con = schema.connect(db_path)
    try:
        schema.ensure(con)
        schema.seed_stations(con)
        year = dt.date.today().year
        n_nappe = _load_nappe(con, [year])
        n_meteo = _load_meteo(con, ["latest"])
        _enrich_stations(con)
        build_nappe_pluie_daily(con)
        _log(con, "hubeau", f"nappe {year}", "update", n_nappe)
        _log(con, "meteofrance", "meteo latest", "update", n_meteo)
    finally:
        con.close()


def rebuild(db_path=None) -> None:
    db_path = config.DB_PATH if db_path is None else db_path
    con = schema.connect(db_path)
    try:
        schema.drop_all(con)
        schema.create_all(con)
        schema.seed_stations(con)
        years = list(range(config.NAPPE_START_YEAR, dt.date.today().year + 1))
        n_nappe = _load_nappe(con, years)
        n_meteo = _load_meteo(con, list(config.METEO_URLS))
        _enrich_stations(con)
        build_nappe_pluie_daily(con)
        _log(con, "hubeau", f"nappe {years[0]}-{years[-1]}", "rebuild", n_nappe)
        _log(con, "meteofrance", "meteo all", "rebuild", n_meteo)
    finally:
        con.close()
