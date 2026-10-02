import pytest

from hackkit.cache import DiskCache


@pytest.fixture
def cache(tmp_path):
    return DiskCache(tmp_path / "cache")
