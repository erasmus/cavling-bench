import shutil
from pathlib import Path

import pytest

from danews.config import Config, Paths

REPO = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def make_fixture_root(dst: Path) -> Paths:
    """Build a repo-shaped tree: fixture data + the real tasks/styleguides/prompts/wordlists."""
    shutil.copytree(FIXTURES / "data", dst / "data")
    shutil.copytree(REPO / "data" / "wordlists", dst / "data" / "wordlists")
    for d in ("tasks", "styleguides", "prompts"):
        shutil.copytree(REPO / d, dst / d)
    shutil.copy(FIXTURES / "models.yaml", dst / "models.yaml")
    return Paths(dst)


@pytest.fixture
def fixture_cfg(tmp_path) -> Config:
    return Config(make_fixture_root(tmp_path / "root"))
