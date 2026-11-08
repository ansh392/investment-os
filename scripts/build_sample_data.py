"""Create sample_data/: local price series and clearly labeled synthetic test sets.

Synthetic files start with ``synthetic_`` and exist only to prove the Alternative Data
Lab reaches the right verdict when the answer is known in advance. Price series are
downloaded for local use and are excluded from version control.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

from investment_os.data.market import price_frame

OUT = ROOT / "sample_data"
REAL = {"UNG": "ung_etf_close", "SPY": "spy_close", "VST": "vst_close", "XLU": "xlu_close"}


def real_series() -> None:
    for ticker, stem in REAL.items():
        frame = price_frame(ticker, period="10y")[["date", "adj_close"]].rename(columns={"adj_close": "value"})
        frame.to_csv(OUT / f"{stem}.csv", index=False)


def synthetic_series(n: int = 420, seed: int = 11) -> None:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2018-01-05", periods=n, freq="W-FRI")
    informative = rng.normal(size=n)
    noise = rng.normal(size=n)
    returns = np.r_[0.0, 0.010 * informative[:-1] + rng.normal(scale=0.02, size=n - 1)]
    prices = 100 * np.cumprod(1 + returns)
    pd.DataFrame({"date": dates, "value": prices}).to_csv(OUT / "synthetic_prices.csv", index=False)
    pd.DataFrame({"date": dates, "value": informative}).to_csv(OUT / "synthetic_signal_informative.csv", index=False)
    pd.DataFrame({"date": dates, "value": noise}).to_csv(OUT / "synthetic_signal_noise.csv", index=False)
    leaky = np.r_[returns[1:], 0.0] + rng.normal(scale=0.002, size=n)
    pd.DataFrame({"date": dates, "value": leaky}).to_csv(OUT / "synthetic_signal_leaky.csv", index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthetic-only", action="store_true", help="Skip the market-price downloads")
    args = parser.parse_args()
    OUT.mkdir(exist_ok=True)
    if not args.synthetic_only:
        real_series()
    synthetic_series()
    print(f"sample_data now holds {len(list(OUT.glob('*.csv')))} datasets")


if __name__ == "__main__":
    main()
