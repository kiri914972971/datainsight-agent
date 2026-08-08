from __future__ import annotations

import warnings

import pandas as pd


def parse_datetime_series(series: pd.Series) -> pd.Series:
    """Safely parse complete dates while preserving mixed string formats."""
    source = series.copy(deep=True)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        if pd.api.types.is_datetime64_any_dtype(source.dtype):
            parsed = pd.to_datetime(
                source,
                errors="coerce",
            )
        elif pd.api.types.is_numeric_dtype(source.dtype):
            parsed = pd.Series(
                pd.NaT,
                index=source.index,
                name=source.name,
                dtype="datetime64[ns]",
            )
        else:
            try:
                parsed = pd.to_datetime(
                    source,
                    errors="coerce",
                    format="mixed",
                )
            except (TypeError, ValueError):
                parsed = source.map(
                    lambda value: pd.to_datetime(
                        value,
                        errors="coerce",
                    )
                )
    return pd.Series(
        parsed,
        index=series.index,
        name=series.name,
    )
