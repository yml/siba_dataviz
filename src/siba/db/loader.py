"""Orchestration du chargement DuckDB (faits, dérivé, journal)."""

from __future__ import annotations

import tempfile
from pathlib import Path

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
            out[p["col"]] = pd.NA
            continue
        ts = sub.set_index(pd.to_datetime(sub["date_mesure"]))["profondeur_nappe"]
        ts = ts[~ts.index.duplicated(keep="last")]
        ts_daily = ts.resample("D").mean().interpolate(method="time", limit=config.INTERP_LIMIT)
        out[p["col"]] = ts_daily.reindex(idx)

    # Pluie : fenêtres calculées sur la série complète Cap-Ferret, puis découpe.
    if meteo.empty:
        out["rr"] = pd.NA
        for w in config.RAIN_WINDOWS:
            out[f"rr_{w}d"] = pd.NA
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

    con.execute("DROP TABLE IF EXISTS nappe_pluie_daily")
    con.register("_daily_df", out)
    con.execute("CREATE TABLE nappe_pluie_daily AS SELECT * FROM _daily_df")
    con.unregister("_daily_df")
    return out


def update(db_path=None):
    raise NotImplementedError


def rebuild(db_path=None):
    raise NotImplementedError
