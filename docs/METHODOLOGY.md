# Methodology

How each number is produced, and which rules constrain it. Known weaknesses are in [LIMITATIONS.md](LIMITATIONS.md).

## SEC normalization

SEC Company Facts is not directly usable, so `investment_os/data/normalize.py` applies these rules:

| Problem | Rule |
|---|---|
| `fy`/`fp` describe the filing, not the fact | Periods are identified from start and end dates |
| One period appears in many filings | Latest-filed wins; values that differ by more than 0.5% across filings are flagged as restated |
| Companies change XBRL tags | Aliases are resolved per period |
| 10-Q cash flows are year-to-date | Discrete quarters are differenced |
| Q4 is rarely tagged | Q4 = fiscal year less nine months, recorded as `derived` |
| Debt has no single reliable tag | Rebuilt from balance-sheet components; left blank with a warning if it cannot be trusted |

Debt excludes operating leases and requires an explicit current portion when built from noncurrent debt, because a noncurrent line alone could understate it. Quarterly data is checked against the fiscal year within a 1% tolerance, and exceptions produce warnings.

## DCF

The operating bridge is built per scenario in `investment_os/models/workspace.py`:

```
Revenue → EBIT → taxes → NOPAT → + D&A → − capex → − ΔNWC → FCFF
```

Enterprise value is the discounted forecast FCFF plus a Gordon-growth terminal value on final-year FCFF, using end-of-year discounting. Equity value subtracts net claims (debt + NCI + preferred − cash) and is divided by basic shares. Operating losses receive no tax shield.

### Default assumptions

Defaults are mechanical starting points recorded as `assumed`, each with its rule. They are not forecasts.

| Input | Default rule |
|---|---|
| Revenue growth | Median annual growth over the last three fiscal years, clipped to −5%/+20%, fading linearly to terminal growth |
| EBIT margin, D&A, capex | Median share of revenue, last three fiscal years |
| Tax rate | Median effective rate clipped to 0–35%, or 21% if unavailable |
| Working capital | Placeholder: 10% of incremental revenue |
| WACC | Placeholder: 9%, with no company-specific build-up |
| Terminal growth | Placeholder: 2.5% |
| Bear / base / bull | Mechanical shifts in growth and margin, weighted 25% / 50% / 25% |

A warning appears when terminal value exceeds 75% of enterprise value. Valuation is refused for financial companies (SIC 6000–6799) and whenever shares, reliable net debt, or the required operating history are unavailable.

## Reverse DCF

Reverse DCF asks what must be true for the model to reconcile to market enterprise value. Three separate bisection solves are reported:

| Solve | Held constant |
|---|---|
| Revenue CAGR | Base-case margins and reinvestment |
| EBIT margin | Base-case growth and reinvestment |
| FCFF CAGR | WACC and terminal growth, from base-period FCFF |

The operating solves still work when current free cash flow is negative. The FCFF solve is skipped with an explanation in that case. A solve with no answer in its search range reports why instead of returning a number.

## Comparable companies

For each peer, the pipeline computes EV/Revenue, EV/EBITDA, P/E and FCF yield from TTM SEC data and the current market value. EBITDA is TTM operating income plus D&A. Implied prices use the peer median, and only peers with a source URL count. Negative denominators are excluded. EV-based values subtract the target's net claims before dividing by shares.

## Thesis testing

`investment_os/research/thesis_lab.py` is deterministic. Growth, valuation and balance sheet are always tested, and margin, cash conversion or reinvestment are added when the hypothesis mentions them. Each template computes findings from filings data and cites their evidence IDs.

| Status | Meaning |
|---|---|
| Supported | Only supporting findings |
| Contradicted | Only contradicting findings |
| Mixed | Both |
| Inconclusive | No testable finding |

Each claim carries a measurable falsification condition, tied to the market-implied figure where one exists. Analyst-added claims receive no automated test and are flagged as needing sourced evidence.

The rating is a mechanical screen: probability-weighted DCF versus price with ±20% thresholds, moved to WATCH when DCF and peer multiples materially disagree in direction.

## Alternative-data protocol

`investment_os/signals/altdata.py` answers one question: does this dataset contain incremental information that survives out of sample?

### Point-in-time rules

- A signal value is usable at target date *t* only if its date plus the declared publication lag is on or before *t*.
- Each modeling row pairs information known at *t* with the return over the following period.
- Signal transforms are causal, using only observations up to their own date.

### Validation design

| Stage | Rule |
|---|---|
| Split | Chronological 60% train, 20% validation, 20% test, requiring at least 60 aligned observations |
| Embargo | One period between adjacent segments |
| Fit on train only | Lag, direction, standardization and coefficients |
| Baseline | Past return plus any controls |
| Incremental value | Out-of-sample R² with the signal less R² of the baseline, both against the training-mean forecast (Campbell-Thompson) |
| Significance | Circular-shift permutation test with 999 shifts, which preserves the signal's autocorrelation and breaks its timing |
| Strategy | Long/short on the standardized signal, net of per-turnover costs |

The verdict **survives out of sample** requires positive incremental R² in validation, a train-to-validation coefficient with the same sign, positive incremental R² in test, a test permutation p-value below 0.05, and positive net return and Sharpe in test.

### Leakage controls

Any failed check other than the advisory one forces the verdict `LEAKAGE SUSPECTED` and suppresses the positive result.

| Check | Fails when |
|---|---|
| Signal known before target date | Any row uses data not yet published |
| No future-dated observations | Any observation is dated after today |
| Unique, ordered timestamps | The panel index is not strictly increasing |
| Segments chronological with embargo | Segments overlap or lack an embargo |
| Implausibly strong signal | Absolute correlation with next-period return is at least 0.60 |
| Publication lag declared | Advisory only: the lag is zero |

### Diagnostics

Reported, but never used for selection or the verdict: Bonferroni-adjusted lag p-values, a reverse-causality check of whether returns lead the signal, rolling correlation, signal coefficients across sequential blocks, and test-segment Sharpe across a lag and threshold grid.

## LBO and credit underwriting

`investment_os/private/lbo.py` takes purchase price, debt, CFADS, interest, mandatory amortization and exit enterprise value.

- **Debt service** is interest on the opening balance plus scheduled amortization. **DSCR** is CFADS divided by debt service.
- **Sponsor distributions** are CFADS above debt service.
- **Shortfalls** capitalize onto the debt balance and are reported.
- **Exit equity** is exit EV less ending debt, floored at zero. A total loss returns −100% IRR.
- **Reverse underwriting** bisects for the highest price that clears a target IRR, and raises an error if no price does.
- **Debt sizing** bisects for the largest debt that holds a minimum DSCR.

## Evidence ledger

`investment_os/core/evidence.py` enforces sourcing at insertion.

| Type | Rule |
|---|---|
| `reported` | Requires an http(s) source URL and a retrieval timestamp |
| `derived` | Requires a source, or inputs that already exist in the ledger |
| `assumed`, `judgment` | May be source-free, but are always labeled |

IDs show their type: `R.revenue.FY2025`, `D.fcf.FY2025`, `A.wacc`, and `M.price` for the market price. The memo validator requires every sentence and table row to cite known evidence IDs or carry a `[Judgment]` label, and export is refused otherwise. The optional Claude layer is held to the same ledger: a rewording that adds a number or unknown citation is rejected, and a critique citing evidence outside the ledger raises an error.
