from __future__ import annotations

import pandas as pd

PRICE_SOURCE_URL = "https://finance.yahoo.com/quote/{ticker}/history/"


def history(ticker: str, period: str = "2y", interval: str = "1d") -> pd.DataFrame:
    try:
        import yfinance as yf
    except ImportError as exc:
        raise RuntimeError("Install yfinance to use market.history") from exc
    df = yf.download(ticker, period=period, interval=interval, auto_adjust=False, progress=False)
    if df.empty:
        raise RuntimeError(f"No market data returned for {ticker}")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
    df = df.reset_index()
    date_col = "Date" if "Date" in df.columns else df.columns[0]
    df[date_col] = pd.to_datetime(df[date_col])
    return df


def price_frame(ticker: str, period: str = "10y") -> pd.DataFrame:
    """Daily prices as date / close / adj_close / volume.

    ``close`` is split-adjusted only and is what market cap uses; ``adj_close`` also
    reinvests dividends and is what return calculations use.
    """
    raw = history(ticker, period=period)
    date_col = "Date" if "Date" in raw.columns else raw.columns[0]
    frame = pd.DataFrame({
        "date": pd.to_datetime(raw[date_col]).dt.tz_localize(None).dt.normalize(),
        "close": pd.to_numeric(raw["Close"], errors="coerce"),
        "adj_close": pd.to_numeric(raw.get("Adj Close", raw["Close"]), errors="coerce"),
        "volume": pd.to_numeric(raw.get("Volume"), errors="coerce"),
    })
    return frame.dropna(subset=["close"]).sort_values("date").reset_index(drop=True)
