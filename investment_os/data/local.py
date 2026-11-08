from __future__ import annotations

from pathlib import Path

import pandas as pd


def load_time_series_csv(path: str | Path, *, date_col: str = "date") -> pd.DataFrame:
    df = pd.read_csv(path)
    if date_col not in df.columns:
        raise ValueError(f"Missing date column {date_col!r}")
    df[date_col] = pd.to_datetime(df[date_col])
    return df.sort_values(date_col).drop_duplicates(date_col).reset_index(drop=True)
