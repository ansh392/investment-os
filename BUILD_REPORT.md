# Investment OS v1.0 Build Report

## Result

All eight priority features in the brief are implemented and run on live SEC and market data. The test suite grew from 12 to **105 tests, all passing**, on Python 3.12.

Live end-to-end runs: VST, NVDA, WMT (each with real peers) and JPM. Every generated memo passed citation validation. A sampled evidence link to Vistra's FY2025 10-K on sec.gov returned HTTP 200.

## What was implemented

| Brief item | Delivered |
|---|---|
| 1. Research pipeline | `scripts/research_company.py`: ticker → CIK → filings → history → prices → market cap/EV → bundle in `outputs/<TICKER>/`, with `--offline` and `--peers` |
| 2. Filing / evidence layer | SEC submissions, links to each filing's primary document, full evidence schema, enforcement at insertion |
| 3. Normalizer | Annual and quarterly history, per-period tag resolution, restatement flags, YTD differencing, derived Q4, conservative debt reconstruction, reconciliation warnings |
| 4. Valuation workspace | History, editable bull/base/bear, operating bridge to FCFF and equity, reverse DCF (FCFF, revenue, margin), sensitivity, real-peer comps |
| 5. Thesis Lab | 3–7 claims, required/supporting/contradictory evidence, what is priced in, catalysts, falsification tests, open diligence; deterministic without an LLM |
| 6. Alternative Data Lab | Any date/value CSV, frequency alignment, publication lag, train-only lag tests, rolling correlation, event studies, train/validation/test with embargo, univariate and multivariate models, leakage checks, cost-aware backtest, parameter stability, explicit verdict |
| 7. IC memo | Markdown and HTML with all required sections; export is refused if any claim is uncited |
| 8. Dashboard | Company Research, Reverse DCF, Thesis Lab, Alternative Data Lab, Private Markets, IC Memo |

Nice-to-haves done: sector plug-ins (energy, semis, consumer), earnings event study, HTML export. Not done: FRED macro panel, estimate-revision import, portfolio risk page.

## Defects fixed in v0.2

- **LBO shortfalls:** unfunded debt service disappeared while principal still fell, overstating returns. It now capitalizes and is reported.
- **Exit equity:** could go below zero. It is now floored, and a total loss returns -100% IRR instead of NaN.
- **`solve_max_purchase_price`:** searched the wrong way when equity was non-positive, and returned an infeasible price as if valid. It now raises when no price works.
- **`latest_standardized`:** a discontinued tag could beat the current one, and partial-year values could pass as latest. Both fixed.
- **SEC evidence:** cited a bare domain. It now links to the filing.

Stricter by design: reported evidence now requires a URL and a retrieval timestamp, so any code passing free-text sources for `reported` items will raise.

## Testing

| Area | Tests |
|---|---|
| SEC normalization fixtures | 19 |
| Valuation, pipeline, evidence, thesis, memo citations, LLM guardrails | 43 + 3 (original valuation) + 3 (original evidence/thesis) |
| Alternative data, leakage, train/test behavior | 21 + 3 (original signals) |
| LBO solvers | 7 |
| Dashboard pages (headless render, parametrized over 6 pages) | 6 cases |

Known-answer check on the Alternative Data Lab at zero publication lag:

| Dataset | Verdict |
|---|---|
| Synthetic planted signal | Survives out of sample |
| Synthetic noise | No reliable incremental information |
| Synthetic with future data | Leakage suspected |

## Not verified

- The **Claude layer was not called live**, because no API key was configured. Its guardrails are unit-tested only.
- The **FRED adapter** is unchanged and was not exercised.
- **Python 3.11** was not run. A linter syntax check targets it, and it caught and fixed one 3.12-only construct.
- In the dashboard, the **CSV upload path** and **live scenario-table edits** were not exercised. All six pages were reviewed in a browser with default inputs.

## Remaining limitations

- **Default DCF inputs are placeholders.** The 9% WACC and 2.5% terminal growth are not company-specific, and terminal cash flow keeps current capex intensity, which tends to undervalue companies in heavy investment phases. Treat default outputs as a starting point.
- **Ratings are mechanical** and change with placeholder inputs. Financial companies receive no rating.
- **No consensus estimates**, so variant perception is measured against reverse-DCF expectations only.
- **XBRL only:** no segment, footnote or KPI parsing. Sector plug-ins add questions, not numbers.
- **Share count is basic**, with no dilution. Operating leases are excluded from debt, and NCI and preferred are at book value.
- **Financials get no valuation model**; the DCF is refused and no alternative is built.
- **Fundamental history uses latest-restated values by default.** `vintage="original"` exists but is not wired into signal research, so fundamentals-based backtests would need it.
- **Event study uses filing date** as a proxy for earnings date.
- **Prices are from an unlicensed source.** Price-bearing outputs and series are excluded from version control. Replace the source for production use.

## Strongest demo workflow

1. `python scripts/research_company.py VST --peers CEG,NRG,TLN`, then `streamlit run dashboard/app.py`.
2. **Company Research → Audit trail:** trace a number to its XBRL tag and filing.
3. **Reverse DCF:** read the market-implied revenue CAGR and EBIT margin, compare the DCF with peer multiples, then change WACC and watch it flow through.
4. **Thesis Lab:** review the historical growth rate against what the market implies, shown with contradictory evidence.
5. **Alternative Data Lab:** run the leaky synthetic dataset and watch it get caught.
6. **IC Memo:** click a citation through to the ledger and on to the SEC filing.
7. Close with `python scripts/research_company.py JPM`, where the system declines to value a bank instead of producing a number.
