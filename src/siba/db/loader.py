"""Orchestration du chargement DuckDB (faits, dérivé, journal)."""

from __future__ import annotations

import tempfile
from pathlib import Path

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


def update(db_path=None):
    raise NotImplementedError


def rebuild(db_path=None):
    raise NotImplementedError
