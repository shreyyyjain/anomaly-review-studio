from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

import pandas as pd


def load_csv_data(uploaded_file: Any) -> pd.DataFrame:
    try:
        dataframe = pd.read_csv(uploaded_file)
    except Exception as exc:  # noqa: BLE001
        raise ValueError("Could not read the uploaded file as CSV.") from exc
    return _normalize_dataframe(dataframe)


def load_demo_data(file_path: Path) -> pd.DataFrame:
    if not file_path.exists():
        raise ValueError(f"Demo dataset not found: {file_path}")
    dataframe = pd.read_csv(file_path)
    return _normalize_dataframe(dataframe)


def validate_dataframe(dataframe: pd.DataFrame, expected_columns: Iterable[str] | None = None) -> str | None:
    if dataframe.empty:
        return "The dataset is empty. Upload a file with at least one row."
    if dataframe.columns.empty:
        return "The dataset does not contain any columns."
    if expected_columns:
        missing = [column for column in expected_columns if column not in dataframe.columns]
        if missing:
            return f"Missing required columns: {', '.join(missing)}"
    return None


def _normalize_dataframe(dataframe: pd.DataFrame) -> pd.DataFrame:
    result = dataframe.copy()
    result.columns = [str(column).strip().lower().replace(" ", "_") for column in result.columns]
    return result
