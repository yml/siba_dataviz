"""
Données piézométriques Hub'eau, avec cache local sur disque.
"""

import os
import time
from datetime import datetime

import pandas as pd
import requests

from .paths import DATA_DIR, cache_age_hours

HUBEAU_URL = "https://hubeau.eaufrance.fr/api/v1/niveaux_nappes/chroniques.json"

PIEZOMETERS = [
    {"code_bss": "08262X0023/F", "name": "Blagon (Lanton)"},
    {"code_bss": "08257X0086/F", "name": "Piraillan (Lège-Cap-Ferret)"},
]

CURRENT_YEAR = datetime.now().year

#: Première année couverte par défaut (début des chroniques exploitables).
DEFAULT_START_YEAR = 2015

# Durée de validité du cache pour l'année en cours (heures).
# Hub'eau ne publie qu'une mesure par jour et requalifie les points récents
# quelques jours plus tard : re-télécharger plus souvent n'apporte rien.
CACHE_MAX_AGE_HOURS = 12.0


def _safe_code_bss(code_bss: str) -> str:
    """Remplace / par _ pour un nom de fichier valide."""
    return code_bss.replace("/", "_")


def _read_cache(path: str) -> pd.DataFrame:
    """Relit un cache CSV en reconstruisant les dates."""
    return pd.read_csv(path, parse_dates=["date_mesure"])


def fetch_nappe(
    code_bss: str,
    name: str,
    year: int,
    data_folder: str | os.PathLike | None = None,
    force: bool = False,
    max_age_hours: float | None = None,
) -> pd.DataFrame:
    """
    Récupère les données piézométriques Hub'eau pour *une année*.

    Cache local : ``DATA_DIR/nappe_{code_bss_safe}_{year}.csv``
    - Années passées : cache permanent (sauf ``force=True``).
    - Année en cours  : cache relu s'il a moins de ``max_age_hours`` heures
      (défaut ``CACHE_MAX_AGE_HOURS``), re-téléchargé au-delà.
      ``max_age_hours=0`` force le re-téléchargement, ``float("inf")`` fige le cache.
    - Si Hub'eau ne répond pas (hors ligne, erreur HTTP), on retombe sur le
      cache existant même périmé plutôt que de renvoyer un DataFrame vide.
    """
    data_folder = DATA_DIR if data_folder is None else data_folder
    os.makedirs(data_folder, exist_ok=True)
    safe = _safe_code_bss(code_bss)
    cache_path = os.path.join(data_folder, f"nappe_{safe}_{year}.csv")

    is_current_year = year >= CURRENT_YEAR
    if max_age_hours is None:
        max_age_hours = CACHE_MAX_AGE_HOURS

    has_cache = os.path.exists(cache_path)
    if has_cache and not force:
        if not is_current_year:
            return _read_cache(cache_path)
        age = cache_age_hours(cache_path)
        if age < max_age_hours:
            print(f"  Cache → {name} ({code_bss}) année {year} (âge {age:.1f} h)")
            return _read_cache(cache_path)

    date_min = f"{year}-01-01"
    date_max = f"{year}-12-31"

    print(f"  Hub'eau → {name} ({code_bss}) année {year} …")
    all_data: list[dict] = []
    page = 1
    while True:
        params = {
            "code_bss": code_bss,
            "size": 1000,
            "page": page,
            "sort": "asc",
            "date_debut_mesure": date_min,
            "date_fin_mesure": date_max,
        }
        resp = requests.get(HUBEAU_URL, params=params, timeout=30)
        if resp.status_code not in (200, 206):
            print(f"    Erreur HTTP {resp.status_code}")
            break
        data = resp.json()
        records = data.get("data", [])
        if not records:
            break
        all_data.extend(records)
        if data.get("next") is None:
            break
        page += 1
        time.sleep(1)

    df = pd.DataFrame(all_data)
    if len(df) > 0:
        df["date_mesure"] = pd.to_datetime(df["date_mesure"], errors="coerce")
        df = df.sort_values("date_mesure").reset_index(drop=True)

    # Rien reçu mais un cache existe : Hub'eau est probablement injoignable.
    # Mieux vaut des données périmées qu'un DataFrame vide.
    if len(df) == 0 and has_cache:
        age = cache_age_hours(cache_path)
        print(f"    → 0 mesure, repli sur le cache (âge {age:.1f} h)")
        return _read_cache(cache_path)

    # Sauvegarder le cache (même vide, pour éviter des re-fetch inutiles —
    # sauf année en cours qu'on veut toujours rafraîchir)
    if len(df) > 0 or not is_current_year:
        df.to_csv(cache_path, index=False)

    print(f"    → {len(df)} mesures")
    return df


def fetch_nappe_multi_years(
    code_bss: str,
    name: str,
    years: range | list[int] | None = None,
    data_folder: str | os.PathLike | None = None,
    force: bool = False,
    max_age_hours: float | None = None,
) -> pd.DataFrame:
    """
    Récupère et concatène les données piézométriques sur plusieurs années.

    ``years`` vaut par défaut ``range(DEFAULT_START_YEAR, CURRENT_YEAR + 1)``,
    calculé à l'appel : la borne haute suit l'année courante au lieu d'être
    figée dans la signature.
    """
    if years is None:
        years = range(DEFAULT_START_YEAR, CURRENT_YEAR + 1)

    print(f"Récupération multi-années : {name} ({code_bss})")
    frames: list[pd.DataFrame] = []
    for y in years:
        df_y = fetch_nappe(
            code_bss,
            name,
            y,
            data_folder=data_folder,
            force=force,
            max_age_hours=max_age_hours,
        )
        if len(df_y) > 0:
            frames.append(df_y)
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    df = df.drop_duplicates(subset=["date_mesure"]).sort_values("date_mesure").reset_index(drop=True)
    print(f"  Total : {len(df)} mesures ({df['date_mesure'].min().date()} → {df['date_mesure'].max().date()})")
    return df
