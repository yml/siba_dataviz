import importlib.util
import tomllib

import pytest

from siba.paths import REPO_ROOT


@pytest.mark.internal
def test_siba_exports_only_paths():
    import siba

    assert set(siba.__all__) == {"DATA_DIR", "REPO_ROOT", "RESULTS_DIR"}
    assert not hasattr(siba, "fetch_nappe")
    assert importlib.util.find_spec("siba.nappe") is None


@pytest.mark.internal
def test_pyproject_has_no_jupyter_deps():
    with open(REPO_ROOT / "pyproject.toml", "rb") as f:
        deps = tomllib.load(f)["project"]["dependencies"]
    retirees = ("nbdime", "notebook", "seaborn", "tabulate", "jinja2")
    assert [d for d in deps if d.startswith(retirees)] == []
