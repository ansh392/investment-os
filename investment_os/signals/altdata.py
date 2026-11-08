"""Alternative Data Lab: does a dataset carry incremental information out of sample?

Discipline enforced by construction:

* a signal observation is usable at target date t only if date + publication lag <= t;
* each row pairs information known at t with the return over the *following* period;
* lag, direction, scaling and coefficients are fitted on the training segment only;
* the validation segment checks the choice, and the test segment is scored once;
* embargo gaps separate segments, so forward returns cannot straddle a boundary.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

MIN_OBSERVATIONS = 60
PERIODS_PER_YEAR = {"D": 252, "W-FRI": 52, "ME": 12}
SIGNIFICANCE = 0.05
SUSPICIOUS_ABS_CORRELATION = 0.60
PERMUTATIONS = 999


def load_dataset(source: str | Path | pd.DataFrame, *, date_col: str = "date", value_col: str | None = None) -> pd.Series:
    """Load any CSV with a date column and a numeric column into a clean series."""
    df = source.copy() if isinstance(source, pd.DataFrame) else pd.read_csv(source)
    if date_col not in df.columns:
        raise ValueError(f"Missing date column {date_col!r}; columns are {list(df.columns)}")
    if value_col is None:
        numeric = [c for c in df.columns if c != date_col and pd.api.types.is_numeric_dtype(df[c])]
        if len(numeric) != 1:
            raise ValueError(f"Specify value_col; numeric columns found: {numeric}")
        value_col = numeric[0]
    if value_col not in df.columns:
        raise ValueError(f"Missing value column {value_col!r}")
    dates = pd.to_datetime(df[date_col], errors="coerce")
    values = pd.to_numeric(df[value_col], errors="coerce")
    series = pd.Series(values.to_numpy(), index=pd.DatetimeIndex(dates), name=value_col)
    series = series[series.index.notna()].dropna().sort_index()
    return series[~series.index.duplicated(keep="last")]


def transform_signal(signal: pd.Series, method: str = "pct_change", window: int = 12) -> pd.Series:
    """Causal transforms only: each value uses observations up to its own date."""
    if method == "level":
        return signal
    if method == "pct_change":
        return signal.pct_change().replace([np.inf, -np.inf], np.nan)
    if method == "diff":
        return signal.diff()
    if method == "trailing_zscore":
        rolling = signal.rolling(window, min_periods=window)
        return (signal - rolling.mean()) / rolling.std(ddof=0)
    raise ValueError(f"Unknown transform: {method}")


def align_asof(signal: pd.Series, target_dates: pd.DatetimeIndex, *, publication_lag_days: int = 0) -> pd.DataFrame:
    """For each target date, the latest signal value already published by that date."""
    left = pd.DataFrame({"date": target_dates}).sort_values("date")
    right = pd.DataFrame({
        "available_at": signal.index + pd.Timedelta(days=publication_lag_days),
        "observation_date": signal.index,
        "signal": signal.to_numpy(),
    }).sort_values("available_at")
    merged = pd.merge_asof(left, right, left_on="date", right_on="available_at", direction="backward")
    return merged.set_index("date")


def prepare_panel(
    signal: pd.Series,
    prices: pd.Series,
    *,
    freq: str = "W-FRI",
    publication_lag_days: int = 0,
    transform: str = "pct_change",
    benchmark: pd.Series | None = None,
    controls: dict[str, pd.Series] | None = None,
) -> pd.DataFrame:
    """Build the modeling table: known-at-t features against next-period return."""
    px = prices.sort_index().resample(freq).last().dropna()
    returns = px.pct_change()
    if benchmark is not None:
        returns = returns - benchmark.sort_index().resample(freq).last().pct_change().reindex(returns.index)
    transformed = transform_signal(signal.sort_index(), transform).dropna()
    panel = align_asof(transformed, px.index, publication_lag_days=publication_lag_days)
    panel["past_return"] = returns
    panel["fwd_return"] = returns.shift(-1)
    for name, series in (controls or {}).items():
        panel[f"control_{name}"] = align_asof(
            transform_signal(series.sort_index(), transform).dropna(), px.index, publication_lag_days=publication_lag_days,
        )["signal"]
    return panel.dropna()


@dataclass(frozen=True)
class Splits:
    train: pd.DataFrame
    validation: pd.DataFrame
    test: pd.DataFrame
    embargo: int

    def as_rows(self) -> pd.DataFrame:
        return pd.DataFrame([
            {"segment": n, "observations": len(p), "start": p.index.min().date(), "end": p.index.max().date()}
            for n, p in (("train", self.train), ("validation", self.validation), ("test", self.test))
        ])


def chronological_split(panel: pd.DataFrame, *, train: float = 0.6, validation: float = 0.2, embargo: int = 1) -> Splits:
    if len(panel) < MIN_OBSERVATIONS:
        raise ValueError(f"At least {MIN_OBSERVATIONS} aligned observations are required, got {len(panel)}")
    if not (0 < train < 1 and 0 < validation < 1 and train + validation < 1):
        raise ValueError("train and validation fractions must leave room for a test segment")
    n = len(panel)
    a, b = int(n * train), int(n * (train + validation))
    return Splits(panel.iloc[:a], panel.iloc[a + embargo:b], panel.iloc[b + embargo:], embargo)


def _corr(a: pd.Series | np.ndarray, b: pd.Series | np.ndarray) -> float:
    x, y = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    if len(x) < 3 or x.std() == 0 or y.std() == 0:
        return float("nan")
    return float(np.corrcoef(x, y)[0, 1])


def _p_from_corr(r: float, n: int) -> float:
    """Two-sided normal-approximation p-value for a correlation."""
    if not np.isfinite(r) or n < 4 or abs(r) >= 1:
        return float("nan")
    t = r * math.sqrt((n - 2) / (1 - r * r))
    return float(math.erfc(abs(t) / math.sqrt(2)))


def lag_test(panel: pd.DataFrame, *, max_lag: int = 8) -> pd.DataFrame:
    """Correlation of signal(t - lag) with the next-period return, on supplied data.

    Bonferroni-adjusted p-values account for searching over several lags.
    """
    rows = []
    trials = max_lag + 1
    for lag in range(trials):
        joined = pd.concat([panel["signal"].shift(lag).rename("s"), panel["fwd_return"]], axis=1).dropna()
        r = _corr(joined["s"], joined["fwd_return"])
        p = _p_from_corr(r, len(joined))
        rows.append({"lag": lag, "correlation": r, "n": len(joined), "p_value": p, "p_bonferroni": min(1.0, p * trials) if p == p else p})
    return pd.DataFrame(rows)


def rolling_correlation(panel: pd.DataFrame, window: int = 26) -> pd.Series:
    return panel["signal"].rolling(window).corr(panel["fwd_return"]).dropna().rename("rolling_correlation")


def reverse_causality(panel: pd.DataFrame, *, max_lag: int = 4) -> pd.DataFrame:
    """Does past return predict the signal? If so, the signal may just follow price."""
    rows = []
    for lag in range(1, max_lag + 1):
        joined = pd.concat([panel["past_return"].shift(lag - 1).rename("r"), panel["signal"]], axis=1).dropna()
        r = _corr(joined["r"], joined["signal"])
        rows.append({"return_leads_by": lag, "correlation": r, "p_value": _p_from_corr(r, len(joined))})
    return pd.DataFrame(rows)


def _features(frame: pd.DataFrame, lag: int) -> pd.DataFrame:
    return frame.assign(signal=frame["signal"].shift(lag)).dropna()


def _fit(y: np.ndarray, x: np.ndarray) -> np.ndarray:
    return np.linalg.lstsq(np.column_stack([np.ones(len(x)), x]), y, rcond=None)[0]


def _predict(beta: np.ndarray, x: np.ndarray) -> np.ndarray:
    return np.column_stack([np.ones(len(x)), x]) @ beta


def _oos_r2(actual: np.ndarray, pred: np.ndarray, train_mean: float) -> float:
    """Campbell-Thompson R2: skill relative to forecasting the training-mean return."""
    denominator = float(((actual - train_mean) ** 2).sum())
    return 1 - float(((actual - pred) ** 2).sum()) / denominator if denominator else float("nan")


@dataclass(frozen=True)
class ModelComparison:
    table: pd.DataFrame
    signal_beta_train: float
    signal_beta_validation: float


def compare_models(splits: Splits, lag: int) -> ModelComparison:
    """Baseline (past return and controls) against baseline + signal.

    Features are standardized with training statistics only.
    """
    train, validation, test = (_features(p, lag) for p in (splits.train, splits.validation, splits.test))
    base_cols = ["past_return", *[c for c in train.columns if c.startswith("control_")]]
    full_cols = [*base_cols, "signal"]
    mean, std = train[full_cols].mean(), train[full_cols].std(ddof=0).replace(0, 1.0)

    def x(frame: pd.DataFrame, cols: list[str]) -> np.ndarray:
        return ((frame[cols] - mean[cols]) / std[cols]).to_numpy()

    y_train = train["fwd_return"].to_numpy()
    train_mean = float(y_train.mean())
    beta_base, beta_full = _fit(y_train, x(train, base_cols)), _fit(y_train, x(train, full_cols))
    rows = []
    for name, frame in (("train", train), ("validation", validation), ("test", test)):
        y = frame["fwd_return"].to_numpy()
        r2_base = _oos_r2(y, _predict(beta_base, x(frame, base_cols)), train_mean)
        r2_full = _oos_r2(y, _predict(beta_full, x(frame, full_cols)), train_mean)
        rows.append({"segment": name, "r2_baseline": r2_base, "r2_with_signal": r2_full, "incremental_r2": r2_full - r2_base})
    val_beta = _fit(validation["fwd_return"].to_numpy(), x(validation, full_cols))
    return ModelComparison(pd.DataFrame(rows), float(beta_full[-1]), float(val_beta[-1]))


def permutation_p_value(signal: np.ndarray, target: np.ndarray, *, n: int = PERMUTATIONS, seed: int = 7) -> float:
    """Circular-shift test: keeps the signal's autocorrelation, breaks its timing."""
    observed = abs(_corr(signal, target))
    if not np.isfinite(observed) or len(signal) < 10:
        return float("nan")
    rng = np.random.default_rng(seed)
    shifts = rng.integers(1, len(signal), size=n)
    exceed = sum(abs(_corr(np.roll(signal, int(s)), target)) >= observed for s in shifts)
    return (exceed + 1) / (n + 1)


