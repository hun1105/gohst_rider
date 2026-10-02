"""Resolve the map output directory without machine-specific absolute paths."""

import os

# 지도 저장 위치를 바꾸려면: export TB3_MAP_DIR=/원하는/경로
MAP_DIR_ENV = 'TB3_MAP_DIR'
DEFAULT_MAP_DIR = os.path.join('~', 'tb3_maps')


def map_directory() -> str:
    """Return $TB3_MAP_DIR, else ~/tb3_maps, as an absolute path."""
    return os.path.abspath(
        os.path.expanduser(os.environ.get(MAP_DIR_ENV, DEFAULT_MAP_DIR))
    )


def map_path(name: str) -> str:
    """Return the map output path (without extension) for the given base name."""
    return os.path.join(map_directory(), name)
