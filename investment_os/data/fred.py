"""FRED macro-series adapter. Optional, and not used by the main workflow."""
from __future__ import annotations

import pandas as pd
import requests

from investment_os.config import settings

BASE_URL = "https://api.stlouisfed.org/fred/series/observations"


class FREDError(RuntimeError):
    pass


def series_observations(
    series_id: str,
    *,
    api_key: str | None = None,
    observation_start: str | None = None,
    observation_end: str | None = None,
    units: str = "lin",
    frequency: str | None = None,
) -> pd.DataFrame:
    key = api_key or settings.fred_api_key
    if not key:
        raise FREDError("FRED_API_KEY is required")
    params = {
        "series_id": series_id,
        "api_key": key,
        "file_type": "json",
        "units": units,
    }
    if observation_start:
        params["observation_start"] = observation_start
    if observation_end:
        params["observation_end"] = observation_end
    if frequency:
        params["frequency"] = frequency
    r = requests.get(BASE_URL, params=params, timeout=30)
    if r.status_code != 200:
        raise FREDError(f"FRED request failed ({r.status_code}): {r.text[:250]}")
    rows = r.json().get("observations", [])
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=["date", "value"])
    df["date"] = pd.to_datetime(df["date"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df[["date", "value"]].dropna().reset_index(drop=True)