@dataclass(frozen=True)
class SegmentPerformance:
    segment: str
    observations: int
    net_return: float
    gross_return: float
    buy_hold_return: float
    sharpe: float
    max_drawdown: float
    hit_rate: float
    turnover: float
    equity: pd.Series = field(repr=False)


def _positions(z: pd.Series, direction: float, threshold: float) -> pd.Series:
    return (np.sign(z) * direction).where(z.abs() >= threshold, 0.0).astype(float)


def backtest_segments(
    splits: Splits, lag: int, *, threshold: float = 0.0, cost_bps: float = 10.0, periods_per_year: int = 52,
) -> list[SegmentPerformance]:
    """Long/short on the standardized signal, with direction learned on train only."""
    train = _features(splits.train, lag)
    mean, std = train["signal"].mean(), train["signal"].std(ddof=0)
    if not np.isfinite(std) or std <= 0:
        raise ValueError("Signal has zero variance in the training segment")
    direction = float(np.sign(_corr(train["signal"], train["fwd_return"]))) or 1.0
    out = []
    for name, frame in (("train", train), ("validation", _features(splits.validation, lag)), ("test", _features(splits.test, lag))):
        position = _positions((frame["signal"] - mean) / std, direction, threshold)
        turnover = position.diff().abs().fillna(position.abs())
        costs = turnover * cost_bps / 10_000
        gross = position * frame["fwd_return"]
        net = gross - costs
        equity = (1 + net).cumprod()
        vol = float(net.std(ddof=0))
        active = position != 0
        out.append(SegmentPerformance(
            segment=name, observations=len(frame), net_return=float(equity.iloc[-1] - 1), gross_return=float((1 + gross).prod() - 1),
            buy_hold_return=float((1 + frame["fwd_return"]).prod() - 1),
            sharpe=float(net.mean() / vol * math.sqrt(periods_per_year)) if vol > 0 else float("nan"),
            max_drawdown=float((equity / equity.cummax() - 1).min()),
            hit_rate=float((np.sign(frame["fwd_return"][active]) == position[active]).mean()) if active.any() else float("nan"),
            turnover=float(turnover.mean()), equity=equity,
        ))
    return out


