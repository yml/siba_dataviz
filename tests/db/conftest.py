import pandas as pd
import pytest

from siba.db import schema


@pytest.fixture
def con(tmp_path):
    """Connexion DuckDB temporaire avec schéma créé."""
    c = schema.connect(tmp_path / "test.duckdb")
    schema.create_all(c)
    yield c
    c.close()


@pytest.fixture
def meteo_csv(tmp_path):
    """Petit CSV Météo-France (;-delimited), 2 stations, colonnes partielles."""
    path = tmp_path / "Q_33_sample.csv"
    header = "NUM_POSTE;NOM_USUEL;LAT;LON;ALTI;AAAAMMJJ;RR;QRR"
    rows = [
        "33236002;CAP-FERRET;44.6305;-1.251667;8;20250101;0.0;1",
        "33236002;CAP-FERRET;44.6305;-1.251667;8;20250102;5.5;1",
        "33999999;AUTRE;44.0;-0.5;50;20250101;2.0;1",
    ]
    path.write_text("\n".join([header, *rows]) + "\n", encoding="utf-8")
    return path
