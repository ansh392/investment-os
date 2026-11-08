# Demo Guide

Run these after the [Quick Start](../README.md#quick-start). Live market values change and aren't licensed for redistribution, so this guide describes the kinds of output to expect instead of publishing them.

Open the dashboard with `streamlit run dashboard/app.py`. Pages are in the left sidebar, and the **Company** selector below them picks the bundle.

## VST: a levered power producer

```bash
python scripts/research_company.py VST --peers CEG,NRG,TLN
```

The terminal prints the evidence count, scenario values, market-implied revenue CAGR, thesis status counts, rating, and any data warnings. The bundle and memo are written to `outputs/VST/`.

In the dashboard, with **VST** selected:

| Page | Do this | Expect |
|---|---|---|
| Company Research | Open **Audit trail** | Each number with its evidence ID, XBRL concept, filing and link to sec.gov |
| Reverse DCF | Move the **WACC** slider | Market-implied growth and margin, a value-per-share chart by method, and a warning when terminal value dominates |
| Thesis Lab | Read each claim | Supporting and contradictory evidence side by side, plus what would falsify it |
| IC Memo | Click a citation | The citation jumps to the ledger, and the ledger links to the filing |

The Energy & Power plug-in adds diligence questions on hedging, capacity auctions and contracted load. It never adds numbers.

## NVDA: where the placeholders matter

```bash
python scripts/research_company.py NVDA --peers AMD,AVGO
```

Select **NVDA** and compare the reverse DCF with history. Default WACC and terminal growth are placeholders, and default growth is clipped at 20%, so treat a large gap to market price as a question about the inputs. Override WACC or edit a scenario on the Reverse DCF page, then see the Thesis Lab and IC Memo update.

## SEC-reported starting point

USD millions, latest fiscal year available from SEC data on November 8, 2026.

| | VST (FY2025) | NVDA (FY2026) |
|---|---|---|
| Revenue | 17,738 | 215,938 |
| Operating income | 1,906 | 130,387 |
| Net income | 944 | 120,067 |
| Operating cash flow | 4,070 | 102,718 |
| Capex | 2,752 | 6,042 |
| Free cash flow (derived) | 1,318 | 96,676 |
| Reconstructed debt | 18,843 | 8,468 |

## Synthetic alternative-data leakage demo

Open **Alternative Data Lab** and choose each dataset. Keep the publication lag at 0.

| Dataset | Expected verdict |
|---|---|
| `SYNTHETIC: planted signal` | INCREMENTAL INFORMATION THAT SURVIVES OUT OF SAMPLE |
| `SYNTHETIC: pure noise` | NO RELIABLE INCREMENTAL INFORMATION |
| `SYNTHETIC: contains the future` | LEAKAGE SUSPECTED: results are not interpretable |

The leaky dataset shows why the checks matter. Its backtest looks extraordinary, and the failed check explains why that result cannot be used. Scroll down for the leakage table, lag test, chronological splits, reverse-causality check and parameter stability grid.

To add real ETF series on your own machine, run `python scripts/build_sample_data.py`. Those files stay local and are excluded by `.gitignore`.

## Private-markets reverse underwriting

Open **Private Markets**. All default inputs are illustrative.

1. Read IRR, MOIC, minimum DSCR, **Max price @ target IRR** and **Max debt @ min DSCR**.
2. Move **Target sponsor IRR** and watch the maximum price change.
3. Raise **Debt** or **Interest rate** until debt service exceeds CFADS. A shortfall warning appears, and the shortfall capitalizes onto the balance.

## A refusal worth seeing

```bash
python scripts/research_company.py JPM
```

The system declines to run an FCFF DCF on a bank, explains why, and issues no rating.

## Without a network connection

```bash
python scripts/build_example_memo.py --save-bundle outputs
```

This builds a fully synthetic company, adds it to the dashboard as **DEMO**, and regenerates the [sample IC memo](../examples/sample_ic_memo.md).

## Other commands

| Command | Purpose |
|---|---|
| `python scripts/research_company.py VST --offline` | Rerun analysis from a saved bundle |
| `python scripts/research_company.py VST --offline --thesis "Your hypothesis"` | Test your own thesis on a saved bundle |
| `python scripts/demo.py` | Run the mechanics on illustrative inputs |
| `python scripts/live_company_snapshot.py VST` | Print the latest standardized SEC facts |
