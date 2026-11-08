"""Basic lead-lag, event-study and out-of-sample helpers; the full protocol is altdata."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class SignalBacktestResult:
    train_correlation: float
    test_correlation: float
    train_directional_accuracy: float
    test_directional_accuracy: float
    test_strategy_return: float
    test_buy_hold_return: float
    test_max_drawdown: float
    observations_train: int
    observations_test: int


def _safe_corr(a: pd.Series, b: pd.Series) -> float:
    joined = pd.concat([a, b], axis=1).dropna()
    if len(joined) < 3 or joined.iloc[:, 0].std() == 0 or joined.iloc[:, 1].std() == 0:
        return float("nan")
    return float(joined.iloc[:, 0].corr(joined.iloc[:, 1]))


def lead_lag_table(signal: pd.Series, target: pd.Series, max_lag: int = 12) -> pd.DataFrame:
    """Correlation of signal(t) with target(t+lag). Positive lag means signal leads target."""
    rows = []
    for lag in range(-max_lag, max_lag + 1):
        corr = _safe_corr(signal, target.shift(-lag))
        rows.append({"lag": lag, "correlation": corr, "abs_correlation": abs(corr) if corr == corr else np.nan})
    return pd.DataFrame(rows)


def event_study(
    returns: pd.Series,
    event_mask: pd.Series,
    *,
    windows: tuple[int, ...] = (1, 5, 20),
) -> pd.DataFrame:
    """Forward-return event study using simple summed returns as an approximation."""
    aligned = pd.concat([returns.rename("r"), event_mask.rename("event")], axis=1).dropna()
    events = aligned.index[aligned["event"].astype(bool)]
    rows = []
    for window in windows:
        vals = []
        for idx in events:
            loc = aligned.index.get_loc(idx)
            future = aligned["r"].iloc[loc + 1 : loc + 1 + window]
            if len(future) == window:
                vals.append(float((1 + future).prod() - 1))
        arr = np.array(vals, dtype=float)
        rows.append({
            "window": window,
            "events": int(len(arr)),
            "mean_forward_return": float(arr.mean()) if len(arr) else np.nan,
            "median_forward_return": float(np.median(arr)) if len(arr) else np.nan,
            "win_rate": float((arr > 0).mean()) if len(arr) else np.nan,
        })
    return pd.DataFrame(rows)


def out_of_sample_signal_backtest(
    signal: pd.Series,
    forward_return: pd.Series,
    *,
    train_fraction: float = 0.70,
    transaction_cost_bps: float = 5.0,
) -> SignalBacktestResult:
    """Simple, transparent OOS test.

    A z-score threshold is learned only on the train set. Test trades are long when
    z>0 and short when z<0. Returns supplied to this function must already be
    forward-looking relative to the signal timestamp to avoid accidental leakage.
    """
    df = pd.concat([signal.rename("signal"), forward_return.rename("fwd")], axis=1).dropna().copy()
    if len(df) < 30:
        raise ValueError("At least 30 aligned observations are required")
    split = max(10, min(len(df) - 10, int(len(df) * train_fraction)))
    train = df.iloc[:split].copy()
    test = df.iloc[split:].copy()
    mean, std = train["signal"].mean(), train["signal"].std(ddof=0)
    if not np.isfinite(std) or std <= 0:
        raise ValueError("Signal has zero variance in train set")

    def score(part: pd.DataFrame) -> tuple[float, float, pd.Series]:
        z = (part["signal"] - mean) / std
        position = np.sign(z)
        direction_acc = float((np.sign(part["fwd"]) == position).mean())
        turnover = position.diff().abs().fillna(position.abs())
        costs = turnover * (transaction_cost_bps / 10_000)
        strategy = position * part["fwd"] - costs
        corr = _safe_corr(part["signal"], part["fwd"])
        return corr, direction_acc, strategy

    train_corr, train_acc, _ = score(train)
    test_corr, test_acc, test_strategy = score(test)
    wealth = (1 + test_strategy).cumprod()
    dd = wealth / wealth.cummax() - 1
    return SignalBacktestResult(
        train_correlation=train_corr,
        test_correlation=test_corr,
        train_directional_accuracy=train_acc,
        test_directional_accuracy=test_acc,
        test_strategy_return=float((1 + test_strategy).prod() - 1),
        test_buy_hold_return=float((1 + test["fwd"]).prod() - 1),
        test_max_drawdown=float(dd.min()),
        observations_train=len(train),
        observations_test=len(test),
    )
