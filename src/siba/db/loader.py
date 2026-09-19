"""Orchestration du chargement DuckDB (faits, dérivé, journal)."""

from __future__ import annotations

import datetime as dt
import tempfile
import time

import numpy as np
import pandas as pd

from . import config, schema, sources


def _as_date(value):
    """Normalise un Timestamp/date/None en ``datetime.date`` (ou None)."""
    if value is None or pd.isna(value):
        return None
    return pd.Timestamp(value).date()


def _span(lo, hi, other_lo, other_hi):
    """Étend un intervalle (lo, hi) avec (other_lo, other_hi), None-safe."""
    if other_lo is not None:
        lo = other_lo if lo is None else min(lo, other_lo)
    if other_hi is not None:
        hi = other_hi if hi is None else max(hi, other_hi)
    return lo, hi


def _load_nappe(con, years, *, fetch=sources.fetch_nappe_year):
    total = 0
    dmin = dmax = None
    for p in config.PIEZOMETERS:
        for year in years:
            df = fetch(p["code_bss"], year)
            n = schema.upsert_dataframe(
                con, "nappe_mesure", df, keys=["code_bss", "date_mesure"]
            )
            total += n
            print(f"Hub'eau       {p['name']} {year} … {n} lignes")
            if not df.empty:
                dates = pd.to_datetime(df["date_mesure"])
                dmin, dmax = _span(dmin, dmax, _as_date(dates.min()), _as_date(dates.max()))
            # Espace les requêtes pour éviter le throttling Hub'eau en rebuild.
            time.sleep(config.NAPPE_REQUEST_DELAY)
    return total, dmin, dmax


def _ingest_meteo_csv(con, path) -> int:
    """Ingère un fichier Météo-France via le lecteur CSV de DuckDB (pas pandas).

    Le fichier est lu en streaming dans une table de staging (toutes colonnes
    en VARCHAR), cadré sur ``METEO_COLUMNS`` (+ ``date`` dérivée d'AAAAMMJJ),
    dédupliqué keep-last sur ``(NUM_POSTE, date)``, puis upserté. Renvoie le
    nombre de lignes stagées.
    """
    path = str(path)
    reader = "read_csv(?, delim=';', header=true, all_varchar=true)"
    present = [d[0] for d in con.execute(f"SELECT * FROM {reader} LIMIT 0", [path]).description]
    proj = ", ".join(
        f'"{c}"' if c in present else f'CAST(NULL AS VARCHAR) AS "{c}"'
        for c in config.METEO_COLUMNS
    )
    con.execute(
        f"""
        CREATE TEMP TABLE _meteo_stage AS
        WITH raw AS (
            SELECT {proj},
                   try_strptime("AAAAMMJJ", '%Y%m%d')::DATE AS "date",
                   row_number() OVER () AS _rn
            FROM {reader}
        )
        SELECT * EXCLUDE (_rn) FROM raw
        WHERE "date" IS NOT NULL
        QUALIFY row_number() OVER (PARTITION BY "NUM_POSTE", "date" ORDER BY _rn DESC) = 1
        """,
        [path],
    )
    n, dmin, dmax = con.execute(
        'SELECT COUNT(*), MIN("date"), MAX("date") FROM _meteo_stage'
    ).fetchone()
    collist = ", ".join(f'"{c}"' for c in config.METEO_COLUMNS + ["date"])
    update_cols = [c for c in config.METEO_COLUMNS if c != "NUM_POSTE"]
    setlist = ", ".join(f'"{c}" = excluded."{c}"' for c in update_cols)
    con.execute(
        f'INSERT INTO meteo_jour ({collist}) SELECT {collist} FROM _meteo_stage '
        f'ON CONFLICT ("NUM_POSTE", "date") DO UPDATE SET {setlist}'
    )
    con.execute("DROP TABLE _meteo_stage")
    return n, dmin, dmax


def _load_meteo(con, url_keys, *, download=sources.download_meteo_file):
    total = 0
    dmin = dmax = None
    for key in url_keys:
        url = config.METEO_URLS[key]
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = download(url, tmp)
            n, lo, hi = _ingest_meteo_csv(con, csv_path)
            total += n
            print(f"Météo-France  fichier {key} … {n} lignes")
            dmin, dmax = _span(dmin, dmax, lo, hi)
    return total, dmin, dmax


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


