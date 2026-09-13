"""
Précipitations Météo-France (Gironde, poste Cap-Ferret), avec cache local.
"""

import glob
import gzip
import os
import shutil
import urllib.request

import pandas as pd

from .paths import DATA_DIR, cache_age_hours

# URLs Météo-France (Gironde, RR-T-Vent)
METEO_DOWNLOAD_URLS = [
    "https://www.data.gouv.fr/api/1/datasets/r/b0e78f3d-9085-4d6d-a47d-6d942f5e9a54",
    "https://www.data.gouv.fr/api/1/datasets/r/5f196a76-ba4f-4aa7-af28-eff6c8797b50",
]

# Seul le fichier « latest » est mis à jour par le producteur ; les archives
# (1842-1949, previous-1950-2024) sont figées et gardent un cache permanent.
METEO_CACHE_MAX_AGE_HOURS = 24.0


def _download_file(
    url: str,
    dest_folder: str | os.PathLike,
    max_age_hours: float | None = None,
) -> None:
    """
    Télécharge *url* dans *dest_folder* si le fichier local est absent ou périmé.

    Le nom du fichier n'est connu qu'après résolution des redirections
    data.gouv.fr : on ouvre la connexion, puis on ne lit le corps que si
    c'est nécessaire.

    - Archives (``1842-1949``, ``previous-…``) : cache permanent.
    - Fichier ``latest-…`` : re-téléchargé au-delà de ``max_age_hours``.
    """
    os.makedirs(dest_folder, exist_ok=True)
    if max_age_hours is None:
        max_age_hours = METEO_CACHE_MAX_AGE_HOURS

    tmp_path = None
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as response:
            file_path = os.path.join(dest_folder, response.url.split("/")[-1])

            if os.path.exists(file_path):
                if "latest" not in os.path.basename(file_path):
                    print(f"  Archive figée : {file_path}")
                    return
                age = cache_age_hours(file_path)
                if age < max_age_hours:
                    print(f"  À jour ({age:.1f} h) : {file_path}")
                    return
                print(f"  Périmé ({age:.1f} h) → re-téléchargement : {file_path}")

            # Écriture dans un fichier temporaire : une coupure réseau ne doit
            # pas laisser un fichier tronqué à la place d'un cache valide.
            tmp_path = file_path + ".part"
            with open(tmp_path, "wb") as out_file:
                shutil.copyfileobj(response, out_file)
            os.replace(tmp_path, file_path)
            print(f"  Downloaded {file_path}")
    except Exception as e:
        print(f"  Failed to download {url}: {e}")
        if tmp_path is not None and os.path.exists(tmp_path):
            os.remove(tmp_path)


def _uncompress_gz_files(folder: str) -> None:
    for root, _, files in os.walk(folder):
        for file in files:
            if file.endswith(".csv.gz"):
                gz_path = os.path.join(root, file)
                csv_path = os.path.join(root, file[:-3])
                # Re-décompresser si le CSV manque ou date d'avant le .gz
                # (sinon un .gz rafraîchi resterait invisible).
                if os.path.exists(csv_path) and os.path.getmtime(csv_path) >= os.path.getmtime(gz_path):
                    continue
                with gzip.open(gz_path, "rb") as f_in:
                    with open(csv_path, "wb") as f_out:
                        shutil.copyfileobj(f_in, f_out)
                print(f"  Uncompressed {gz_path}")


def load_meteo_capferret(
    data_folder: str | os.PathLike | None = None,
    date_min: str = "2015-01-01",
    max_age_hours: float | None = None,
) -> pd.DataFrame:
    """
    Télécharge (si nécessaire) et charge les données Météo-France Cap-Ferret.

    ``max_age_hours`` contrôle la fraîcheur du fichier « latest » (défaut
    ``METEO_CACHE_MAX_AGE_HOURS``) ; ``0`` force le re-téléchargement.

    Retourne un DataFrame indexé par DATE avec les colonnes RR et SLIDING_RR7.
    """
    data_folder = DATA_DIR if data_folder is None else data_folder
    for url in METEO_DOWNLOAD_URLS:
        _download_file(url, data_folder, max_age_hours=max_age_hours)
    _uncompress_gz_files(data_folder)

    q_33_csv = sorted(glob.glob(os.path.join(data_folder, "Q_33_*.csv")))
    print(f"Fichiers CSV météo : {q_33_csv}")

    df_meteo = pd.concat(
        (pd.read_csv(f, delimiter=";") for f in q_33_csv),
        ignore_index=True,
    )
    df_meteo["DATE"] = pd.to_datetime(df_meteo["AAAAMMJJ"], format="%Y%m%d")

    df_cf = df_meteo[df_meteo["NOM_USUEL"] == "CAP-FERRET"].sort_values("DATE").copy()
    df_cf["SLIDING_RR7"] = df_cf["RR"].rolling(window=7, min_periods=1).sum()
    df_cf = df_cf[df_cf["DATE"] >= date_min].copy()
    df_cf = df_cf.set_index("DATE")
    df_cf.index.name = "DATE"

    print(
        f"Cap-Ferret : {df_cf.index.min().date()} → {df_cf.index.max().date()}"
        f"  ({len(df_cf)} jours)"
    )
    return df_cf
