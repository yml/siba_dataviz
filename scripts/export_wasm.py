#!/usr/bin/env python3
"""Régénère le notebook marimo « épisode hors de contrôle » en version autonome
(données embarquées, sans DuckDB) et l'exporte en HTML WASM interactif.

Source de vérité : ``marimo/episode_hors_controle.py`` (lit ``siba.duckdb``).
Ce script en dérive une copie ``*_export.py`` où l'accès DuckDB est remplacé par
des données CSV embarquées (gzip + base64) lues depuis la base, puis lance
``marimo export html-wasm``.

Usage :
    uv run python scripts/export_wasm.py
    # ou : make export-wasm

Le HTML produit (``results/wasm/episode_hors_controle.html`` + ``results/wasm/
assets/``) doit être servi en HTTP (``python -m http.server --directory
results/wasm``) : le
navigateur charge Pyodide au premier affichage, puis le sélecteur d'épisode est
interactif sans serveur Python.
"""

from __future__ import annotations

import base64
import gzip
import subprocess
import sys
from pathlib import Path

import duckdb

from siba.data.config import DB_PATH

REPO = Path(__file__).resolve().parents[1]
SOURCE = REPO / "marimo" / "episode_hors_controle.py"
EXPORT = REPO / "marimo" / "episode_hors_controle_export.py"
OUT = REPO / "results" / "wasm" / "episode_hors_controle.html"

# --- anchors dans le notebook source (le script échoue si l'un manque) --------

OLD_IMPORTS = '''    import duckdb
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from scipy import stats

    from siba.data.config import DB_PATH

    plt.style.use("seaborn-v0_8-whitegrid")
    return DB_PATH, duckdb, mdates, mo, np, pd, plt, stats'''

NEW_IMPORTS = '''    import base64
    import gzip
    import io

    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from scipy import stats

    plt.style.use("seaborn-v0_8-whitegrid")
    return base64, gzip, io, mdates, mo, np, pd, plt, stats'''

OLD_LOAD = '''@app.cell
def _(DB_PATH, duckdb, pd):
    con = duckdb.connect(str(DB_PATH), read_only=True)
    df = con.execute(
        'SELECT "date", "Blagon", "Piraillan", rr AS "RR", rr_7d AS "RR7", in_hc '
        "FROM v_nappe_pluie_events ORDER BY \\"date\\""
    ).df()
    episodes = con.execute(
        "SELECT start_date, end_date, label FROM hc_period ORDER BY start_date"
    ).df()
    con.close()

    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")
    episodes["start_date"] = pd.to_datetime(episodes["start_date"])
    episodes["end_date"] = pd.to_datetime(episodes["end_date"])

    NAPPE_COLS = ["Blagon", "Piraillan"]
    return NAPPE_COLS, df, episodes'''

NEW_LOAD_TMPL = '''@app.cell
def _(base64, gzip, io, pd):
    # Données embarquées (CSV gzip+base64) — notebook autonome, sans DuckDB.
    _DAILY_B64 = "{daily}"
    _EPISODES_B64 = "{episodes}"

    def _load(b64):
        raw = gzip.decompress(base64.b64decode(b64))
        return pd.read_csv(io.BytesIO(raw))

    df = _load(_DAILY_B64)
    episodes = _load(_EPISODES_B64)

    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")
    df["in_hc"] = df["in_hc"].astype(str).str.lower().isin(["true", "1"])
    episodes["start_date"] = pd.to_datetime(episodes["start_date"])
    episodes["end_date"] = pd.to_datetime(episodes["end_date"])

    NAPPE_COLS = ["Blagon", "Piraillan"]
    return NAPPE_COLS, df, episodes'''

OLD_TITLE = '''    Version réactive inspirée de `notebooks/analyse_nappe_pluie_2026.ipynb`, lisant
    `siba.duckdb` (`v_nappe_pluie_events` + `hc_period`).'''

NEW_TITLE = '''    Version réactive inspirée de `notebooks/analyse_nappe_pluie_2026.ipynb`. Les
    données (nappe, pluie, épisodes HC) sont **embarquées** dans le notebook — page
    autonome, aucune base ni serveur requis.'''

OLD_APP = 'app = marimo.App(width="full", auto_download=["html"], sql_output="native")'
NEW_APP = 'app = marimo.App(width="full")'


def _b64(df) -> str:
    return base64.b64encode(gzip.compress(df.to_csv(index=False).encode())).decode()


def fetch_embedded() -> tuple[str, str]:
    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        daily = con.execute(
            'SELECT "date", "Blagon", "Piraillan", rr AS "RR", rr_7d AS "RR7", in_hc '
            'FROM v_nappe_pluie_events ORDER BY "date"'
        ).df()
        episodes = con.execute(
            "SELECT start_date, end_date, label FROM hc_period ORDER BY start_date"
        ).df()
    finally:
        con.close()
    return _b64(daily), _b64(episodes)


def build_export_notebook() -> None:
    src = SOURCE.read_text()

    def swap(text, old, new, what):
        n = text.count(old)
        if n != 1:
            raise SystemExit(
                f"Ancre « {what} » introuvable ou non unique ({n}) dans {SOURCE}. "
                "Le notebook source a changé : mettre à jour scripts/export_wasm.py."
            )
        return text.replace(old, new)

    daily_b64, episodes_b64 = fetch_embedded()
    new_load = NEW_LOAD_TMPL.format(daily=daily_b64, episodes=episodes_b64)

    src = swap(src, OLD_IMPORTS, NEW_IMPORTS, "imports")
    src = swap(src, OLD_LOAD, new_load, "chargement données")
    src = swap(src, OLD_TITLE, NEW_TITLE, "titre")
    if OLD_APP in src:  # présent seulement si l'éditeur marimo l'a ajouté
        src = src.replace(OLD_APP, NEW_APP)

    if "duckdb" in src or "siba" in src:
        raise SystemExit("Référence duckdb/siba résiduelle dans le notebook exporté.")

    EXPORT.write_text(src)
    print(f"écrit {EXPORT.relative_to(REPO)} ({len(daily_b64)} o de données embarquées)")


def run_wasm_export() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "marimo", "export", "html-wasm",
        str(EXPORT), "-o", str(OUT), "--mode", "run",
    ]
    print("→", " ".join(cmd))
    subprocess.run(cmd, check=True)
    print(f"\nHTML WASM : {OUT.relative_to(REPO)} (+ results/wasm/assets/)")
    print("Tester :   python -m http.server --directory results/wasm")


def main() -> int:
    if not DB_PATH.exists():
        raise SystemExit(
            f"Base introuvable : {DB_PATH}. Lancer d'abord "
            "`uv run python -m siba.data rebuild` (ou `update`)."
        )
    build_export_notebook()
    run_wasm_export()
    return 0


if __name__ == "__main__":
    sys.exit(main())
