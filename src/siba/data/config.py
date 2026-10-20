"""Constantes du flux DuckDB : chemins, stations, URLs, fenêtres."""

from pathlib import Path

from siba.paths import DATA_DIR

#: Base DuckDB (respecte SIBA_DATA_DIR via DATA_DIR).
DB_PATH = DATA_DIR / "siba.duckdb"

#: Fichiers sources tels que téléchargés (JSON Hub'eau, .csv.gz Météo-France).
SOURCES_DIR = DATA_DIR / "sources"

#: Fixture TOML des événements curés (HC réseau EU + interdictions coquillages).
EVENTS_TOML = Path(__file__).parent / "fixtures" / "events.toml"

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
    {
        # Canauley DFCI, ouvrage de 7,65 m, même masse d'eau que Blagon.
        "code_bss": "08266X0003/F",
        "name": "Canauley (Biganos)",
        "col": "Biganos",
        "station_id": "nappe_08266X0003_F",
    },
    {
        # Villemarie 126, ouvrage de 20 m, rive sud : hors bassin de collecte
        # de la STEP de Biganos.
        "code_bss": "08494X0126/PZ1",
        "name": "Villemarie (La Teste-de-Buch)",
        "col": "La_Teste",
        "station_id": "nappe_08494X0126_PZ1",
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

#: Fichiers Météo-France Gironde (data.gouv.fr, redirigés vers OVH S3). L'ordre
#: est l'ordre d'ingestion : le plus récent en dernier.
METEO_URLS = {
    # Archive avant 1950 (figée, chargée par rebuild seulement).
    "historical": "https://www.data.gouv.fr/api/1/datasets/r/f74e1970-5462-4981-87e5-fb535b2c1af1",
    "previous": "https://www.data.gouv.fr/api/1/datasets/r/b0e78f3d-9085-4d6d-a47d-6d942f5e9a54",
    "latest": "https://www.data.gouv.fr/api/1/datasets/r/5f196a76-ba4f-4aa7-af28-eff6c8797b50",
}

#: Postes Météo-France conservés dans meteo_jour (filtre à l'ingestion). Un
#: poste hors liste reste disponible dans les fichiers sources.
METEO_STATIONS = [
    "33236002",  # Cap-Ferret, 1921 → : référence ; rupture de site le 11/07/2023
    "33529001",  # Cazaux (base aérienne), 1921 → : même site depuis 1944, classe B
    "33122003",  # Pierroton-INRAE (Cestas), 2002 → : intérieur, classe E
    "33042001",  # Belin-Béliet, 1881 → : changement de pluviomètre 21/07/2021 sans effet visible
    "33051001",  # Biganos, 1964–2021 : rive est, près de la STEP
    "33236004",  # Lège-Bourg, 2003–2020 : rive nord
    "33011001",  # Arès, 1882–2003 : rive nord-est
    "33009001",  # Arcachon, 1947–2001 : rivage
    "33019001",  # Audenge Agglomération, 1882–1906 : utilisé par l'ancienne analyse 70 mm
    "33529004",  # La Teste-de-Buch-La Salie, 1881–1950 : plus longue série avant 1950
    "33009004",  # Arcachon Agglomération - CMD, 1885–1946 : longue série d'Arcachon
]

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

#: En-tête brut complet des fichiers Météo-France Q_33_*_RR-T-Vent : les 60 noms
#: de colonnes, dans l'ordre du fichier source. Signification de chaque champ :
#: descriptif officiel (``METEO_DESCRIPTOR_URL``, mis en cache dans ``_data/``)
#: et ``DATA_DICTIONARY.md``.
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

#: Exports Enki (analyses bactériologiques), un CSV par année, déposés par
#: ``scripts/fetch_enki.py``. Le portail est derrière un login : la récupération
#: reste manuelle, le chargement est automatique.
ENKI_DIR = DATA_DIR / "enki"

#: Unité des analyses bactériologiques (constante dans l'export, pas stockée
#: ligne à ligne).
ENKI_UNIT = "UFC/100mL"
