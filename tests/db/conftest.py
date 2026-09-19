import pytest

from siba.db import schema


@pytest.fixture
def con(tmp_path):
    """Connexion DuckDB temporaire avec schéma créé."""
    c = schema.connect(tmp_path / "test.duckdb")
    schema.create_all(c)
    yield c
    c.close()
