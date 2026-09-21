# Analyse de donnée autour de EAU du SIBA

Analyse croisée des nappes phréatiques et des précipitations sur le Bassin
d'Arcachon. Les données viennent de Hub'eau (piézomètres) et de Météo-France
(poste de Cap-Ferret), avec un cache local dans `_data/`.

## Sources des données

Tout est récupéré directement depuis les portails open data (voir
`src/siba/data/config.py`) :

**Nappe — Hub'eau (piézométrie)**

- API chroniques : <https://hubeau.eaufrance.fr/api/v1/niveaux_nappes/chroniques>
- Documentation : <https://hubeau.eaufrance.fr/page/api-piezometrie>
- Stations (fiches ADES) : Blagon (Lanton) `08262X0023/F`
  (<https://ades.eaufrance.fr/Fiche/PointEau?code=08262X0023/F>), Piraillan
  (Lège-Cap-Ferret) `08257X0086/F`
  (<https://ades.eaufrance.fr/Fiche/PointEau?code=08257X0086/F>)

**Pluie — Météo-France (données climatologiques quotidiennes, Gironde)**

- Portail : <https://meteo.data.gouv.fr/>
- Fichiers utilisés : `previous` (1950-2024)
  <https://www.data.gouv.fr/api/1/datasets/r/b0e78f3d-9085-4d6d-a47d-6d942f5e9a54>
  et `latest` (année en cours)
  <https://www.data.gouv.fr/api/1/datasets/r/5f196a76-ba4f-4aa7-af28-eff6c8797b50>
- Descriptif des champs : <https://meteofrance.s3.sbg.io.cloud.ovh.net/data/synchro_ftp/BASE/QUOT/Q_descriptif_champs_RR-T-Vent.csv>
- Poste utilisé : Cap-Ferret `33236002`

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

## Base DuckDB (`siba.data`)

Chargement des données directement depuis Hub'eau et Météo-France vers une base
DuckDB locale `_data/siba.duckdb`, sans passer par le cache CSV.

```sh
# reconstruire la base de zéro
uv run python -m siba.data rebuild

# mise à jour incrémentale (année précédente + courante, fichier météo « latest »)
uv run python -m siba.data update
```

`rebuild` charge la nappe de 2010 à l'année en cours et les fichiers
Météo-France `previous` (1950-2024) + `latest`. L'archive Météo-France
antérieure à 1950 n'est volontairement pas chargée (la table journalière
démarre en 2015). `update` ne recharge que l'année précédente et l'année en
cours (Hub'eau) et le fichier `latest` (Météo-France).

Tables : `nappe_mesure`, `meteo_jour` (toutes stations Gironde, colonnes
brutes), `station`, `ingest_log`. Vues/dérivés : `v_meteo_interest` (stations
d'intérêt), `nappe_pluie_daily` (table matérialisée : nappes interpolées +
cumuls de pluie 7/14/28/56 j sur Cap-Ferret).

Description détaillée des tables et colonnes : voir [`DATA_DICTIONARY.md`](DATA_DICTIONARY.md).

## Notebooks

| Notebook | Contenu |
|---|---|
| `notebooks/meteofrance_33_precipation.ipynb` | Précipitations Cap-Ferret, séries longues et seuils RR7 |
| `notebooks/hauteur_nappes_phreatiques.ipynb` | Niveaux piézométriques bruts (Piraillan, Blagon) |
| `notebooks/analyse_nappe_pluie_historique.ipynb` | Nappe + pluie 2010 → aujourd'hui, périodes « hors de contrôle » |
| `notebooks/analyse_nappe_pluie_2026.ipynb` | Zoom sur l'épisode de 2026 |
| `marimo/explore_nappe_pluie.py` | Exploration réactive (curseurs, agrégats DuckDB) |
| `marimo/vue_ensemble_multi_annees.py` | Un sous-graphe par année, nappe + pluie + périodes HC |
| `marimo/episode_hors_controle.py` | Épisode HC en détail (exportable en WASM) |
| `marimo/bacterio_carte_pollution.py` | Carte des points chauds *E. coli*, par année |
