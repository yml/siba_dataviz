import pandas as pd

from siba.db import sources

NAPPE_COLS = [
    "code_bss", "date_mesure", "niveau_nappe_eau", "profondeur_nappe",
    "statut", "qualification", "mode_obtention", "code_producteur",
    "nom_producteur", "code_nature_mesure", "urn_bss", "timestamp_mesure",
]


class _FakeResp:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def json(self):
        return self._payload


class _FakeSession:
    """Renvoie une page de données puis une page vide (fin de pagination)."""

    def __init__(self, records):
        self._pages = [
            {"data": records, "next": None},
        ]
        self.calls = 0

    def get(self, url, params=None, timeout=None):
        page = self._pages[self.calls] if self.calls < len(self._pages) else {"data": [], "next": None}
        self.calls += 1
        return _FakeResp(page)


def test_fetch_nappe_year_maps_columns():
    rec = {
        "code_bss": "08262X0023/F", "date_mesure": "2024-01-01",
        "niveau_nappe_eau": 45.44, "profondeur_nappe": 1.26,
        "statut": "Donnée contrôlée niveau 2", "qualification": "Correcte",
        "mode_obtention": "Valeur mesurée", "code_producteur": "327",
        "nom_producteur": "SGR Aquitaine", "code_nature_mesure": "N",
        "urn_bss": "http://x", "timestamp_mesure": 1704124800000,
    }
    df = sources.fetch_nappe_year("08262X0023/F", 2024, session=_FakeSession([rec]))
    assert list(df.columns) == NAPPE_COLS
    assert len(df) == 1
    assert df.loc[0, "profondeur_nappe"] == 1.26
    assert pd.api.types.is_datetime64_any_dtype(df["date_mesure"])


def test_fetch_nappe_year_empty_has_columns():
    df = sources.fetch_nappe_year("X/F", 2024, session=_FakeSession([]))
    assert list(df.columns) == NAPPE_COLS
    assert df.empty
