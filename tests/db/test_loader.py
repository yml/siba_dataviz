import pandas as pd

from siba.db import config, loader, schema, sources


def _con(tmp_path):
    c = schema.connect(tmp_path / "t.duckdb")
    schema.create_all(c)
    schema.seed_stations(c)
    return c


def _fake_nappe(code_bss, year, **kwargs):
    return pd.DataFrame({
        "code_bss": [code_bss],
        "date_mesure": [pd.Timestamp(f"{year}-06-01")],
        "niveau_nappe_eau": [10.0], "profondeur_nappe": [1.0],
        "statut": ["s"], "qualification": ["Correcte"], "mode_obtention": ["m"],
        "code_producteur": ["327"], "nom_producteur": ["p"],
        "code_nature_mesure": ["N"], "urn_bss": ["u"], "timestamp_mesure": [1],
    })


def test_load_nappe_upserts_all_piezos(tmp_path):
    con = _con(tmp_path)
    n = loader._load_nappe(con, [2024], fetch=_fake_nappe)
    assert n == len(config.PIEZOMETERS)
    count = con.execute("SELECT COUNT(*) FROM nappe_mesure").fetchone()[0]
    assert count == len(config.PIEZOMETERS)
    # idempotent: re-run does not duplicate
    loader._load_nappe(con, [2024], fetch=_fake_nappe)
    count2 = con.execute("SELECT COUNT(*) FROM nappe_mesure").fetchone()[0]
    assert count2 == len(config.PIEZOMETERS)
    con.close()


def test_load_meteo_upserts_and_cleans_temp(tmp_path, meteo_csv):
    con = _con(tmp_path)
    seen = {}

    def _dl(url, dest_dir):
        # simulate download by copying fixture into the temp dir
        import shutil
        from pathlib import Path
        dest = Path(dest_dir) / "Q_33.csv"
        shutil.copy(meteo_csv, dest)
        seen["dir"] = Path(dest_dir)
        return dest

    n = loader._load_meteo(con, ["latest"], download=_dl, read=sources.read_meteo_csv)
    assert n == 3
    count = con.execute("SELECT COUNT(*) FROM meteo_jour").fetchone()[0]
    assert count == 3
    # temp dir cleaned
    assert not seen["dir"].exists()
    con.close()
