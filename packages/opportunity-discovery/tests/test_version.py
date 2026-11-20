"""The reported version must match the package metadata."""

import tomllib
from pathlib import Path

from opportunity_discovery import USER_AGENT, __version__


def test_version_matches_pyproject():
    pyproject = tomllib.loads((Path(__file__).parent.parent / "pyproject.toml").read_text(encoding="utf-8"))
    assert __version__ == pyproject["project"]["version"]
    assert f"opportunity-discovery/{__version__} " in USER_AGENT
