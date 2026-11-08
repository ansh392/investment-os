from investment_os.private.lbo import LBOInputs, run_lbo, solve_max_debt_for_dscr, solve_max_purchase_price


def base_inputs():
    return LBOInputs(
        purchase_price=1000,
        debt=550,
        cash=0,
        annual_cfads=(150, 160, 170, 180, 190),
        interest_rate=0.085,
        mandatory_amortization_pct=0.05,
        exit_enterprise_value=1250,
    )


def test_lbo_returns_are_positive():
    result = run_lbo(base_inputs())
    assert result["irr"] > 0
    assert result["moic"] > 1
    assert result["min_dscr"] > 1


def test_max_price_clears_target():
    x = base_inputs()
    price = solve_max_purchase_price(
        debt=x.debt,
        cash=0,
        annual_cfads=x.annual_cfads,
        interest_rate=x.interest_rate,
        mandatory_amortization_pct=x.mandatory_amortization_pct,
        exit_enterprise_value=x.exit_enterprise_value,
        target_irr=0.20,
        low=x.debt + 1,
        high=1800,
    )
    result = run_lbo(LBOInputs(price, x.debt, 0, x.annual_cfads, x.interest_rate, x.mandatory_amortization_pct, x.exit_enterprise_value))
    assert result["irr"] >= 0.1999


def test_max_debt_respects_dscr():
    x = base_inputs()
    debt = solve_max_debt_for_dscr(
        purchase_price=x.purchase_price,
        cash=0,
        annual_cfads=x.annual_cfads,
        interest_rate=x.interest_rate,
        mandatory_amortization_pct=x.mandatory_amortization_pct,
        exit_enterprise_value=x.exit_enterprise_value,
        minimum_dscr=1.40,
    )
    result = run_lbo(LBOInputs(x.purchase_price, debt, 0, x.annual_cfads, x.interest_rate, x.mandatory_amortization_pct, x.exit_enterprise_value))
    assert result["min_dscr"] >= 1.3999


def test_debt_service_shortfall_capitalizes_and_is_reported():
    x = LBOInputs(1000, 800, 0, (10.0, 10.0), 0.10, 0.05, 1200)
    result = run_lbo(x)
    assert result["total_shortfall"] > 0
    assert result["ending_debt"] > x.debt * (1 - 2 * x.mandatory_amortization_pct)


def test_exit_equity_floored_at_zero_and_total_loss_irr():
    result = run_lbo(LBOInputs(1000, 800, 0, (10.0, 10.0), 0.10, 0.05, 100))
    assert result["exit_equity"] == 0
    assert result["irr"] == -1.0


def test_max_price_search_handles_low_bound_below_debt():
    x = base_inputs()
    price = solve_max_purchase_price(
        debt=x.debt, cash=0, annual_cfads=x.annual_cfads, interest_rate=x.interest_rate,
        mandatory_amortization_pct=x.mandatory_amortization_pct, exit_enterprise_value=x.exit_enterprise_value,
        target_irr=0.20, low=1, high=1800,
    )
    result = run_lbo(LBOInputs(price, x.debt, 0, x.annual_cfads, x.interest_rate, x.mandatory_amortization_pct, x.exit_enterprise_value))
    assert abs(result["irr"] - 0.20) < 1e-4


def test_max_price_raises_when_target_unreachable():
    import pytest

    x = base_inputs()
    with pytest.raises(ValueError):
        solve_max_purchase_price(
            debt=800, cash=0, annual_cfads=(10.0, 10.0), interest_rate=x.interest_rate,
            mandatory_amortization_pct=x.mandatory_amortization_pct, exit_enterprise_value=100,
            target_irr=0.20, low=801, high=1800,
        )
