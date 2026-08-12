from importlib.metadata import version as _get_version
from pathlib import Path

__version__ = _get_version("pds")

version = __version__


def get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent
