"""siba.db — chargement DuckDB des nappes (Hub'eau) et de la pluie (Météo-France).

Paquet isolé : n'importe aucun des modules siba.nappe / meteo / merge.
"""

from .loader import rebuild, update

__all__ = ["rebuild", "update"]
