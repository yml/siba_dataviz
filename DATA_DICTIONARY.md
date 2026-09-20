# Dictionnaire des données — `_data/siba.duckdb`

Base DuckDB `_data/siba.duckdb`, alimentée par le programme Python `siba.data`
(le paquet `src/siba/data/` — ce n'est pas le nom de la base ; voir README).
Deux sources : Hub'eau (chroniques piézométriques) et Météo-France (données
quotidiennes RR-T-Vent, Gironde). Ce document décrit chaque table et chaque
colonne. URLs des sources : voir [Sources](#sources) en bas de page.

Le descriptif officiel des champs Météo-France est mis en cache dans
`_data/Q_descriptif_champs_RR-T-Vent.csv` (téléchargé depuis data.gouv / OVH).

---

## `station` — dimension des points de mesure

| colonne | type | description |
|---|---|---|
| `station_id` | VARCHAR (PK) | identifiant interne stable (`nappe_<code_bss>` ou `meteo_<num_poste>`) |
| `source` | VARCHAR | `hubeau` (piézomètre) ou `meteofrance` (poste météo) |
| `name` | VARCHAR | libellé lisible du point |
| `lat` | DOUBLE | latitude (degrés décimaux) |
| `lon` | DOUBLE | longitude (degrés décimaux) |
| `alti` | DOUBLE | altitude (m) — renseignée pour les postes météo |
| `code_bss` | VARCHAR | code BSS du piézomètre (Hub'eau), NULL pour la météo |
| `num_poste` | VARCHAR | numéro Météo-France du poste, NULL pour la nappe |
| `of_interest` | BOOLEAN | pilote la vue `v_meteo_interest` |

---

## `nappe_mesure` — chroniques piézométriques Hub'eau

Grain : une ligne par (`code_bss`, `date_mesure`). Clé primaire
`(code_bss, date_mesure)`.

| colonne | type | description |
|---|---|---|
| `code_bss` | VARCHAR | identifiant BSS du piézomètre (ex. `08262X0023/F`) |
| `date_mesure` | DATE | date de la mesure |
| `niveau_nappe_eau` | DOUBLE | niveau de la nappe en cote NGF (altitude du plan d'eau, m) |
| `profondeur_nappe` | DOUBLE | profondeur de la nappe sous le repère/sol (m) — c'est la valeur tracée |
| `statut` | VARCHAR | statut de la donnée (ex. « Donnée contrôlée niveau 2 ») |
| `qualification` | VARCHAR | qualification : Correcte / Incorrecte / Incertaine / Non qualifié |
| `mode_obtention` | VARCHAR | mode d'obtention (ex. « Valeur mesurée ») |
| `code_producteur` | VARCHAR | code du producteur de la donnée |
| `nom_producteur` | VARCHAR | nom du producteur (ex. SGR Aquitaine) |
| `code_nature_mesure` | VARCHAR | nature de la mesure (`N` = naturel, etc.) |
| `urn_bss` | VARCHAR | URN du point d'eau dans ADES |
| `timestamp_mesure` | BIGINT | horodatage epoch (ms) de la mesure |

---

## `meteo_jour` — données quotidiennes Météo-France (Gironde)

Grain : une ligne par (`NUM_POSTE`, `date`), toutes les stations de Gironde,
toutes les colonnes brutes du fichier `Q_33_*_RR-T-Vent`. Clé primaire
`(NUM_POSTE, date)`. Les colonnes brutes sont stockées en VARCHAR (verbatim) ;
la colonne `date` (DATE) est dérivée de `AAAAMMJJ`.

À chaque grandeur `X` est associé un **code qualité** `QX` :

| code | signification |
|---|---|
| 9 | donnée filtrée (contrôles de premier niveau) |
| 0 | donnée protégée (validée définitivement par le climatologue) |
| 1 | donnée validée (contrôle automatique ou climatologue) |
| 2 | donnée douteuse, en cours de vérification |

### Colonnes

| colonne | description | unité |
|---|---|---|
| `date` | date de la mesure (dérivée de `AAAAMMJJ`) | DATE |
| `NUM_POSTE` | numéro Météo-France du poste (8 chiffres) | |
| `NOM_USUEL` | nom usuel du poste | |
| `LAT` | latitude (négative au sud) | degrés |
| `LON` | longitude (négative à l'ouest de Greenwich) | degrés |
| `ALTI` | altitude du pied de l'abri / pluviomètre | m |
| `AAAAMMJJ` | date de la mesure (année mois jour) | |
| `RR` | précipitation tombée en 24 h (06h FU J → 06h FU J+1, affectée à J) | mm et 1/10 |
| `TN` | température minimale sous abri | °C et 1/10 |
| `HTN` | heure de `TN` | hhmm |
| `TX` | température maximale sous abri | °C et 1/10 |
| `HTX` | heure de `TX` | hhmm |
| `TM` | moyenne quotidienne des températures horaires sous abri | °C et 1/10 |
| `TNTXM` | moyenne quotidienne (TN+TX)/2 | °C et 1/10 |
| `TAMPLI` | amplitude thermique quotidienne (TX−TN) | °C et 1/10 |
| `TNSOL` | température minimale à 10 cm au-dessus du sol | °C et 1/10 |
| `TN50` | température minimale à 50 cm au-dessus du sol | °C et 1/10 |
| `DG` | durée de gel sous abri (T ≤ 0 °C) | mn |
| `FFM` | moyenne quotidienne du vent moyenné sur 10 mn, à 10 m | m/s et 1/10 |
| `FF2M` | moyenne quotidienne du vent moyenné sur 10 mn, à 2 m | m/s et 1/10 |
| `FXY` | max quotidien de la force max horaire du vent (10 mn), à 10 m | m/s et 1/10 |
| `DXY` | direction de `FXY` | rose de 360 |
| `HXY` | heure de `FXY` | hhmm |
| `FXI` | max quotidien de la force max horaire du vent instantané, à 10 m | m/s et 1/10 |
| `DXI` | direction de `FXI` | rose de 360 |
| `HXI` | heure de `FXI` | hhmm |
| `FXI2` | max quotidien de la force max horaire du vent instantané, à 2 m | m/s et 1/10 |
| `DXI2` | direction de `FXI2` | rose de 360 |
| `HXI2` | heure de `FXI2` | hhmm |
| `FXI3S` | max quotidien de la force max horaire du vent moyenné sur 3 s, à 10 m | m/s et 1/10 |
| `DXI3S` | direction de `FXI3S` | rose de 360 |
| `HXI3S` | heure de `FXI3S` | hhmm |
| `DRR` | durée des précipitations | mn |
| `STATUS_FXI3S` | mode d'obtention de `FXI3S` (0 : non calculé, 1 : fonction de transfert) | |
| `STATUS_DXI3S` | mode d'obtention de `DXI3S` (0 : mesuré, 1 : assimilé à DXI) | |

Chaque grandeur ci-dessus ayant un code qualité possède aussi la colonne `Q<...>`
correspondante (`QRR`, `QTN`, `QHTN`, `QTX`, …) suivant le barème du tableau des
codes qualité.

---

## `nappe_pluie_daily` — table matérialisée (analyse croisée, base Cap-Ferret)

Grain : une ligne par jour, index journalier sans trou, de `2015-01-01` à la
dernière date disponible. Reconstruite à chaque chargement.

| colonne | type | description |
|---|---|---|
| `date` | DATE | jour |
| `Blagon` | DOUBLE | profondeur nappe Blagon (Lanton), rééchantillonnée en journalier + interpolation temporelle (trous ≤ 3 j) |
| `Piraillan` | DOUBLE | profondeur nappe Piraillan (Lège-Cap-Ferret), même traitement |
| `rr` | DOUBLE | précipitation quotidienne à Cap-Ferret (mm) |
| `rr_7d` | DOUBLE | cumul glissant de pluie sur 7 jours (NULL tant que la fenêtre n'est pas pleine) |
| `rr_14d` | DOUBLE | cumul glissant sur 14 jours |
| `rr_28d` | DOUBLE | cumul glissant sur 28 jours |
| `rr_56d` | DOUBLE | cumul glissant sur 56 jours |

Les colonnes de nappe reprennent la méthode des notebooks (resample journalier +
`interpolate(method="time", limit=3)`), pour rester comparables.

---

## `v_meteo_interest` — vue curée des stations d'intérêt

Sélection lisible des colonnes utiles pour les stations `station.of_interest`
(aujourd'hui : Cap-Ferret). Colonnes castées depuis `meteo_jour`.

| colonne | type | description |
|---|---|---|
| `num_poste` | VARCHAR | numéro du poste |
| `name` | VARCHAR | nom usuel |
| `date` | DATE | jour |
| `rr` | DOUBLE | précipitation quotidienne (mm) |
| `qrr` | INTEGER | code qualité de `rr` |
| `tn` | DOUBLE | température minimale (°C) |
| `tx` | DOUBLE | température maximale (°C) |
| `tm` | DOUBLE | température moyenne (°C) |
| `ffm` | DOUBLE | vent moyen à 10 m (m/s) |
| `fxy` | DOUBLE | rafale (max horaire du vent moyenné 10 mn) à 10 m (m/s) |

---

## `ingest_log` — journal des chargements

| colonne | type | description |
|---|---|---|
| `source` | VARCHAR | `hubeau` ou `meteofrance` |
| `scope` | VARCHAR | portée du chargement (ex. `nappe 2010-2026`, `meteo latest`) |
| `mode` | VARCHAR | `update` ou `rebuild` |
| `rows_upserted` | BIGINT | nombre de lignes insérées/mises à jour |
| `date_min` | DATE | première date couverte par le chargement |
| `date_max` | DATE | dernière date couverte |
| `fetched_at` | TIMESTAMP | horodatage du chargement |

---

## `hc_period` — périodes « hors de contrôle » (HC) du réseau eaux usées

Données curées à la main (fixture `src/siba/data/fixtures/events.toml`), remplacées
intégralement à chaque `update` / `rebuild`. Une ligne par période HC signalée.

| colonne | type | description |
|---|---|---|
| `start_date` | DATE | début de la période HC |
| `end_date` | DATE | fin de la période HC |
| `label` | VARCHAR | libellé lisible de l'épisode |
| `communes` | VARCHAR[] | communes concernées (liste) |
| `cause` | VARCHAR | cause rapportée (saturation réseau, surverses…) |
| `source` | VARCHAR | source de l'information |
| `verified` | BOOLEAN | `true` = date confirmée par arrêté préfectoral / constat OFB officiel ; `false` = date estimée / rapportée (presse, lanceurs d'alerte) |

---

## `interdiction_period` — interdictions préfectorales (pêche / commercialisation coquillages)

Fixture curée, remplacée intégralement à chaque chargement. Bassin d'Arcachon +
Banc d'Arguin. Une ligne par arrêté d'interdiction.

| colonne | type | description |
|---|---|---|
| `start_date` | DATE | début de l'interdiction |
| `end_date` | DATE | fin (levée) de l'interdiction |
| `label` | VARCHAR | libellé lisible de l'épisode |
| `especes` | VARCHAR[] | espèces / coquillages visés (liste) |
| `cause` | VARCHAR | cause (norovirus origine EU, toxines algales…) |
| `source` | VARCHAR | source de l'information |
| `verified` | BOOLEAN | `true` = date confirmée par arrêté préfectoral / constat OFB officiel ; `false` = date estimée / rapportée |
| `peche_loisir` | BOOLEAN | l'interdiction couvre aussi la pêche de loisir |

---

## `v_nappe_pluie_events` — vue journalière nappe/pluie + drapeaux d'événements

Vue construite sur `nappe_pluie_daily` (toutes ses colonnes reprises via `d.*`),
augmentée de deux drapeaux booléens par jour, pour l'analyse de corrélation.

| colonne | type | description |
|---|---|---|
| *(colonnes de `nappe_pluie_daily`)* | | `date`, `Blagon`, `Piraillan`, `rr`, `rr_7d`, `rr_14d`, `rr_28d`, `rr_56d` |
| `in_hc` | BOOLEAN | le jour tombe dans au moins une période `hc_period` |
| `in_interdiction` | BOOLEAN | le jour tombe dans au moins une période `interdiction_period` |

---

## Sources

Données récupérées directement depuis les portails open data (voir
`src/siba/data/config.py`).

### Nappe — Hub'eau (piézométrie)

- API chroniques : <https://hubeau.eaufrance.fr/api/v1/niveaux_nappes/chroniques>
- Documentation : <https://hubeau.eaufrance.fr/page/api-piezometrie>
- Stations (fiches ADES) :
  - Blagon (Lanton) `08262X0023/F` : <https://ades.eaufrance.fr/Fiche/PointEau?code=08262X0023/F>
  - Piraillan (Lège-Cap-Ferret) `08257X0086/F` : <https://ades.eaufrance.fr/Fiche/PointEau?code=08257X0086/F>

### Pluie — Météo-France (données climatologiques quotidiennes, Gironde)

- Portail open data : <https://meteo.data.gouv.fr/>
- Fichier « previous » (1950-2024) : <https://www.data.gouv.fr/api/1/datasets/r/b0e78f3d-9085-4d6d-a47d-6d942f5e9a54>
- Fichier « latest » (année en cours) : <https://www.data.gouv.fr/api/1/datasets/r/5f196a76-ba4f-4aa7-af28-eff6c8797b50>
- Descriptif des champs : <https://meteofrance.s3.sbg.io.cloud.ovh.net/data/synchro_ftp/BASE/QUOT/Q_descriptif_champs_RR-T-Vent.csv>
- Poste utilisé : Cap-Ferret `33236002`

---

## `analyse_bacterio` — analyses bactériologiques (portail Enki)

Un prélèvement par ligne. Source : exports annuels du portail Enki du SIBA
(`scripts/fetch_enki.py`, derrière authentification), déposés dans
`_data/enki/`. Chaque CSV annuel fait foi : le chargement **remplace l'année
entière**, ce qui absorbe les corrections amont et les `context_id` dupliqués
(un même prélèvement peut porter deux analyses) sans clé primaire artificielle.

Unité des deux mesures : **UFC/100 mL**.

| colonne | type | description |
|---|---|---|
| `annee` | INTEGER | année du fichier source ; clé de remplacement |
| `context_id` | VARCHAR | identifiant Enki du prélèvement (**non unique**) |
| `date_prelevement` | DATE | date de début du prélèvement |
| `date_fin` | DATE | date de fin |
| `heure_debut` / `heure_fin` | VARCHAR | heures (`hh:mm`) |
| `point` | VARCHAR | point d'échantillonnage (ex. `0503-LEPONTEILS`) |
| `latitude` / `longitude` | DOUBLE | coordonnées du point |
| `laboratoire` | VARCHAR | sonde ou laboratoire ayant réalisé la mesure |
| `etendue_eau` | VARCHAR | étendue d'eau |
| `bassin_versant` | VARCHAR | bassin versant |
| `justification` | VARCHAR | justification du point d'échantillonnage |
| `ecoli` | DOUBLE | *Escherichia coli* (UFC/100 mL) |
| `ecoli_censure` | VARCHAR | `<`, `=` ou `>` — voir ci-dessous |
| `ecoli_raw` | VARCHAR | valeur brute telle qu'exportée |
| `entero` | DOUBLE | entérocoques (UFC/100 mL) |
| `entero_censure` | VARCHAR | `<`, `=` ou `>` |
| `entero_raw` | VARCHAR | valeur brute |

**Valeurs censurées.** Le laboratoire rend parfois `<10.0` (sous la limite de
détection) ou `>2419.6` (plafond de quantification Colilert/IDEXX). La borne est
stockée dans `ecoli` / `entero` **et** signalée par `*_censure` : filtrer sur
`censure = '='` pour ne garder que les valeurs exactes, et ne pas traiter un
`>2419.6` comme un 2419,6 — ce sont justement les épisodes les plus contaminés.

**Couverture.** Les analyses commencent en 2014 : le portail n'exporte même pas
les colonnes de mesure pour 2012-2013 (elles valent alors NULL). Les colonnes
météo de l'export (ciel, précipitations, vagues, vent) ne sont jamais
renseignées côté source et ne sont donc pas reprises ici.
