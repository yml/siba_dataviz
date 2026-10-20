# Analyse de donnée autour de EAU du SIBA

Analyse croisée des nappes phréatiques et des précipitations sur le Bassin
d'Arcachon. Les données viennent de Hub'eau (piézomètres) et de Météo-France
(poste de Cap-Ferret), chargées dans une base DuckDB locale (`_data/siba.duckdb`).

## Sources des données

Tout est récupéré directement depuis les portails open data (voir
`src/siba/data/config.py`) :

**Nappe — Hub'eau (piézométrie)**

- API chroniques : <https://hubeau.eaufrance.fr/api/v1/niveaux_nappes/chroniques>
- Documentation : <https://hubeau.eaufrance.fr/page/api-piezometrie>
- Stations (fiches ADES) : Blagon (Lanton) `08262X0023/F`
  (<https://ades.eaufrance.fr/Fiche/PointEau?code=08262X0023/F>), Piraillan
  (Lège-Cap-Ferret) `08257X0086/F`
  (<https://ades.eaufrance.fr/Fiche/PointEau?code=08257X0086/F>), Canauley
  (Biganos) `08266X0003/F`
  (<https://ades.eaufrance.fr/Fiche/PointEau?code=08266X0003/F>), Villemarie
  (La Teste-de-Buch) `08494X0126/PZ1`
  (<https://ades.eaufrance.fr/Fiche/PointEau?code=08494X0126/PZ1>)

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
src/siba/       module partagé (chemins, chargement DuckDB `siba.data`)
marimo/         notebooks marimo (.py, réactifs)
_data/          cache des données brutes — non versionné
_local/         documents sources (rapports, arrêtés, PDF) — non versionné
results/        exports (WASM, HTML)
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
# marimo (éditeur réactif)
uv run marimo edit marimo/explore_nappe_pluie.py
```

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
| `marimo/explore_nappe_pluie.py` | Exploration réactive (curseurs, agrégats DuckDB) |
| `marimo/vue_ensemble_multi_annees.py` | Un sous-graphe par année, nappe + pluie + périodes HC |
| `marimo/episode_hors_controle.py` | Épisode HC en détail (exportable en WASM) |
| `marimo/bacterio_carte_pollution.py` | Carte des points chauds *E. coli*, par année |
| `marimo/comparaison_stations_pluie.py` | Les 11 postes de pluie comparés, rupture de Cap-Ferret (2023), critère SIBA des 70 mm, épisodes HC par poste |
| `marimo/step_biganos_nappe.py` | Débit d'eau brute de la STEP de Biganos face à la nappe (nécessite `_local/`) |
| `marimo/postes_pompage_nappe.py` | Postes de pompage du réseau collecteur face à la nappe (nécessite `_local/`) |
