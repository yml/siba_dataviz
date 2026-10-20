"""
Emplacements des fichiers du projet.

Les chemins sont ancrés sur la racine du dépôt (déduite de ``__file__``) et
non sur le répertoire courant : un notebook rangé dans ``marimo/`` trouve
``_data/`` sans ``../`` ni ``os.chdir``.
"""

import os
from pathlib import Path

# src/siba/paths.py → src/siba → src → racine du dépôt
REPO_ROOT = Path(__file__).resolve().parents[2]

#: Cache local des données brutes (Hub'eau, Météo-France).
DATA_DIR = Path(os.environ.get("SIBA_DATA_DIR", REPO_ROOT / "_data"))

#: Sorties : figures, exports HTML/PDF.
RESULTS_DIR = Path(os.environ.get("SIBA_RESULTS_DIR", REPO_ROOT / "results"))
