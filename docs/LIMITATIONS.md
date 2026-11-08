# Limitations

Investment OS is a research tool and has had no external validation or audit. Nothing in it is investment advice, and "institutional-style" describes its design intent.

## Data

- **Latest restated XBRL fundamentals are not filing-vintage-aware for historical backtests.** Company fundamentals use latest-filed values by default, so a backtest on them would not reflect what was known at the time. `vintage="original"` exists in the normalizer but is not wired into signal research.
- **Standardized XBRL only.** Full filing text, footnotes, segment data and company KPIs are not parsed. Sector plug-ins add diligence questions, not numbers.
- **No silent estimation of missing data.** A value that cannot be reliably produced stays blank with a warning, so some outputs are unavailable for some companies.
- **Market-price source limitations.** Prices come from Yahoo Finance via `yfinance`, an unlicensed convenience source that can change or fail without notice. Replace it for production use. Price-bearing outputs are excluded from this repository.
- **No consensus estimates.** Variant views are measured against reverse-DCF expectations only.
- **XBRL coverage is finite.** Tag aliases cover common cases, so unusual filers may produce blanks. Debt in particular may be unavailable.
- **The evidence ledger covers recent periods:** six fiscal years and eight quarters.

## Valuation

- **DCF assumptions are user-driven.** Default WACC, terminal growth, working capital and scenario weights are placeholders. Default growth and margin are mechanical medians of recent history, and default growth is clipped at 20%.
- **Terminal value keeps final-year capex intensity,** which can undervalue companies in heavy investment phases.
- **End-of-year discounting** is used, with no mid-year convention.
- **Share counts are basic,** with no dilution from options, RSUs or convertibles.
- **Operating leases are excluded from debt,** and NCI and preferred are at book value.
- **Financial companies get no valuation model.** The DCF is refused and no alternative is built.
- **Reverse-DCF solves are partial.** Each varies one driver and holds the rest at base-case assumptions.
- **Comps are unadjusted medians** of analyst-chosen peers.

## Thesis testing and memos

- **Evidence IDs do not prove semantic support.** They show only that a claim is linked or labeled according to the ledger rule. A person must still judge whether the evidence supports the claim.
- **Claim tests are rule-based.** Thresholds such as 4.0x leverage are heuristics, and findings are not weighted, so one finding on each side produces `mixed` regardless of importance.
- **Ratings are mechanical screens,** not recommendations, and they move with placeholder inputs.
- **Catalysts and sector notes are generic templates.**
- **The earnings event study uses filing date** as a proxy for the earnings date.

## Signal research

- **The test segment is protected by procedure, not by a lockout.** The protocol scores it once per run, but an analyst can rerun the lab with different settings and informally overfit it. The parameter-stability grid also reads the test segment, as a diagnostic that never feeds selection.
- **Data revisions to user-supplied series are not modeled.** Publication lag is declared by the user, and a zero lag produces only an advisory warning.
- **The implausibility check is a threshold.** Leakage weaker than 0.60 correlation with the next-period return passes that check.
- **Backtests are single-asset and simplified.** They use flat per-turnover costs, with no borrow, financing, slippage or capacity modeling. Sharpe ratios omit a risk-free rate.
- **Lag selection takes the strongest training correlation.** Bonferroni-adjusted p-values are reported, but don't gate the choice.
- **Signal coefficients by block are a stability diagnostic,** not a refit walk-forward backtest.

## Private markets

The LBO is a simplified underwriting model. It has no fees, taxes, cash sweep, revolver, covenants, floating rates or tranching. CFADS and exit value are user inputs, with no operating build behind them.

## Verification status

| Area | Status |
|---|---|
| Automated tests | 105 tests, on Python 3.12 only; they use fixtures and need no network |
| Live SEC and price pipeline | Run manually on real tickers |
| Claude layer | One live smoke test of claim rewording; memo critique not called live, and guardrails otherwise unit-tested |
| FRED adapter | Not exercised |
| Dashboard CSV upload and scenario-table editing | Not exercised |