def parameter_stability(
    splits: Splits, *, max_lag: int = 4, thresholds: tuple[float, ...] = (0.0, 0.5, 1.0), cost_bps: float = 10.0, periods_per_year: int = 52,
) -> pd.DataFrame:
    """Out-of-sample Sharpe for each parameter pair.

    Diagnostic only: it reveals whether a result depends on one lucky setting and is
    never used to choose parameters.
    """
    rows = []
    for lag in range(max_lag + 1):
        for threshold in thresholds:
            perf = backtest_segments(splits, lag, threshold=threshold, cost_bps=cost_bps, periods_per_year=periods_per_year)[-1]
            rows.append({"lag": lag, "threshold": threshold, "test_sharpe": perf.sharpe, "test_net_return": perf.net_return})
    return pd.DataFrame(rows)


def walk_forward_betas(panel: pd.DataFrame, lag: int, *, folds: int = 5) -> pd.DataFrame:
    """Signal coefficient in sequential blocks; sign flips indicate instability."""
    frame = _features(panel, lag)
    rows = []
    for i, block in enumerate(np.array_split(np.arange(len(frame)), folds), 1):
        part = frame.iloc[block]
        std = part["signal"].std(ddof=0) or 1.0
        rows.append({
            "fold": i, "start": part.index.min().date(), "end": part.index.max().date(),
            "standardized_beta": float(_fit(part["fwd_return"].to_numpy(), (part[["signal"]].to_numpy() - part["signal"].mean()) / std)[1]),
        })
    return pd.DataFrame(rows)


