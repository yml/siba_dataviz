"""
siba — analyse croisée nappes phréatiques + précipitations, Bassin d'Arcachon.

Sous-modules :

- :mod:`siba.nappe` — chroniques piézométriques Hub'eau (cache local)
- :mod:`siba.meteo` — précipitations Météo-France au Cap-Ferret
- :mod:`siba.merge` — fusion des deux sur un index journalier
- :mod:`siba.paths` — emplacements ancrés sur la racine du dépôt

Les chemins ne dépendent pas du répertoire courant : un notebook rangé dans
``notebooks/`` ou ``marimo/`` trouve ``_data/`` sans bricolage de ``sys.path``.
"""

from .merge import merge_nappe_pluie
from .meteo import (
    METEO_CACHE_MAX_AGE_HOURS,
    METEO_DOWNLOAD_URLS,
    load_meteo_capferret,
)
from .nappe import (
    CACHE_MAX_AGE_HOURS,
    CURRENT_YEAR,
    DEFAULT_START_YEAR,
    HUBEAU_URL,
    PIEZOMETERS,
    fetch_nappe,
    fetch_nappe_multi_years,
)
from .paths import DATA_DIR, REPO_ROOT, RESULTS_DIR

__all__ = [
    "CACHE_MAX_AGE_HOURS",
    "CURRENT_YEAR",
    "DATA_DIR",
    "DEFAULT_START_YEAR",
    "HUBEAU_URL",
    "METEO_CACHE_MAX_AGE_HOURS",
    "METEO_DOWNLOAD_URLS",
    "PIEZOMETERS",
    "REPO_ROOT",
    "RESULTS_DIR",
    "fetch_nappe",
    "fetch_nappe_multi_years",
    "load_meteo_capferret",
    "merge_nappe_pluie",
]
