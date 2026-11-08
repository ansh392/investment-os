import numpy as np
import pandas as pd
import pytest

from conftest import synthetic_weekly
from investment_os.signals.altdata import (
    abnormal_event_study,
    align_asof,
    backtest_segments,
    chronological_split,
    compare_models,
    lag_test,
    leakage_checks,
    load_dataset,
    permutation_p_value,
    prepare_panel,
    run_altdata_lab,
    transform_signal,
)


def test_load_any_csv_shape(tmp_path):
    p = tmp_path / "x.csv"
    p.write_text("date,kpi,label\n2024-01-02,2,a\n2024-01-01,1,b\n2024-01-02,3,c\nbad,9,d\n")
    s = load_dataset(p)
    assert list(s) == [1.0, 3.0] and s.index.is_monotonic_increasing


def test_load_requires_explicit_column_when_ambiguous():
    with pytest.raises(ValueError):
        load_dataset(pd.DataFrame({"date": ["2024-01-01"], "a": [1], "b": [2]}))


def test_asof_respects_publication_lag():
    s = pd.Series([1.0, 2.0], index=pd.to_datetime(["2024-01-01", "2024-01-08"]))
    out = align_asof(s, pd.DatetimeIndex(["2024-01-08"]), publication_lag_days=3)
    assert out["signal"].iloc[0] == 1.0  # the Jan 8 value is unpublished until Jan 11


def test_trailing_zscore_is_causal():
    s = pd.Series(np.arange(30, dtype=float), index=pd.date_range("2024-01-01", periods=30))
    changed = s.copy()
    changed.iloc[-1] = 1e6
    a, b = transform_signal(s, "trailing_zscore", 5), transform_signal(changed, "trailing_zscore", 5)
    pd.testing.assert_series_equal(a.iloc[:-1], b.iloc[:-1])


def panel():
    s, p, _ = synthetic_weekly()
    return prepare_panel(s, p, transform="level")


def test_changing_future_prices_does_not_change_past_features():
    s, p, _ = synthetic_weekly()
    bumped = p.copy()
    bumped.iloc[-5:] *= 3
    a, b = prepare_panel(s, p, transform="level"), prepare_panel(s, bumped, transform="level")
    pd.testing.assert_series_equal(a["signal"].iloc[:-10], b["signal"].iloc[:-10])
    pd.testing.assert_series_equal(a["past_return"].iloc[:-10], b["past_return"].iloc[:-10])


def test_fwd_return_is_next_period():
    s, p, _ = synthetic_weekly(n=100)
    frame = prepare_panel(s, p, transform="level")
    returns = p.resample("W-FRI").last().pct_change()
    assert frame["fwd_return"].iloc[0] == pytest.approx(returns.shift(-1).loc[frame.index[0]])


def test_split_is_chronological_with_embargo():
    p = panel()
    sp = chronological_split(p)
    assert sp.train.index.max() < sp.validation.index.min() < sp.test.index.min()
    assert len(sp.train) + len(sp.validation) + len(sp.test) == len(p) - 2


def test_split_rejects_short_series():
    with pytest.raises(ValueError):
        chronological_split(panel().iloc[:20])


def test_model_fit_ignores_validation_and_test_outcomes():
    sp = chronological_split(panel())
    tampered = sp.test.copy()
    tampered["fwd_return"] = -tampered["fwd_return"]
    other = type(sp)(sp.train, sp.validation, tampered, sp.embargo)
    assert compare_models(sp, 0).signal_beta_train == pytest.approx(compare_models(other, 0).signal_beta_train)


def test_backtest_direction_learned_on_train_only():
    sp = chronological_split(panel())
    tampered = sp.test.copy()
    tampered["signal"] = -tampered["signal"]
    other = type(sp)(sp.train, sp.validation, tampered, sp.embargo)
    assert backtest_segments(sp, 0)[0].net_return == pytest.approx(backtest_segments(other, 0)[0].net_return)


def test_costs_reduce_returns():
    sp = chronological_split(panel())
    free, costly = backtest_segments(sp, 0, cost_bps=0)[-1], backtest_segments(sp, 0, cost_bps=50)[-1]
    assert costly.net_return < free.net_return
    assert free.max_drawdown <= 0


def test_bonferroni_never_understates_p_value():
    table = lag_test(panel(), max_lag=4)
    assert (table.p_bonferroni >= table.p_value).all()


def test_permutation_detects_real_and_rejects_noise():
    rng = np.random.default_rng(1)
    x, noise = rng.normal(size=120), rng.normal(size=120)
    assert permutation_p_value(x, 0.5 * x + rng.normal(size=120)) < 0.05
    assert permutation_p_value(noise, rng.normal(size=120)) > 0.05


def test_planted_signal_survives():
    s, p, _ = synthetic_weekly()
    report = run_altdata_lab(s, p, transform="level", max_lag=3)
    assert report.survives_out_of_sample and report.selected_lag == 0


def test_noise_is_rejected():
    s, p, _ = synthetic_weekly()
    noise = pd.Series(np.random.default_rng(99).normal(size=len(s)), index=s.index)
    assert not run_altdata_lab(noise, p, transform="level", max_lag=3).survives_out_of_sample


def test_leaky_dataset_is_flagged():
    s, p, r = synthetic_weekly()
    leaky = pd.Series(np.r_[r[1:], 0.0], index=s.index)
    report = run_altdata_lab(leaky, p, transform="level", max_lag=3)
    assert report.verdict.startswith("LEAKAGE") and not report.survives_out_of_sample


def test_future_dated_rows_fail_leakage_check():
    s, p, _ = synthetic_weekly()
    frame = prepare_panel(s, p, transform="level")
    checks = {c.name: c for c in leakage_checks(s, frame, chronological_split(frame), publication_lag_days=7, as_of=s.index[100])}
    assert not checks["No future-dated observations"].passed


def test_zero_publication_lag_is_only_a_warning():
    s, p, _ = synthetic_weekly()
    frame = prepare_panel(s, p, transform="level")
    check = next(c for c in leakage_checks(s, frame, chronological_split(frame), publication_lag_days=0) if c.name == "Publication lag declared")
    assert not check.passed and check.severity == "warn"


def test_report_exposes_out_of_sample_costs_and_drawdown():
    s, p, _ = synthetic_weekly()
    table = run_altdata_lab(s, p, transform="level", max_lag=2).performance_table()
    assert list(table.segment) == ["train", "validation", "test"]
    assert {"net_return", "gross_return", "max_drawdown", "turnover", "sharpe"} <= set(table.columns)


def test_event_study_enters_after_event_and_drops_overlaps():
    idx = pd.bdate_range("2024-01-01", periods=30)
    r = pd.Series(0.0, index=idx)
    r.iloc[5] = 0.10  # day of event must not count
    r.iloc[6] = 0.02
    out = abnormal_event_study(r, [idx[5], idx[6]], windows=(5,))
    assert out.events.iloc[0] == 1
    assert out.mean_car.iloc[0] == pytest.approx(0.02)


def test_event_study_market_adjustment():
    idx = pd.bdate_range("2024-01-01", periods=30)
    r = pd.Series(0.01, index=idx)
    assert abnormal_event_study(r, [idx[3]], benchmark=r, windows=(1,)).mean_car.iloc[0] == pytest.approx(0.0)
