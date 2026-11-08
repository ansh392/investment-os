import numpy as np
import pandas as pd

from investment_os.signals.analytics import event_study, lead_lag_table, out_of_sample_signal_backtest


def test_oos_backtest_runs_and_splits():
    rng = np.random.default_rng(1)
    n = 120
    s = pd.Series(rng.normal(size=n))
    fwd = 0.01 * s + pd.Series(rng.normal(scale=0.01, size=n))
    out = out_of_sample_signal_backtest(s, fwd, transaction_cost_bps=5)
    assert out.observations_train + out.observations_test == n
    assert out.test_correlation > 0


def test_lead_lag_shape():
    s = pd.Series(range(50), dtype=float)
    t = s.shift(1)
    out = lead_lag_table(s, t, max_lag=3)
    assert len(out) == 7
    assert set(out.columns) == {"lag", "correlation", "abs_correlation"}


def test_event_study_counts_events():
    idx = pd.RangeIndex(30)
    returns = pd.Series([0.01] * 30, index=idx)
    events = pd.Series(False, index=idx)
    events.iloc[[1, 10]] = True
    out = event_study(returns, events, windows=(1, 5))
    assert int(out.loc[out["window"] == 1, "events"].iloc[0]) == 2
