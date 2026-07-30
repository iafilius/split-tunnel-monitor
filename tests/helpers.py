"""Shared test helper utilities (importable from within the tests package)."""
import os


def load_fixture(fixtures_dir: str, name: str) -> str:
    """Load a fixture file and return its contents as a string."""
    path = os.path.join(fixtures_dir, name)
    with open(path, encoding="utf-8") as f:
        return f.read()