@dataclass(frozen=True)
class LeakageCheck:
    name: str
    passed: bool
    detail: str
    severity: str = "fail"  # "fail" blocks a positive verdict; "warn" is advisory


def leakage_checks(
    signal: pd.Series, panel: pd.DataFrame, splits: Splits, *, publication_lag_days: int, as_of: pd.Timestamp | None = None,
) -> list[LeakageCheck]:
    checks: list[LeakageCheck] = []
    available = panel["observation_date"] + pd.Timedelta(days=publication_lag_days)
    late = int((available > panel.index.to_series()).sum())
    checks.append(LeakageCheck("Signal known before target date", late == 0, f"{late} row(s) use data not yet published at the target date."))
    now = as_of or pd.Timestamp.now().normalize()
    future = int((signal.index > now).sum())
    checks.append(LeakageCheck("No future-dated observations", future == 0, f"{future} observation(s) dated after {now.date()}."))
    checks.append(LeakageCheck("Unique, ordered timestamps", panel.index.is_monotonic_increasing and panel.index.is_unique, "The panel index must be strictly increasing."))
    ordered = splits.train.index.max() < splits.validation.index.min() and splits.validation.index.max() < splits.test.index.min()
    checks.append(LeakageCheck("Segments chronological with embargo", ordered and splits.embargo >= 1, f"Embargo of {splits.embargo} period(s) between segments."))
    corr_fwd = _corr(panel["signal"], panel["fwd_return"])
    checks.append(LeakageCheck(
        "Implausibly strong signal", not (np.isfinite(corr_fwd) and abs(corr_fwd) >= SUSPICIOUS_ABS_CORRELATION),
        f"Correlation with next-period return is {corr_fwd:.2f}; above {SUSPICIOUS_ABS_CORRELATION:.2f} usually means the dataset contains the outcome.",
    ))
    checks.append(LeakageCheck(
        "Publication lag declared", publication_lag_days > 0,
        f"Publication lag is {publication_lag_days} day(s); zero assumes data is usable the moment it is dated, and revisions are not modeled.",
        severity="warn",
    ))
    return checks


@dataclass(frozen=True)
class AltDataReport:
    selected_lag: int
    splits: Splits
    lag_table: pd.DataFrame
    validation_lag_table: pd.DataFrame
    reverse: pd.DataFrame
    rolling: pd.Series
    models: ModelComparison
    performance: list[SegmentPerformance]
    stability: pd.DataFrame
    betas: pd.DataFrame
    leakage: list[LeakageCheck]
    test_permutation_p: float
    verdict: str
    has_incremental_information: bool
    survives_out_of_sample: bool
    reasons: list[str]

    def performance_table(self) -> pd.DataFrame:
        return pd.DataFrame([{k: v for k, v in p.__dict__.items() if k != "equity"} for p in self.performance])


