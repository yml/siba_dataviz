"""
siba — analyse croisée nappes phréatiques + précipitations, Bassin d'Arcachon.

Sous-modules :

- :mod:`siba.data` — chargement DuckDB (Hub'eau, Météo-France, Enki)
- :mod:`siba.paths` — emplacements ancrés sur la racine du dépôt

Les chemins ne dépendent pas du répertoire courant : un notebook rangé dans
``marimo/`` trouve ``_data/`` sans bricolage de ``sys.path``.
"""

from .paths import DATA_DIR, REPO_ROOT, RESULTS_DIR

__all__ = ["DATA_DIR", "REPO_ROOT", "RESULTS_DIR"]
