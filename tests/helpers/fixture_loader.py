from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd


FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures"


def fixture_path(filename: str) -> Path:
    path = FIXTURE_DIR / filename
    if not path.is_file():
        raise FileNotFoundError(f"Fixture does not exist: {filename}")
    return path


def load_csv_fixture(filename: str, **kwargs) -> pd.DataFrame:
    options = {"encoding": "utf-8"}
    options.update(kwargs)
    return pd.read_csv(fixture_path(filename), **options)


def copy_fixture_to_temp(filename: str, temp_dir: str | Path) -> Path:
    destination_dir = Path(temp_dir)
    destination_dir.mkdir(parents=True, exist_ok=True)
    return Path(shutil.copy2(fixture_path(filename), destination_dir / filename))
