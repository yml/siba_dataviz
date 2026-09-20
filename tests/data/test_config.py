import tomllib
from pathlib import Path

from siba.data import config


def test_events_toml_fixture_ships_and_parses():
    assert config.EVENTS_TOML.exists()
    assert isinstance(config.EVENTS_TOML, Path)
    with open(config.EVENTS_TOML, "rb") as f:
        data = tomllib.load(f)
    assert len(data["hc_period"]) == 9
    assert len(data["interdiction_period"]) == 4


def test_db_path_under_data_dir():
    from siba.paths import DATA_DIR

    assert config.DB_PATH == DATA_DIR / "siba.duckdb"
    assert isinstance(config.DB_PATH, Path)


def test_piezometers_have_required_keys():
    assert len(config.PIEZOMETERS) == 2
    for p in config.PIEZOMETERS:
        assert set(p) >= {"code_bss", "name", "col", "station_id"}


def test_cap_ferret_is_a_station_of_interest():
    numeros = {s["num_poste"] for s in config.METEO_STATIONS_OF_INTEREST}
    assert config.CAP_FERRET_NUM_POSTE in numeros


def test_rain_windows_and_meteo_columns():
    assert config.RAIN_WINDOWS == [7, 14, 28, 56]
    assert config.INTERP_LIMIT == 3
    # Full raw Météo-France header is captured verbatim.
    assert config.METEO_COLUMNS[:6] == [
        "NUM_POSTE", "NOM_USUEL", "LAT", "LON", "ALTI", "AAAAMMJJ",
    ]
    assert "RR" in config.METEO_COLUMNS
    assert len(config.METEO_COLUMNS) == 60
