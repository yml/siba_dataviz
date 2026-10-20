import json

import pandas as pd
import pytest
import requests

from siba.data import config, sources

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

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(str(self.status_code))


class _FakeSession:
    """Sert les pages données dans l'ordre, puis une page vide (fin de pagination)."""

    def __init__(self, pages):
        self._pages = pages
        self.calls = 0

    def get(self, url, params=None, timeout=None):
        page = self._pages[self.calls] if self.calls < len(self._pages) else {"data": [], "next": None}
        self.calls += 1
        return _FakeResp(page)


_REC = {
    "code_bss": "08262X0023/F", "date_mesure": "2024-01-01",
    "niveau_nappe_eau": 45.44, "profondeur_nappe": 1.26,
    "statut": "Donnée contrôlée niveau 2", "qualification": "Correcte",
    "mode_obtention": "Valeur mesurée", "code_producteur": "327",
    "nom_producteur": "SGR Aquitaine", "code_nature_mesure": "N",
    "urn_bss": "http://x", "timestamp_mesure": 1704124800000,
    "code_continuite": "2",
}


@pytest.mark.functional
def test_download_nappe_year_writes_merged_pages_with_all_fields(tmp_path):
    rec1 = _REC
    rec2 = {**_REC, "date_mesure": "2024-01-02", "profondeur_nappe": 1.3}
    sess = _FakeSession([{"data": [rec1], "next": "url"}, {"data": [rec2], "next": None}])
    dest = tmp_path / "x" / "2024.json"
    out = sources.download_nappe_year("08262X0023/F", 2024, dest, session=sess)
    assert out == dest
    # Les deux pages fusionnées, champ hors schéma (code_continuite) conservé.
    assert json.loads(dest.read_text(encoding="utf-8")) == [rec1, rec2]
    assert not [p for p in dest.parent.iterdir() if p.name.endswith(".tmp")]


@pytest.mark.functional
def test_download_nappe_year_empty_writes_empty_list(tmp_path):
    dest = tmp_path / "2024.json"
    sources.download_nappe_year("X/F", 2024, dest, session=_FakeSession([]))
    assert json.loads(dest.read_text(encoding="utf-8")) == []


@pytest.mark.functional
def test_read_nappe_year_maps_columns(tmp_path):
    path = tmp_path / "2024.json"
    path.write_text(json.dumps([_REC]), encoding="utf-8")
    df = sources.read_nappe_year(path)
    assert list(df.columns) == NAPPE_COLS
    assert len(df) == 1
    assert df.loc[0, "profondeur_nappe"] == 1.26
    assert pd.api.types.is_datetime64_any_dtype(df["date_mesure"])


@pytest.mark.functional
def test_read_nappe_year_empty_has_columns(tmp_path):
    path = tmp_path / "2024.json"
    path.write_text("[]", encoding="utf-8")
    df = sources.read_nappe_year(path)
    assert list(df.columns) == NAPPE_COLS
    assert df.empty


@pytest.mark.functional
def test_download_meteo_file_keeps_gz_as_downloaded(tmp_path, monkeypatch):
    import gzip
    import io

    payload = b"NUM_POSTE;AAAAMMJJ;RR\n33236002;20250101;1.0\n"
    gz = io.BytesIO()
    with gzip.GzipFile(fileobj=gz, mode="wb") as f:
        f.write(payload)
    gz_bytes = gz.getvalue()

    class _Resp:
        url = "https://x/Q_33_latest-2025-2026_RR-T-Vent.csv.gz"
        status_code = 200

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def iter_content(self, chunk_size=1):
            yield gz_bytes

        def raise_for_status(self):
            pass

    def _fake_get(url, stream=False, timeout=None, allow_redirects=True):
        return _Resp()

    monkeypatch.setattr(sources.requests, "get", _fake_get)
    dest = tmp_path / "mf" / "latest.csv.gz"
    out = sources.download_meteo_file("https://data.gouv/whatever", dest)
    assert out == dest
    assert dest.read_bytes() == gz_bytes  # tel que téléchargé, pas décompressé
    assert not [p for p in dest.parent.iterdir() if p.name.endswith(".tmp")]


def test_download_meteo_descriptor_writes_file(tmp_path, monkeypatch):
    payload = b"NOM_CHAMP;DESCRIPTION\nRR;precipitation en 24h\n"

    class _Resp:
        status_code = 200

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def iter_content(self, chunk_size=1):
            yield payload

        def raise_for_status(self):
            pass

    def _fake_get(url, stream=False, timeout=None, allow_redirects=True):
        return _Resp()

    monkeypatch.setattr(sources.requests, "get", _fake_get)
    dest = tmp_path / "Q_descriptif_champs_RR-T-Vent.csv"
    out = sources.download_meteo_descriptor(dest)
    assert out == dest
    assert dest.read_bytes() == payload


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    """Neutralise les back-off/délais réseau pour garder les tests rapides."""
    monkeypatch.setattr(sources.time, "sleep", lambda *_a, **_k: None)


class _TimeoutThenOk:
    """Timeout au 1er appel, données ensuite (transient network hiccup)."""

    def __init__(self, records):
        self.records = records
        self.calls = 0

    def get(self, url, params=None, timeout=None):
        self.calls += 1
        if self.calls == 1:
            raise requests.exceptions.Timeout("boom")
        return _FakeResp({"data": self.records, "next": None})


class _AlwaysStatus:
    def __init__(self, status):
        self.status = status
        self.calls = 0

    def get(self, url, params=None, timeout=None):
        self.calls += 1
        return _FakeResp({}, status=self.status)


@pytest.mark.functional
def test_download_nappe_year_retries_on_timeout(tmp_path):
    rec = {"code_bss": "A/F", "date_mesure": "2024-01-01", "profondeur_nappe": 1.0}
    sess = _TimeoutThenOk([rec])
    dest = tmp_path / "2024.json"
    sources.download_nappe_year("A/F", 2024, dest, session=sess)
    assert json.loads(dest.read_text(encoding="utf-8")) == [rec]
    assert sess.calls == 2  # retried after the first timeout


@pytest.mark.functional
def test_download_nappe_year_raises_on_persistent_5xx(tmp_path):
    sess = _AlwaysStatus(500)
    dest = tmp_path / "2024.json"
    with pytest.raises(RuntimeError):
        sources.download_nappe_year("A/F", 2024, dest, session=sess)
    assert sess.calls == config.NAPPE_MAX_RETRIES  # retried, then gave up
    assert not dest.exists()


@pytest.mark.functional
def test_download_nappe_year_raises_on_client_error(tmp_path):
    # A 404 is a real failure, not "no data": it must surface, not return empty.
    sess = _AlwaysStatus(404)
    dest = tmp_path / "2024.json"
    with pytest.raises(requests.exceptions.HTTPError):
        sources.download_nappe_year("A/F", 2024, dest, session=sess)
    assert sess.calls == 1  # client error is not retried
    assert not dest.exists()
