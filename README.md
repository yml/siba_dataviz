# Analyse de donnée autour de EAU du SIBA

Analyse croisée des nappes phréatiques et des précipitations sur le Bassin
d'Arcachon. Les données viennent de Hub'eau (piézomètres) et de Météo-France
(poste de Cap-Ferret), avec un cache local dans `_data/`.

## Organisation

```
src/siba/       module partagé (récupération, cache, fusion)
notebooks/      notebooks Jupyter (.ipynb)
marimo/         notebooks marimo (.py, réactifs)
_data/          cache des données brutes — non versionné
_local/         documents sources (rapports, arrêtés, PDF) — non versionné
results/        figures produites
  exports/      exports HTML / PDF des notebooks
```

## Installation

Python 3.14 (voir `.python-version`).

```sh
uv sync
```

Le module `siba` est installé en mode éditable : `from siba import ...`
fonctionne depuis n'importe quel répertoire, et les chemins vers `_data/` et
`results/` sont ancrés sur la racine du dépôt (voir `src/siba/paths.py`).

Deux variables d'environnement permettent de déplacer ces dossiers, par exemple
pour partager un cache entre plusieurs copies du dépôt :

```sh
export SIBA_DATA_DIR=/chemin/vers/cache
export SIBA_RESULTS_DIR=/chemin/vers/sorties
```

## Utilisation

```sh
# Jupyter
uv run jupyter lab

# marimo (éditeur réactif)
uv run marimo edit marimo/explore_nappe_pluie.py
```

Depuis Python ou un notebook :

```python
from siba import PIEZOMETERS, fetch_nappe_multi_years, load_meteo_capferret, merge_nappe_pluie

# years vaut par défaut range(DEFAULT_START_YEAR, CURRENT_YEAR + 1), soit 2015 → année courante
nappe = {p["name"]: fetch_nappe_multi_years(p["code_bss"], p["name"]) for p in PIEZOMETERS}
meteo = load_meteo_capferret(date_min="2015-01-01")
df = merge_nappe_pluie(nappe, meteo, date_min="2015-01-01")
```

### Cache

Les téléchargements sont mis en cache dans `_data/` :

- chroniques Hub'eau — les années passées sont figées, l'année en cours est
  rechargée au-delà de 12 h (`CACHE_MAX_AGE_HOURS`) ;
- fichiers Météo-France — les archives sont figées, le fichier `latest` est
  rechargé au-delà de 24 h (`METEO_CACHE_MAX_AGE_HOURS`).

Passer `max_age_hours=0` force le rechargement, `float("inf")` fige le cache
(utile hors ligne). Si la source est injoignable, le cache existant est relu
plutôt que de renvoyer un résultat vide.

## Notebooks

| Notebook | Contenu |
|---|---|
| `notebooks/meteofrance_33_precipation.ipynb` | Précipitations Cap-Ferret, séries longues et seuils RR7 |
| `notebooks/hauteur_nappes_phreatiques.ipynb` | Niveaux piézométriques bruts (Piraillan, Blagon) |
| `notebooks/analyse_nappe_pluie_historique.ipynb` | Nappe + pluie 2010 → aujourd'hui, périodes « hors de contrôle » |
| `notebooks/analyse_nappe_pluie_2026.ipynb` | Zoom sur l'épisode de 2026 |
| `marimo/explore_nappe_pluie.py` | Exploration réactive (curseurs, agrégats DuckDB) |
