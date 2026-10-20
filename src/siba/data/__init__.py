"""siba.data — chargement DuckDB des nappes (Hub'eau) et de la pluie (Météo-France).

Paquet isolé : n'importe aucun des modules siba.nappe / meteo / merge.
"""

from .loader import list_versions, prune, rebuild, restore, snapshot, update

__all__ = ["list_versions", "prune", "rebuild", "restore", "snapshot", "update"]
