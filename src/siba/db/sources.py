"""Fetchers purs : API/fichier → DataFrame, sans cache disque durable."""

from __future__ import annotations

import gzip
import shutil
import time
from pathlib import Path

import pandas as pd
import requests

from . import config

_NAPPE_COLS = [
    "code_bss", "date_mesure", "niveau_nappe_eau", "profondeur_nappe",
    "statut", "qualification", "mode_obtention", "code_producteur",
    "nom_producteur", "code_nature_mesure", "urn_bss", "timestamp_mesure",
]


def _get_with_retry(sess, url, params):
    """GET Hub'eau avec tentatives sur timeout / HTTP 429 / 5xx.

    Renvoie la réponse pour un statut non-réessayable (2xx ou 4xx) ; lève la
    dernière erreur si toutes les tentatives réessayables sont épuisées.
    """
    last_exc: Exception | None = None
    for attempt in range(config.NAPPE_MAX_RETRIES):
        try:
            resp = sess.get(url, params=params, timeout=30)
        except requests.exceptions.Timeout as exc:
            last_exc = exc
            time.sleep(config.NAPPE_BACKOFF * (attempt + 1))
            continue
        if resp.status_code == 429 or 500 <= resp.status_code < 600:
            last_exc = RuntimeError(
                f"Hub'eau HTTP {resp.status_code} (tentative {attempt + 1})"
            )
            time.sleep(config.NAPPE_BACKOFF * (attempt + 1))
            continue
        return resp
    raise last_exc


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
        resp = _get_with_retry(sess, url, params)
        # A non-2xx here is a real API failure (e.g. 404), not "no data": surface
        # it instead of returning an empty frame that looks like an empty year.
        resp.raise_for_status()
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


def download_meteo_file(url: str, dest_dir) -> Path:
    """Télécharge *url* dans *dest_dir* (temp), décompresse .gz, renvoie le .csv."""
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=120, allow_redirects=True) as resp:
        resp.raise_for_status()
        fname = resp.url.split("/")[-1] or "meteo_download"
        raw_path = dest_dir / fname
        with open(raw_path, "wb") as out:
            for chunk in resp.iter_content(chunk_size=1 << 16):
                if chunk:
                    out.write(chunk)

    if raw_path.suffix == ".gz":
        csv_path = raw_path.with_suffix("")  # strip .gz
        with gzip.open(raw_path, "rb") as f_in, open(csv_path, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
        raw_path.unlink(missing_ok=True)
        return csv_path
    return raw_path
