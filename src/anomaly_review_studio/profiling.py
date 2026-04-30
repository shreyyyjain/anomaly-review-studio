from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


@dataclass
class ColumnProfile:
    column: str
    dtype: str
    non_null_count: int
    missing_count: int
    missing_pct: float
    unique_count: int
    top_value: str
    top_value_count: int
    min_value: str | None = None
    max_value: str | None = None
    mean_value: float | None = None
    std_value: float | None = None
    inferred_semantics: str = "unknown"

    def as_dict(self) -> dict[str, Any]:
        return {
            "column": self.column,
            "dtype": self.dtype,
            "non_null_count": self.non_null_count,
            "missing_count": self.missing_count,
            "missing_pct": round(self.missing_pct, 2),
            "unique_count": self.unique_count,
            "top_value": self.top_value,
            "top_value_count": self.top_value_count,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "mean_value": self.mean_value,
            "std_value": self.std_value,
            "inferred_semantics": self.inferred_semantics,
        }


class DatasetProfile:
    def __init__(self, columns: list[ColumnProfile], row_count: int):
        self.columns = columns
        self.row_count = row_count

    def as_records(self) -> list[dict[str, Any]]:
        return [column.as_dict() for column in self.columns]

    @property
    def total_missing(self) -> int:
        return sum(column.missing_count for column in self.columns)


def profile_dataframe(dataframe: pd.DataFrame) -> DatasetProfile:
    columns: list[ColumnProfile] = []
    row_count = len(dataframe)

    for column_name in dataframe.columns:
        series = dataframe[column_name]
        non_null_count = int(series.notna().sum())
        missing_count = int(series.isna().sum())
        missing_pct = (missing_count / row_count * 100.0) if row_count else 0.0
        unique_count = int(series.nunique(dropna=True))
        top_value = _safe_string(series.mode(dropna=True).iloc[0]) if unique_count else ""
        top_value_count = int(series.value_counts(dropna=True).iloc[0]) if unique_count else 0
        dtype = str(series.dtype)
        inferred_semantics = _infer_semantics(series, column_name)
        min_value, max_value, mean_value, std_value = _numeric_summary(series)
        columns.append(
            ColumnProfile(
                column=column_name,
                dtype=dtype,
                non_null_count=non_null_count,
                missing_count=missing_count,
                missing_pct=missing_pct,
                unique_count=unique_count,
                top_value=top_value,
                top_value_count=top_value_count,
                min_value=min_value,
                max_value=max_value,
                mean_value=mean_value,
                std_value=std_value,
                inferred_semantics=inferred_semantics,
            )
        )

    return DatasetProfile(columns=columns, row_count=row_count)


def _infer_semantics(series: pd.Series, column_name: str) -> str:
    lower_name = column_name.lower()
    if any(token in lower_name for token in ["id", "key"]):
        return "identifier"
    if any(token in lower_name for token in ["date", "time", "timestamp"]):
        return "datetime"
    if pd.api.types.is_numeric_dtype(series):
        return "numeric"
    if series.dropna().astype(str).str.match(r"^\d{5}(-\d{4})?$", na=False).mean() > 0.6:
        return "postal_code"
    return "categorical"


def _numeric_summary(series: pd.Series) -> tuple[str | None, str | None, float | None, float | None]:
    numeric = pd.to_numeric(series, errors="coerce")
    valid_numeric = numeric.dropna()
    if valid_numeric.empty:
        return None, None, None, None
    min_value = _safe_string(valid_numeric.min())
    max_value = _safe_string(valid_numeric.max())
    mean_value = float(np.round(valid_numeric.mean(), 2))
    std_value = float(np.round(valid_numeric.std(ddof=0), 2)) if len(valid_numeric) > 1 else 0.0
    return min_value, max_value, mean_value, std_value


def _safe_string(value: Any) -> str:
    if pd.isna(value):
        return ""
    return str(value)