def run_altdata_lab(
    signal: pd.Series,
    prices: pd.Series,
    *,
    freq: str = "W-FRI",
    publication_lag_days: int = 0,
    transform: str = "pct_change",
    benchmark: pd.Series | None = None,
    controls: dict[str, pd.Series] | None = None,
    max_lag: int = 8,
    cost_bps: float = 10.0,
    threshold: float = 0.0,
    as_of: pd.Timestamp | None = None,
) -> AltDataReport:
    """Run the whole protocol and answer the incremental-information question."""
    panel = prepare_panel(
        signal, prices, freq=freq, publication_lag_days=publication_lag_days, transform=transform, benchmark=benchmark, controls=controls,
    )
    splits = chronological_split(panel)
    ppy = PERIODS_PER_YEAR.get(freq, 52)
    train_lags = lag_test(splits.train, max_lag=max_lag)
    lag = int(train_lags.loc[train_lags["correlation"].abs().idxmax(), "lag"])
    models = compare_models(splits, lag)
    performance = backtest_segments(splits, lag, threshold=threshold, cost_bps=cost_bps, periods_per_year=ppy)
    test_frame = _features(splits.test, lag)
    test_p = permutation_p_value(test_frame["signal"].to_numpy(), test_frame["fwd_return"].to_numpy())
    checks = leakage_checks(signal, panel, splits, publication_lag_days=publication_lag_days, as_of=as_of)

    table = models.table.set_index("segment")
    val_gain, test_gain = float(table.loc["validation", "incremental_r2"]), float(table.loc["test", "incremental_r2"])
    same_sign = models.signal_beta_train * models.signal_beta_validation > 0
    test_perf = performance[-1]
    leak_ok = all(c.passed for c in checks if c.severity == "fail")
    has_info = val_gain > 0 and same_sign
    survives = has_info and test_gain > 0 and test_p < SIGNIFICANCE and test_perf.net_return > 0 and test_perf.sharpe > 0

    reasons = [
        f"Lag {lag} selected on the training segment only ({len(train_lags)} lags searched).",
        f"Validation incremental R2 is {val_gain:+.4f}, and the signal coefficient {'keeps' if same_sign else 'flips'} sign from train to validation.",
        f"Test incremental R2 is {test_gain:+.4f}, with a circular-shift permutation p-value of {test_p:.3f}.",
        f"Test strategy after {cost_bps:.0f} bps costs returned {test_perf.net_return:+.1%} (buy-and-hold {test_perf.buy_hold_return:+.1%}), Sharpe {test_perf.sharpe:.2f}, max drawdown {test_perf.max_drawdown:.1%}.",
    ]
    if not leak_ok:
        verdict = "LEAKAGE SUSPECTED: results are not interpretable"
        reasons.extend(f"Failed check: {c.name}. {c.detail}" for c in checks if not c.passed and c.severity == "fail")
        has_info = survives = False
    elif survives:
        verdict = "INCREMENTAL INFORMATION THAT SURVIVES OUT OF SAMPLE"
    elif has_info:
        verdict = "INCREMENTAL IN VALIDATION, BUT DOES NOT SURVIVE THE TEST SEGMENT"
    else:
        verdict = "NO RELIABLE INCREMENTAL INFORMATION"

    return AltDataReport(
        selected_lag=lag, splits=splits, lag_table=train_lags, validation_lag_table=lag_test(splits.validation, max_lag=max_lag),
        reverse=reverse_causality(panel), rolling=rolling_correlation(panel), models=models, performance=performance,
        stability=parameter_stability(splits, cost_bps=cost_bps, periods_per_year=ppy), betas=walk_forward_betas(panel, lag),
        leakage=checks, test_permutation_p=test_p, verdict=verdict, has_incremental_information=has_info,
        survives_out_of_sample=survives, reasons=reasons,
    )


def abnormal_event_study(
    returns: pd.Series, event_dates: list[Any], *, benchmark: pd.Series | None = None, windows: tuple[int, ...] = (1, 5, 20),
) -> pd.DataFrame:
    """Compounded post-event return, market-adjusted when a benchmark is supplied.

    Entry is the first session strictly after the event date. Events overlapping the
    previous counted event's window are dropped to keep observations independent.
    """
    r = returns.sort_index().dropna()
    if benchmark is not None:
        r = (r - benchmark.reindex(r.index)).dropna()
    locations = sorted({int(r.index.searchsorted(pd.Timestamp(d), side="right")) for d in event_dates})
    rows = []
    for window in windows:
        values: list[float] = []
        next_free = 0
        for loc in locations:
            if loc < next_free or loc + window > len(r):
                continue
            values.append(float((1 + r.iloc[loc:loc + window]).prod() - 1))
            next_free = loc + window
        arr = np.array(values, dtype=float)
        std = float(arr.std(ddof=1)) if len(arr) > 1 else float("nan")
        rows.append({
            "window": window, "events": len(arr), "mean_car": float(arr.mean()) if len(arr) else float("nan"),
            "t_stat": float(arr.mean() / (std / math.sqrt(len(arr)))) if len(arr) > 1 and std > 0 else float("nan"),
            "win_rate": float((arr > 0).mean()) if len(arr) else float("nan"),
        })
    return pd.DataFrame(rows)
