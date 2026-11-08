import math

from investment_os.models.valuation import DCFInputs, dcf_valuation, fcff_forecast, reverse_dcf_implied_growth


def test_dcf_positive():
    out = dcf_valuation(DCFInputs((100, 110, 121), 0.10, 0.03, 50, 10))
    assert out["enterprise_value"] > 0
    assert out["implied_price"] > 0


def test_reverse_dcf_recovers_growth():
    growth = 0.12
    fcff = fcff_forecast(100, growth, 5)
    ev = dcf_valuation(DCFInputs(fcff, 0.10, 0.03))["enterprise_value"]
    recovered = reverse_dcf_implied_growth(
        market_enterprise_value=ev,
        starting_fcff=100,
        years=5,
        wacc=0.10,
        terminal_growth=0.03,
    )
    assert math.isclose(recovered, growth, rel_tol=1e-6, abs_tol=1e-6)


def test_dcf_rejects_wacc_below_terminal_growth():
    try:
        dcf_valuation(DCFInputs((100, 110), 0.02, 0.03))
    except ValueError:
        return
    raise AssertionError("Expected ValueError")
