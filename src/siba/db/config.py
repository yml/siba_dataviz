"""Constantes du flux DuckDB : chemins, stations, URLs, fenêtres."""

from siba.paths import DATA_DIR

#: Base DuckDB (respecte SIBA_DATA_DIR via DATA_DIR).
DB_PATH = DATA_DIR / "siba.duckdb"

#: API chroniques piézométriques Hub'eau.
HUBEAU_URL = "https://hubeau.eaufrance.fr/api/v1/niveaux_nappes/chroniques.json"

#: Piézomètres suivis. ``col`` = nom de colonne dans nappe_pluie_daily.
PIEZOMETERS = [
    {
        "code_bss": "08262X0023/F",
        "name": "Blagon (Lanton)",
        "col": "Blagon",
        "station_id": "nappe_08262X0023_F",
    },
    {
        "code_bss": "08257X0086/F",
        "name": "Piraillan (Lège-Cap-Ferret)",
        "col": "Piraillan",
        "station_id": "nappe_08257X0086_F",
    },
]

#: Stations météo dont on veut une vue curée pratique.
METEO_STATIONS_OF_INTEREST = [
    {"num_poste": "33236002", "name": "CAP-FERRET", "station_id": "meteo_33236002"},
]

#: Station de référence pour la table fusionnée.
CAP_FERRET_NUM_POSTE = "33236002"

#: Première année de nappe chargée lors d'un rebuild.
NAPPE_START_YEAR = 2010

#: Début de la table fusionnée journalière.
DAILY_START = "2015-01-01"

#: Fichiers Météo-France Gironde (data.gouv.fr, redirigés vers OVH S3).
METEO_URLS = {
    "previous": "https://www.data.gouv.fr/api/1/datasets/r/b0e78f3d-9085-4d6d-a47d-6d942f5e9a54",
    "latest": "https://www.data.gouv.fr/api/1/datasets/r/5f196a76-ba4f-4aa7-af28-eff6c8797b50",
}

#: Descriptif officiel des champs Météo-France (mis en cache dans _data au rebuild).
METEO_DESCRIPTOR_URL = "https://meteofrance.s3.sbg.io.cloud.ovh.net/data/synchro_ftp/BASE/QUOT/Q_descriptif_champs_RR-T-Vent.csv"

#: Fenêtres glissantes de cumul de pluie (jours).
RAIN_WINDOWS = [7, 14, 28, 56]

#: Limite d'interpolation temporelle des nappes (jours).
INTERP_LIMIT = 3

#: Robustesse Hub'eau : nombre de tentatives et back-off (s) de base sur
#: timeout / HTTP 429 / 5xx.
NAPPE_MAX_RETRIES = 3
NAPPE_BACKOFF = 1.0

#: Délai (s) entre deux requêtes annuelles Hub'eau, pour éviter le throttling
#: lors d'un rebuild qui enchaîne les années. Mis à 0 dans les tests.
NAPPE_REQUEST_DELAY = 1.0

#: En-tête brut complet des fichiers Q_33_*_RR-T-Vent (60 colonnes).
METEO_COLUMNS = [
    "NUM_POSTE", "NOM_USUEL", "LAT", "LON", "ALTI", "AAAAMMJJ",
    "RR", "QRR", "TN", "QTN", "HTN", "QHTN", "TX", "QTX", "HTX", "QHTX",
    "TM", "QTM", "TNTXM", "QTNTXM", "TAMPLI", "QTAMPLI", "TNSOL", "QTNSOL",
    "TN50", "QTN50", "DG", "QDG", "FFM", "QFFM", "FF2M", "QFF2M",
    "FXY", "QFXY", "DXY", "QDXY", "HXY", "QHXY", "FXI", "QFXI",
    "DXI", "QDXI", "HXI", "QHXI", "FXI2", "QFXI2", "DXI2", "QDXI2",
    "HXI2", "QHXI2", "FXI3S", "QFXI3S", "DXI3S", "QDXI3S", "HXI3S", "QHXI3S",
    "DRR", "QDRR", "STATUS_FXI3S", "STATUS_DXI3S",
]
