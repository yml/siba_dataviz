"""Fetchers purs : API/fichier → DataFrame, sans cache disque durable."""

from __future__ import annotations

import time

import pandas as pd
import requests

from . import config

_NAPPE_COLS = [
    "code_bss", "date_mesure", "niveau_nappe_eau", "profondeur_nappe",
    "statut", "qualification", "mode_obtention", "code_producteur",
    "nom_producteur", "code_nature_mesure", "urn_bss", "timestamp_mesure",
]


def fetch_nappe_year(
    code_bss: str,
    year: int,
    *,
    url: str = config.HUBEAU_URL,
    session: requests.Session | None = None,
) -> pd.DataFrame:
    """Récupère les chroniques Hub'eau d'un piézomètre pour une année.

    Pagination par pages de 1000 (``sort=asc``). Retourne un DataFrame aux
    colonnes de ``nappe_mesure`` ; vide (mêmes colonnes) si aucune mesure.
    """
    sess = session or requests
    records: list[dict] = []
    page = 1
    while True:
        params = {
            "code_bss": code_bss,
            "size": 1000,
            "page": page,
            "sort": "asc",
            "date_debut_mesure": f"{year}-01-01",
            "date_fin_mesure": f"{year}-12-31",
        }
        resp = sess.get(url, params=params, timeout=30)
        if resp.status_code not in (200, 206):
            break
        data = resp.json()
        batch = data.get("data", [])
        if not batch:
            break
        records.extend(batch)
        if data.get("next") is None:
            break
        page += 1
        time.sleep(1)

    df = pd.DataFrame(records)
    df = df.reindex(columns=_NAPPE_COLS)
    if not df.empty:
        df["date_mesure"] = pd.to_datetime(df["date_mesure"], errors="coerce")
        df = df.dropna(subset=["date_mesure"])
        df = df.sort_values("date_mesure").reset_index(drop=True)
    return df