def format_summary(con, mode: str) -> str:
    """Bloc de résumé (chaîne pure, testable) lu depuis la base après chargement.

    Reprend, pour le chargement courant : les lignes ``ingest_log`` de ce run
    (source, scope, lignes, plage de dates), les comptes des tables de faits +
    dérivée, le nombre de stations météo distinctes et l'étendue de
    ``nappe_pluie_daily``.
    """
    lines = [f"Résumé ({mode}) :"]
    # Lignes ingest_log de CE run : la fenêtre récente (les deux _log d'un run
    # sont écrits en rafale ; le run précédent est distant de plusieurs secondes).
    log_rows = con.execute(
        """
        WITH latest AS (SELECT MAX(fetched_at) AS m FROM ingest_log WHERE mode = ?)
        SELECT source, scope, rows_upserted, date_min, date_max
        FROM ingest_log, latest
        WHERE mode = ? AND fetched_at >= latest.m - INTERVAL 10 SECOND
        ORDER BY source
        """,
        [mode, mode],
    ).fetchall()
    for source, scope, rows, dmin, dmax in log_rows:
        lines.append(f"  {source:<12} {scope:<20} {rows:>9} lignes  {dmin} → {dmax}")

    counts = {
        t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        for t in ("nappe_mesure", "meteo_jour", "nappe_pluie_daily")
    }
    n_stations = con.execute('SELECT COUNT(DISTINCT "NUM_POSTE") FROM meteo_jour').fetchone()[0]
    span = con.execute("SELECT MIN(date), MAX(date) FROM nappe_pluie_daily").fetchone()
    lines.append(
        f"  Tables : nappe_mesure={counts['nappe_mesure']}  "
        f"meteo_jour={counts['meteo_jour']} ({n_stations} stations)  "
        f"nappe_pluie_daily={counts['nappe_pluie_daily']}"
    )
    lines.append(f"  nappe_pluie_daily : {span[0]} → {span[1]}")
    return "\n".join(lines)


def _log(con, source, scope, mode, rows, date_min=None, date_max=None) -> None:
    con.execute(
        "INSERT INTO ingest_log (source, scope, mode, rows_upserted, "
        "date_min, date_max, fetched_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        [source, scope, mode, rows, date_min, date_max, dt.datetime.now()],
    )


def update(db_path=None) -> None:
    db_path = config.DB_PATH if db_path is None else db_path
    con = schema.connect(db_path)
    try:
        print(f"siba.db update → {db_path}")
        # Atomic: schema changes, loads, the derived rebuild and the log rows run
        # in one transaction so a mid-run failure (e.g. meteo after nappe) rolls
        # back and never leaves raw and derived data inconsistent.
        con.execute("BEGIN TRANSACTION")
        try:
            schema.create_all(con)  # IF NOT EXISTS / OR REPLACE: safe if tables exist
            schema.seed_stations(con)
            year = dt.date.today().year
            # Prev + current year: a January run still picks up late-December points
            # and prior-year requalifications; the upsert absorbs the overlap.
            years = [year - 1, year]
            n_nappe, nmin, nmax = _load_nappe(con, years)
            n_meteo, mmin, mmax = _load_meteo(con, ["latest"])
            _enrich_stations(con)
            print("Construction de nappe_pluie_daily …")
            build_nappe_pluie_daily(con)
            _log(con, "hubeau", f"nappe {years[0]}-{years[-1]}", "update", n_nappe, nmin, nmax)
            _log(con, "meteofrance", "meteo latest", "update", n_meteo, mmin, mmax)
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
        print(format_summary(con, "update"))
    finally:
        con.close()


def rebuild(db_path=None) -> None:
    db_path = config.DB_PATH if db_path is None else db_path
    con = schema.connect(db_path)
    try:
        print(f"siba.db rebuild → {db_path}")
        # Atomic: drop/create/load run in one transaction so a mid-run failure
        # (e.g. a Hub'eau timeout) rolls back and preserves the existing data
        # instead of leaving an emptied DB. DuckDB rolls back DDL and DML together.
        con.execute("BEGIN TRANSACTION")
        try:
            schema.drop_all(con)
            schema.create_all(con)
            schema.seed_stations(con)
            years = list(range(config.NAPPE_START_YEAR, dt.date.today().year + 1))
            n_nappe, nmin, nmax = _load_nappe(con, years)
            n_meteo, mmin, mmax = _load_meteo(con, list(config.METEO_URLS))
            _enrich_stations(con)
            print("Construction de nappe_pluie_daily …")
            build_nappe_pluie_daily(con)
            _log(con, "hubeau", f"nappe {years[0]}-{years[-1]}", "rebuild", n_nappe, nmin, nmax)
            _log(con, "meteofrance", "meteo all", "rebuild", n_meteo, mmin, mmax)
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
        # Rafraîchit le descriptif officiel des champs météo (best-effort : un
        # échec réseau ne casse pas le rebuild, la base est déjà committée).
        try:
            descriptor = config.DATA_DIR / "Q_descriptif_champs_RR-T-Vent.csv"
            sources.download_meteo_descriptor(descriptor)
            print(f"Descriptif Météo-France mis en cache : {descriptor}")
        except Exception as exc:
            print(f"Avertissement : descriptif Météo-France non mis à jour ({exc})")
        print(format_summary(con, "rebuild"))
    finally:
        con.close()
