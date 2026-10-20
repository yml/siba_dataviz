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
- Fichiers utilisés : `historical` (avant 1950, `Q_33_avant-1949_RR-T-Vent.csv.gz`)
  <https://www.data.gouv.fr/api/1/datasets/r/f74e1970-5462-4981-87e5-fb535b2c1af1>,
  `previous` (1950-2024)
  <https://www.data.gouv.fr/api/1/datasets/r/b0e78f3d-9085-4d6d-a47d-6d942f5e9a54>
  et `latest` (année en cours)
  <https://www.data.gouv.fr/api/1/datasets/r/5f196a76-ba4f-4aa7-af28-eff6c8797b50>
- Descriptif des champs : <https://meteofrance.s3.sbg.io.cloud.ovh.net/data/synchro_ftp/BASE/QUOT/Q_descriptif_champs_RR-T-Vent.csv>
- Référence : Cap-Ferret `33236002` ; postes chargés : les 11 de
  `config.METEO_STATIONS` (voir `DATA_DICTIONARY.md`, table `meteo_jour`)

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

Chargement des données Hub'eau et Météo-France dans une base DuckDB locale
`_data/siba.duckdb`. Les fichiers téléchargés restent sous `_data/sources/`
(JSON Hub'eau par piézomètre et par année, `.csv.gz` Météo-France tels quels).

```sh
make rebuild    # reconstruit depuis _data/sources/ (télécharge ce qui manque)
make refresh    # idem en retéléchargeant toutes les sources
make update     # année précédente + courante (Hub'eau), fichier météo « latest »
make versions   # liste les versions, la courante est marquée *
make snapshot   # copie la version courante avant une modification manuelle
make restore V=<nom>
make prune      # supprime les anciennes versions (garde les 5 plus récentes)
```

`rebuild` charge la nappe de 2010 à l'année en cours et les trois fichiers
Météo-France (`historical` avant 1950, `previous` 1950-2024, `latest`).
`update` retélécharge l'année précédente et l'année en cours (Hub'eau) et le
fichier `latest` (Météo-France). Chaque commande a son équivalent
`uv run python -m siba.data <commande>`.

Tables : `nappe_mesure`, `meteo_jour` (11 postes curés, colonnes brutes),
`station`, `ingest_log`. Vues/dérivés : `v_meteo_interest` (stations
d'intérêt), `nappe_pluie_daily` (table matérialisée : nappes interpolées +
cumuls de pluie 7/14/28/56 j sur Cap-Ferret).

### Versions de la base

`_data/siba.duckdb` est un lien symbolique vers une version :
`_data/versions/<aaaammjj_hhmmss>__(load|snapshot)__siba.duckdb`. `--db-path`
et `SIBA_DATA_DIR` déplacent l'ensemble (le dossier `versions/` est toujours à
côté du lien).

**Lister** : `make versions` (ou `uv run python -m siba.data versions`).

```
  20261018_155239__load__siba.duckdb         load         95,2 Mo
  20261020_093000__snapshot__siba.duckdb     snapshot     95,2 Mo
* 20261020_101500__load__siba.duckdb         load         14,4 Mo
```

`*` = version courante. Une base `siba.duckdb` classique est migrée en
première version au premier lancement, sans perte : elle garde son contenu
d'avant (tous les postes de Gironde, sans l'archive avant 1950) et sa
taille. Lancer ensuite une fois `make rebuild` pour obtenir les 11 postes curés
depuis 1881.

**Revenir en arrière** :

1. `make versions` pour trouver le nom ;
2. `make restore V=20261018_155239__load__siba.duckdb` ;
3. redémarrer l'UI DuckDB ou relancer les notebooks (un client ouvert garde la
   version qu'il a ouverte) ;
4. pour revenir à la dernière version : `make versions`, puis
   `make restore V=<dernier nom>`.

Un `restore` ne copie rien et ne supprime rien : il déplace le lien.

**Inspecter une version sans basculer** (DuckDB, depuis la racine du dépôt) :

```sql
ATTACH '_data/versions/<nom>' AS ancienne (READ_ONLY);
SELECT count(*) FROM ancienne.nappe_mesure;
```

**Ce qui crée une version** : `update`, `rebuild`, `refresh` (`__load__`) et
`snapshot` (`__snapshot__`). `update` et `snapshot` partent d'une copie de la
version courante, `rebuild` et `refresh` d'une base vide. Chaque nouvelle
version est construite dans un `.tmp`, puis le lien bascule d'un coup ; un
chargement qui échoue ne touche ni au lien ni aux versions existantes.

**Faire de la place** : aucune version n'est supprimée automatiquement.
`make prune` garde les 5 versions les plus récentes (`VERSIONS_KEEP`) et
supprime les autres ; `make prune N=3` en garde 3 (ou
`uv run python -m siba.data prune --keep 3`). La version courante et une
version qui a un `.wal` ne sont jamais supprimées. La commande affiche les
fichiers supprimés.

- Un chargement refuse de démarrer si la version courante a un `.wal` : un
  client en écriture est ouvert (UI DuckDB), le fermer d'abord.
- Un `.tmp` orphelin après un crash se supprime à la main.
- Après un chargement, redémarrer l'UI DuckDB (`DETACH` / `ATTACH`) ou relancer
  les notebooks pour voir la nouvelle version.

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
