# Investment Committee Memo: Synthetic Demo Co (DEMO)

> **Synthetic example. Every company, filing, price and peer below is invented.**
> Synthetic Demo Co does not exist and nothing here describes any real security. The analysis
> is pipeline output, run on simulated filings by `scripts/build_example_memo.py`. Only this
> notice, the `synthetic-source` link labels and the collapsed ledger were added afterward.
> Not investment advice.

> Data retrieved 2026-11-08T21:13:51Z. Sector module: General. CIK 1.
> Automated research output for analysis of a process, not investment advice. Default assumptions are mechanical placeholders until an analyst overrides them.

## Recommendation

**AVOID / SHORT CANDIDATE, SUBJECT TO DILIGENCE** [Judgment]

Rule-based rating: probability-weighted DCF versus price is -24% with thresholds of +20% and -20%, and 2 thesis claim(s) contradicted. [Judgment]

## Thesis

Hypothesis under test: The market underestimates revenue growth and the conversion of earnings into free cash flow as new capacity comes online. [Judgment]

Claim status across 6 tests: 1 supported, 3 mixed, 2 contradicted, 0 inconclusive. [Judgment]

### C1. Revenue growth can meet or exceed what the market is discounting.

Status: **mixed**. [Judgment]

- Supporting: Latest quarter revenue changed +13.0% year over year. [D.revenue.2025Q4] [D.revenue.2024Q4]
- Contradicting: Revenue compounded at 14.7% over 3 years, against a market-implied 17.5%. [R.revenue.FY2022] [R.revenue.FY2025] [D.implied_revenue_cagr]

### C2. The current price offers a margin of safety against independent value.

Status: **contradicted**. [Judgment]

- Contradicting: Probability-weighted DCF of $78.70 is -24% versus the $104.00 share price. [D.value.weighted] [M.price]
- Contradicting: Peer-median EV/EBITDA implies $87.11, -16% versus the share price. [D.comps.ev_ebitda] [M.price]

### C3. The balance sheet can absorb the downside case.

Status: **mixed**. [Judgment]

- Supporting: Net debt is 1.3x TTM EBITDA. [D.debt.2025Q4] [R.cash.2025Q4] [D.ttm.operating_income] [D.ttm.dna]
- Contradicting: Reconstructed debt changed +31% over the period. [D.debt.FY2022] [D.debt.FY2025]

### C4. Operating margins are durable at or above the level the market is discounting.

Status: **contradicted**. [Judgment]

- Contradicting: EBIT margin moved from 19.0% to 18.0% over the period. [R.operating_income.FY2022] [R.operating_income.FY2025] [R.revenue.FY2022] [R.revenue.FY2025]
- Contradicting: TTM EBIT margin is 18.0%, against a market-implied 23.0%. [D.ttm.operating_income] [D.ttm.revenue] [D.implied_ebit_margin]

### C5. Reported earnings convert into free cash flow.

Status: **supported**. [Judgment]

- Supporting: Free cash flow was positive in 4 of the last 4 fiscal years. [D.fcf.FY2022] [D.fcf.FY2023] [D.fcf.FY2024] [D.fcf.FY2025]
- Supporting: TTM operating cash flow is 1.5x net income. [D.ttm.cfo] [D.ttm.net_income]

### C6. Capital spending earns an adequate incremental return.

Status: **mixed**. [Judgment]

- Supporting: Cumulative capex of $2.4B coincided with a +$0.6B change in annual EBIT. [R.operating_income.FY2022] [R.operating_income.FY2025] [R.capex.FY2025]
- Contradicting: TTM capex is 1.8x D&A. [D.ttm.capex] [D.ttm.dna]

## Variant Perception

- Holding margins at the base case, the market EV requires a 17.5% revenue CAGR. [D.implied_revenue_cagr]
- Holding growth at the base case, the market EV requires a 23.0% EBIT margin. [D.implied_ebit_margin]
- From base-period FCFF, the market EV requires a 15.7% FCFF CAGR. [D.implied_fcff_cagr]

The variant view exists only where sourced operating evidence differs from these market-implied requirements. [Judgment]

## Valuation

Market capitalization is $26.0B [D.market_cap] and enterprise value is $29.0B [D.enterprise_value], at a share price of $104.00 [M.price].

| Scenario | Probability | Value per share | Terminal share of EV | Evidence |
|---|---|---|---|---|
| Bear | 25% | $46.48 | 75% | [D.value.bear] [A.scenario.bear] |
| Base | 50% | $77.21 | 75% | [D.value.base] [A.scenario.base] |
| Bull | 25% | $113.88 | 76% | [D.value.bull] [A.scenario.bull] |
| Weighted | 100% | $78.70 | n/a | [D.value.weighted] |

### Base-case bridge from assumptions to free cash flow (USD billions)

| Line | Y1 | Y2 | Y3 | Y4 | Y5 |
|---|---|---|---|---|---|
| revenue [A.growth_anchor] | 11.81 | 13.09 | 14.14 | 14.89 | 15.26 |
| ebit [A.ebit_margin] | 2.24 | 2.49 | 2.69 | 2.83 | 2.90 |
| taxes [A.tax_rate] | 0.47 | 0.52 | 0.56 | 0.59 | 0.61 |
| nopat [A.tax_rate] | 1.77 | 1.96 | 2.12 | 2.23 | 2.29 |
| dna [A.dna_pct] | 0.59 | 0.65 | 0.71 | 0.74 | 0.76 |
| capex [A.capex_pct] | 1.06 | 1.18 | 1.27 | 1.34 | 1.37 |
| delta_nwc [A.nwc_pct] | 0.14 | 0.13 | 0.11 | 0.07 | 0.04 |
| fcff [D.value.base] | 1.16 | 1.31 | 1.45 | 1.56 | 1.64 |

- Peer-median ev_ebitda of 10.4x implies $87.11 per share. [D.comps.ev_ebitda]
- Peer-median ev_revenue of 2.3x implies $82.80 per share. [D.comps.ev_revenue]
- Peer-median pe of 17.3x implies $88.48 per share. [D.comps.pe]

## Catalysts

- Next periodic filing, estimated around 2026-05-17 from past filing cadence. [Judgment]
- Next periodic filing and earnings call. [Judgment]
- Capital-allocation announcement. [Judgment]

## Bear Case

- (C1) Revenue compounded at 14.7% over 3 years, against a market-implied 17.5%. [R.revenue.FY2022] [R.revenue.FY2025] [D.implied_revenue_cagr]
- (C2) Probability-weighted DCF of $78.70 is -24% versus the $104.00 share price. [D.value.weighted] [M.price]
- (C2) Peer-median EV/EBITDA implies $87.11, -16% versus the share price. [D.comps.ev_ebitda] [M.price]
- (C3) Reconstructed debt changed +31% over the period. [D.debt.FY2022] [D.debt.FY2025]
- (C4) EBIT margin moved from 19.0% to 18.0% over the period. [R.operating_income.FY2022] [R.operating_income.FY2025] [R.revenue.FY2022] [R.revenue.FY2025]
- (C4) TTM EBIT margin is 18.0%, against a market-implied 23.0%. [D.ttm.operating_income] [D.ttm.revenue] [D.implied_ebit_margin]
- (C6) TTM capex is 1.8x D&A. [D.ttm.capex] [D.ttm.dna]
- The bear scenario values the shares at $46.48. [D.value.bear]

## Risks

- Findings test only what standardized XBRL data can show; segment and footnote detail are not parsed. [Judgment]
- No consensus estimates, so the variant view is measured against reverse-DCF expectations. [Judgment]
- interest_expense: no matching XBRL concept reported (InterestExpense, InterestExpenseNonoperating). [Judgment]
- stockholders_equity: no matching XBRL concept reported (StockholdersEquity). [Judgment]
- noncontrolling_interest: no matching XBRL concept reported (MinorityInterest). [Judgment]
- preferred_stock: no matching XBRL concept reported (PreferredStockValue). [Judgment]
- base case: terminal value is 75% of EV, so the result is dominated by WACC and terminal growth. [Judgment]
- bull case: terminal value is 76% of EV, so the result is dominated by WACC and terminal growth. [Judgment]

## Falsification Conditions

- C1: Revenue growth stays below the market-implied 17.5% for two consecutive fiscal years. [Judgment]
- C2: Sourced base-case value falls within 15% of, or below, the share price after assumptions are replaced with company-specific estimates. [Judgment]
- C3: Net debt exceeds 4.0x TTM EBITDA, or a refinancing occurs at a materially higher cost. [Judgment]
- C4: TTM EBIT margin stays below 23.0% (market-implied) for four quarters. [Judgment]
- C5: Operating cash flow falls below 0.8x net income, or TTM free cash flow turns negative. [Judgment]
- C6: Capex keeps rising while incremental EBIT stays flat or negative for two fiscal years. [Judgment]

## Unanswered Diligence

- What is the competitive response if returns stay above the cost of capital?. [Judgment]
- How much of recent growth is price rather than volume?. [Judgment]
- Replace placeholder WACC and terminal growth with a company-specific build-up. [Judgment]
- Source consensus estimates; this system has none and does not infer them. [Judgment]

## Model Assumptions Appendix

| Item | Value | Basis | Evidence |
|---|---|---|---|
| Base-case initial revenue growth | 0.135802 | Median annual revenue growth, last 3 FY, clipped to -5%/20%; fades to terminal growth | [A.growth_anchor] |
| Base-case EBIT margin | 0.19 | Median EBIT margin, last 3 FY | [A.ebit_margin] |
| Tax rate | 0.21 | Median effective rate, last 3 FY, clipped to 0%-35% | [A.tax_rate] |
| D&A as share of revenue | 0.05 | Median D&A / revenue, last 3 FY | [A.dna_pct] |
| Capex as share of revenue | 0.09 | Median capex / revenue, last 3 FY | [A.capex_pct] |
| Working capital as share of incremental revenue | 0.1 | Placeholder: 10% of incremental revenue; not derived from company data | [A.nwc_pct] |
| Weighted average cost of capital | 0.09 | Placeholder: 9% with no company-specific build-up; override it | [A.wacc] |
| Terminal growth rate | 0.025 | Placeholder: 2.5%, roughly long-run nominal growth; override it | [A.terminal_growth] |
| Bear scenario path | growth 9.6% fading to 1.5%; EBIT margin 15.2%; probability 25% | Mechanical shift around the base anchors; analyst should override. | [A.scenario.bear] |
| Base scenario path | growth 13.6% fading to 2.5%; EBIT margin 19.0%; probability 50% | Mechanical shift around the base anchors; analyst should override. | [A.scenario.base] |
| Bull scenario path | growth 17.6% fading to 3.5%; EBIT margin 22.8%; probability 25% | Mechanical shift around the base anchors; analyst should override. | [A.scenario.bull] |

## Evidence Ledger

<details>
<summary>Open the full evidence ledger</summary>


- **[R.capex.FY2021] DEMO capex, FY2021** — 360000000.0 USD (reported) | 10-K | 2021-12-31 | filed 2022-02-15 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.cash.FY2021] DEMO cash, FY2021** — 1200000000.0 USD (reported) | 10-K | 2021-12-31 | filed 2022-02-15 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.cfo.FY2021] DEMO cfo, FY2021** — 1131600000.0 USD (reported) | 10-K | 2021-12-31 | filed 2022-02-15 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[D.debt.FY2021] DEMO debt, FY2021** — 3000000000.0 USD (derived) | 10-K | 2021-12-31 | filed 2022-02-15 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.dna.FY2021] DEMO dna, FY2021** — 300000000.0 USD (reported) | 10-K | 2021-12-31 | filed 2022-02-15 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.net_income.FY2021] DEMO net income, FY2021** — 711000000.0 USD (reported) | 10-K | 2021-12-31 | filed 2022-02-15 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.operating_income.FY2021] DEMO operating income, FY2021** — 1080000000.0 USD (reported) | 10-K | 2021-12-31 | filed 2022-02-15 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.revenue.FY2021] DEMO revenue, FY2021** — 6000000000.0 USD (reported) | 10-K | 2021-12-31 | filed 2022-02-15 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.total_assets.FY2021] DEMO total assets, FY2021** — 9000000000.0 USD (reported) | 10-K | 2021-12-31 | filed 2022-02-15 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.total_liabilities.FY2021] DEMO total liabilities, FY2021** — 5400000000.0 USD (reported) | 10-K | 2021-12-31 | filed 2022-02-15 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.capex.FY2022] DEMO capex, FY2022** — 483000000.00000006 USD (reported) | 10-K | 2022-12-31 | filed 2023-02-15 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.cash.FY2022] DEMO cash, FY2022** — 1200000000.0 USD (reported) | 10-K | 2022-12-31 | filed 2023-02-15 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.cfo.FY2022] DEMO cfo, FY2022** — 1357920000.0 USD (reported) | 10-K | 2022-12-31 | filed 2023-02-15 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[D.debt.FY2022] DEMO debt, FY2022** — 3200000000.0 USD (derived) | 10-K | 2022-12-31 | filed 2023-02-15 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.dna.FY2022] DEMO dna, FY2022** — 345000000.0 USD (reported) | 10-K | 2022-12-31 | filed 2023-02-15 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.net_income.FY2022] DEMO net income, FY2022** — 884010000.0 USD (reported) | 10-K | 2022-12-31 | filed 2023-02-15 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.operating_income.FY2022] DEMO operating income, FY2022** — 1311000000.0 USD (reported) | 10-K | 2022-12-31 | filed 2023-02-15 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.revenue.FY2022] DEMO revenue, FY2022** — 6900000000.0 USD (reported) | 10-K | 2022-12-31 | filed 2023-02-15 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.total_assets.FY2022] DEMO total assets, FY2022** — 10350000000.0 USD (reported) | 10-K | 2022-12-31 | filed 2023-02-15 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.total_liabilities.FY2022] DEMO total liabilities, FY2022** — 5960000000.0 USD (reported) | 10-K | 2022-12-31 | filed 2023-02-15 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.capex.FY2023] DEMO capex, FY2023** — 648000000.0 USD (reported) | 10-K | 2023-12-31 | filed 2024-02-15 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.cash.FY2023] DEMO cash, FY2023** — 1200000000.0 USD (reported) | 10-K | 2023-12-31 | filed 2024-02-15 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.cfo.FY2023] DEMO cfo, FY2023** — 1660500000.0 USD (reported) | 10-K | 2023-12-31 | filed 2024-02-15 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[D.debt.FY2023] DEMO debt, FY2023** — 3600000000.0 USD (derived) | 10-K | 2023-12-31 | filed 2024-02-15 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.dna.FY2023] DEMO dna, FY2023** — 405000000.0 USD (reported) | 10-K | 2023-12-31 | filed 2024-02-15 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.net_income.FY2023] DEMO net income, FY2023** — 1109160000.0 USD (reported) | 10-K | 2023-12-31 | filed 2024-02-15 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.operating_income.FY2023] DEMO operating income, FY2023** — 1620000000.0 USD (reported) | 10-K | 2023-12-31 | filed 2024-02-15 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.revenue.FY2023] DEMO revenue, FY2023** — 8100000000.0 USD (reported) | 10-K | 2023-12-31 | filed 2024-02-15 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.total_assets.FY2023] DEMO total assets, FY2023** — 12150000000.0 USD (reported) | 10-K | 2023-12-31 | filed 2024-02-15 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.total_liabilities.FY2023] DEMO total liabilities, FY2023** — 6840000000.0 USD (reported) | 10-K | 2023-12-31 | filed 2024-02-15 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.capex.2024Q1] DEMO capex, 2024Q1** — 190440000.0 USD (reported) | 10-Q | 2024-03-31 | filed 2024-05-05 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.cash.2024Q1] DEMO cash, 2024Q1** — 1200000000.0 USD (reported) | 10-Q | 2024-03-31 | filed 2024-05-05 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.cfo.2024Q1] DEMO cfo, 2024Q1** — 416428800.0 USD (reported) | 10-Q | 2024-03-31 | filed 2024-05-05 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[D.debt.2024Q1] DEMO debt, 2024Q1** — 4000000000.0 USD (derived) | 10-Q | 2024-03-31 | filed 2024-05-05 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.dna.2024Q1] DEMO dna, 2024Q1** — 105800000.0 USD (reported) | 10-Q | 2024-03-31 | filed 2024-05-05 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.net_income.2024Q1] DEMO net income, 2024Q1** — 274003600.0 USD (reported) | 10-Q | 2024-03-31 | filed 2024-05-05 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.operating_income.2024Q1] DEMO operating income, 2024Q1** — 402040000.0 USD (reported) | 10-Q | 2024-03-31 | filed 2024-05-05 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.revenue.2024Q1] DEMO revenue, 2024Q1** — 2116000000.0 USD (reported) | 10-Q | 2024-03-31 | filed 2024-05-05 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.total_assets.2024Q1] DEMO total assets, 2024Q1** — 13800000000.0 USD (reported) | 10-Q | 2024-03-31 | filed 2024-05-05 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.total_liabilities.2024Q1] DEMO total liabilities, 2024Q1** — 7680000000.0 USD (reported) | 10-Q | 2024-03-31 | filed 2024-05-05 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[D.capex.2024Q2] DEMO capex, 2024Q2** — 198720000.0 USD (derived) | 10-Q | 2024-06-30 | filed 2024-08-05 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.cash.2024Q2] DEMO cash, 2024Q2** — 1200000000.0 USD (reported) | 10-Q | 2024-06-30 | filed 2024-08-05 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[D.cfo.2024Q2] DEMO cfo, 2024Q2** — 434534400.0 USD (derived) | 10-Q | 2024-06-30 | filed 2024-08-05 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[D.debt.2024Q2] DEMO debt, 2024Q2** — 4000000000.0 USD (derived) | 10-Q | 2024-06-30 | filed 2024-08-05 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[D.dna.2024Q2] DEMO dna, 2024Q2** — 110400000.0 USD (derived) | 10-Q | 2024-06-30 | filed 2024-08-05 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.net_income.2024Q2] DEMO net income, 2024Q2** — 285916800.0 USD (reported) | 10-Q | 2024-06-30 | filed 2024-08-05 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.operating_income.2024Q2] DEMO operating income, 2024Q2** — 419520000.0 USD (reported) | 10-Q | 2024-06-30 | filed 2024-08-05 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.revenue.2024Q2] DEMO revenue, 2024Q2** — 2208000000.0 USD (reported) | 10-Q | 2024-06-30 | filed 2024-08-05 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.total_assets.2024Q2] DEMO total assets, 2024Q2** — 13800000000.0 USD (reported) | 10-Q | 2024-06-30 | filed 2024-08-05 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.total_liabilities.2024Q2] DEMO total liabilities, 2024Q2** — 7680000000.0 USD (reported) | 10-Q | 2024-06-30 | filed 2024-08-05 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[D.capex.2024Q3] DEMO capex, 2024Q3** — 207000000.0 USD (derived) | 10-Q | 2024-09-30 | filed 2024-11-05 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.cash.2024Q3] DEMO cash, 2024Q3** — 1200000000.0 USD (reported) | 10-Q | 2024-09-30 | filed 2024-11-05 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[D.cfo.2024Q3] DEMO cfo, 2024Q3** — 452640000.0 USD (derived) | 10-Q | 2024-09-30 | filed 2024-11-05 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[D.debt.2024Q3] DEMO debt, 2024Q3** — 4000000000.0 USD (derived) | 10-Q | 2024-09-30 | filed 2024-11-05 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[D.dna.2024Q3] DEMO dna, 2024Q3** — 115000000.0 USD (derived) | 10-Q | 2024-09-30 | filed 2024-11-05 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.net_income.2024Q3] DEMO net income, 2024Q3** — 297830000.0 USD (reported) | 10-Q | 2024-09-30 | filed 2024-11-05 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.operating_income.2024Q3] DEMO operating income, 2024Q3** — 437000000.0 USD (reported) | 10-Q | 2024-09-30 | filed 2024-11-05 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.revenue.2024Q3] DEMO revenue, 2024Q3** — 2300000000.0 USD (reported) | 10-Q | 2024-09-30 | filed 2024-11-05 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.total_assets.2024Q3] DEMO total assets, 2024Q3** — 13800000000.0 USD (reported) | 10-Q | 2024-09-30 | filed 2024-11-05 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.total_liabilities.2024Q3] DEMO total liabilities, 2024Q3** — 7680000000.0 USD (reported) | 10-Q | 2024-09-30 | filed 2024-11-05 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.capex.FY2024] DEMO capex, FY2024** — 828000000.0 USD (reported) | 10-K | 2024-12-31 | filed 2025-02-15 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[D.capex.2024Q4] DEMO capex, 2024Q4** — 231840000.0 USD (derived) | 10-K | 2024-12-31 | filed 2025-02-15 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.cash.FY2024] DEMO cash, FY2024** — 1200000000.0 USD (reported) | 10-K | 2024-12-31 | filed 2025-02-15 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.cash.2024Q4] DEMO cash, 2024Q4** — 1200000000.0 USD (reported) | 10-K | 2024-12-31 | filed 2025-02-15 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.cfo.FY2024] DEMO cfo, FY2024** — 1810560000.0 USD (reported) | 10-K | 2024-12-31 | filed 2025-02-15 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[D.cfo.2024Q4] DEMO cfo, 2024Q4** — 506956800.0 USD (derived) | 10-K | 2024-12-31 | filed 2025-02-15 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[D.debt.FY2024] DEMO debt, FY2024** — 4000000000.0 USD (derived) | 10-K | 2024-12-31 | filed 2025-02-15 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[D.debt.2024Q4] DEMO debt, 2024Q4** — 4000000000.0 USD (derived) | 10-K | 2024-12-31 | filed 2025-02-15 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.dna.FY2024] DEMO dna, FY2024** — 460000000.0 USD (reported) | 10-K | 2024-12-31 | filed 2025-02-15 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[D.dna.2024Q4] DEMO dna, 2024Q4** — 128800000.0 USD (derived) | 10-K | 2024-12-31 | filed 2025-02-15 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.net_income.FY2024] DEMO net income, FY2024** — 1191320000.0 USD (reported) | 10-K | 2024-12-31 | filed 2025-02-15 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[D.net_income.2024Q4] DEMO net income, 2024Q4** — 333569600.0 USD (derived) | 10-K | 2024-12-31 | filed 2025-02-15 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.operating_income.FY2024] DEMO operating income, FY2024** — 1748000000.0 USD (reported) | 10-K | 2024-12-31 | filed 2025-02-15 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[D.operating_income.2024Q4] DEMO operating income, 2024Q4** — 489440000.0 USD (derived) | 10-K | 2024-12-31 | filed 2025-02-15 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.revenue.FY2024] DEMO revenue, FY2024** — 9200000000.0 USD (reported) | 10-K | 2024-12-31 | filed 2025-02-15 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[D.revenue.2024Q4] DEMO revenue, 2024Q4** — 2576000000.0 USD (derived) | 10-K | 2024-12-31 | filed 2025-02-15 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.total_assets.FY2024] DEMO total assets, FY2024** — 13800000000.0 USD (reported) | 10-K | 2024-12-31 | filed 2025-02-15 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.total_assets.2024Q4] DEMO total assets, 2024Q4** — 13800000000.0 USD (reported) | 10-K | 2024-12-31 | filed 2025-02-15 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.total_liabilities.FY2024] DEMO total liabilities, FY2024** — 7680000000.0 USD (reported) | 10-K | 2024-12-31 | filed 2025-02-15 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.total_liabilities.2024Q4] DEMO total liabilities, 2024Q4** — 7680000000.0 USD (reported) | 10-K | 2024-12-31 | filed 2025-02-15 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.capex.2025Q1] DEMO capex, 2025Q1** — 215280000.0 USD (reported) | 10-Q | 2025-03-31 | filed 2025-05-05 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.cash.2025Q1] DEMO cash, 2025Q1** — 1200000000.0 USD (reported) | 10-Q | 2025-03-31 | filed 2025-05-05 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.cfo.2025Q1] DEMO cfo, 2025Q1** — 451131200.0 USD (reported) | 10-Q | 2025-03-31 | filed 2025-05-05 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[D.debt.2025Q1] DEMO debt, 2025Q1** — 4200000000.0 USD (derived) | 10-Q | 2025-03-31 | filed 2025-05-05 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.dna.2025Q1] DEMO dna, 2025Q1** — 119600000.0 USD (reported) | 10-Q | 2025-03-31 | filed 2025-05-05 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.net_income.2025Q1] DEMO net income, 2025Q1** — 294354000.0 USD (reported) | 10-Q | 2025-03-31 | filed 2025-05-05 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.operating_income.2025Q1] DEMO operating income, 2025Q1** — 430560000.0 USD (reported) | 10-Q | 2025-03-31 | filed 2025-05-05 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.revenue.2025Q1] DEMO revenue, 2025Q1** — 2392000000.0 USD (reported) | 10-Q | 2025-03-31 | filed 2025-05-05 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.total_assets.2025Q1] DEMO total assets, 2025Q1** — 15600000000.0 USD (reported) | 10-Q | 2025-03-31 | filed 2025-05-05 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.total_liabilities.2025Q1] DEMO total liabilities, 2025Q1** — 8360000000.0 USD (reported) | 10-Q | 2025-03-31 | filed 2025-05-05 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[D.capex.2025Q2] DEMO capex, 2025Q2** — 224640000.0 USD (derived) | 10-Q | 2025-06-30 | filed 2025-08-05 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.cash.2025Q2] DEMO cash, 2025Q2** — 1200000000.0 USD (reported) | 10-Q | 2025-06-30 | filed 2025-08-05 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[D.cfo.2025Q2] DEMO cfo, 2025Q2** — 470745600.0 USD (derived) | 10-Q | 2025-06-30 | filed 2025-08-05 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[D.debt.2025Q2] DEMO debt, 2025Q2** — 4200000000.0 USD (derived) | 10-Q | 2025-06-30 | filed 2025-08-05 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[D.dna.2025Q2] DEMO dna, 2025Q2** — 124800000.0 USD (derived) | 10-Q | 2025-06-30 | filed 2025-08-05 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.net_income.2025Q2] DEMO net income, 2025Q2** — 307152000.0 USD (reported) | 10-Q | 2025-06-30 | filed 2025-08-05 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.operating_income.2025Q2] DEMO operating income, 2025Q2** — 449280000.0 USD (reported) | 10-Q | 2025-06-30 | filed 2025-08-05 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.revenue.2025Q2] DEMO revenue, 2025Q2** — 2496000000.0 USD (reported) | 10-Q | 2025-06-30 | filed 2025-08-05 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.total_assets.2025Q2] DEMO total assets, 2025Q2** — 15600000000.0 USD (reported) | 10-Q | 2025-06-30 | filed 2025-08-05 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.total_liabilities.2025Q2] DEMO total liabilities, 2025Q2** — 8360000000.0 USD (reported) | 10-Q | 2025-06-30 | filed 2025-08-05 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[D.capex.2025Q3] DEMO capex, 2025Q3** — 234000000.0 USD (derived) | 10-Q | 2025-09-30 | filed 2025-11-05 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.cash.2025Q3] DEMO cash, 2025Q3** — 1200000000.0 USD (reported) | 10-Q | 2025-09-30 | filed 2025-11-05 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[D.cfo.2025Q3] DEMO cfo, 2025Q3** — 490360000.0 USD (derived) | 10-Q | 2025-09-30 | filed 2025-11-05 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[D.debt.2025Q3] DEMO debt, 2025Q3** — 4200000000.0 USD (derived) | 10-Q | 2025-09-30 | filed 2025-11-05 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[D.dna.2025Q3] DEMO dna, 2025Q3** — 130000000.0 USD (derived) | 10-Q | 2025-09-30 | filed 2025-11-05 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.net_income.2025Q3] DEMO net income, 2025Q3** — 319950000.0 USD (reported) | 10-Q | 2025-09-30 | filed 2025-11-05 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.operating_income.2025Q3] DEMO operating income, 2025Q3** — 468000000.0 USD (reported) | 10-Q | 2025-09-30 | filed 2025-11-05 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.revenue.2025Q3] DEMO revenue, 2025Q3** — 2600000000.0 USD (reported) | 10-Q | 2025-09-30 | filed 2025-11-05 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.total_assets.2025Q3] DEMO total assets, 2025Q3** — 15600000000.0 USD (reported) | 10-Q | 2025-09-30 | filed 2025-11-05 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.total_liabilities.2025Q3] DEMO total liabilities, 2025Q3** — 8360000000.0 USD (reported) | 10-Q | 2025-09-30 | filed 2025-11-05 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.capex.FY2025] DEMO capex, FY2025** — 936000000.0 USD (reported) | 10-K | 2025-12-31 | filed 2026-02-15 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[D.capex.2025Q4] DEMO capex, 2025Q4** — 262080000.0 USD (derived) | 10-K | 2025-12-31 | filed 2026-02-15 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.cash.FY2025] DEMO cash, FY2025** — 1200000000.0 USD (reported) | 10-K | 2025-12-31 | filed 2026-02-15 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.cash.2025Q4] DEMO cash, 2025Q4** — 1200000000.0 USD (reported) | 10-K | 2025-12-31 | filed 2026-02-15 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.cfo.FY2025] DEMO cfo, FY2025** — 1961440000.0 USD (reported) | 10-K | 2025-12-31 | filed 2026-02-15 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[D.cfo.2025Q4] DEMO cfo, 2025Q4** — 549203200.0 USD (derived) | 10-K | 2025-12-31 | filed 2026-02-15 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[D.debt.FY2025] DEMO debt, FY2025** — 4200000000.0 USD (derived) | 10-K | 2025-12-31 | filed 2026-02-15 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[D.debt.2025Q4] DEMO debt, 2025Q4** — 4200000000.0 USD (derived) | 10-K | 2025-12-31 | filed 2026-02-15 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.dna.FY2025] DEMO dna, FY2025** — 520000000.0 USD (reported) | 10-K | 2025-12-31 | filed 2026-02-15 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[D.dna.2025Q4] DEMO dna, 2025Q4** — 145600000.0 USD (derived) | 10-K | 2025-12-31 | filed 2026-02-15 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.net_income.FY2025] DEMO net income, FY2025** — 1279800000.0 USD (reported) | 10-K | 2025-12-31 | filed 2026-02-15 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[D.net_income.2025Q4] DEMO net income, 2025Q4** — 358344000.0 USD (derived) | 10-K | 2025-12-31 | filed 2026-02-15 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.operating_income.FY2025] DEMO operating income, FY2025** — 1872000000.0 USD (reported) | 10-K | 2025-12-31 | filed 2026-02-15 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[D.operating_income.2025Q4] DEMO operating income, 2025Q4** — 524160000.0 USD (derived) | 10-K | 2025-12-31 | filed 2026-02-15 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.revenue.FY2025] DEMO revenue, FY2025** — 10400000000.0 USD (reported) | 10-K | 2025-12-31 | filed 2026-02-15 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[D.revenue.2025Q4] DEMO revenue, 2025Q4** — 2912000000.0 USD (derived) | 10-K | 2025-12-31 | filed 2026-02-15 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.total_assets.FY2025] DEMO total assets, FY2025** — 15600000000.0 USD (reported) | 10-K | 2025-12-31 | filed 2026-02-15 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.total_assets.2025Q4] DEMO total assets, 2025Q4** — 15600000000.0 USD (reported) | 10-K | 2025-12-31 | filed 2026-02-15 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.total_liabilities.FY2025] DEMO total liabilities, FY2025** — 8360000000.0 USD (reported) | 10-K | 2025-12-31 | filed 2026-02-15 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.total_liabilities.2025Q4] DEMO total liabilities, 2025Q4** — 8360000000.0 USD (reported) | 10-K | 2025-12-31 | filed 2026-02-15 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[D.fcf.FY2021] DEMO free cash flow (CFO less capex), FY2021** — 771600000.0 USD (derived) | 2021-12-31 | Retrieved: 2026-11-08T21:13:51Z | Inputs: R.cfo.FY2021, R.capex.FY2021
- **[D.fcf.FY2022] DEMO free cash flow (CFO less capex), FY2022** — 874920000.0 USD (derived) | 2022-12-31 | Retrieved: 2026-11-08T21:13:51Z | Inputs: R.cfo.FY2022, R.capex.FY2022
- **[D.fcf.FY2023] DEMO free cash flow (CFO less capex), FY2023** — 1012500000.0 USD (derived) | 2023-12-31 | Retrieved: 2026-11-08T21:13:51Z | Inputs: R.cfo.FY2023, R.capex.FY2023
- **[D.fcf.FY2024] DEMO free cash flow (CFO less capex), FY2024** — 982560000.0 USD (derived) | 2024-12-31 | Retrieved: 2026-11-08T21:13:51Z | Inputs: R.cfo.FY2024, R.capex.FY2024
- **[D.fcf.FY2025] DEMO free cash flow (CFO less capex), FY2025** — 1025440000.0 USD (derived) | 2025-12-31 | Retrieved: 2026-11-08T21:13:51Z | Inputs: R.cfo.FY2025, R.capex.FY2025
- **[D.fcf.2024Q1] DEMO free cash flow (CFO less capex), 2024Q1** — 225988800.0 USD (derived) | 2024-03-31 | Retrieved: 2026-11-08T21:13:51Z | Inputs: R.cfo.2024Q1, R.capex.2024Q1
- **[D.fcf.2024Q2] DEMO free cash flow (CFO less capex), 2024Q2** — 235814400.0 USD (derived) | 2024-06-30 | Retrieved: 2026-11-08T21:13:51Z | Inputs: D.cfo.2024Q2, D.capex.2024Q2
- **[D.fcf.2024Q3] DEMO free cash flow (CFO less capex), 2024Q3** — 245640000.0 USD (derived) | 2024-09-30 | Retrieved: 2026-11-08T21:13:51Z | Inputs: D.cfo.2024Q3, D.capex.2024Q3
- **[D.fcf.2024Q4] DEMO free cash flow (CFO less capex), 2024Q4** — 275116800.0 USD (derived) | 2024-12-31 | Retrieved: 2026-11-08T21:13:51Z | Inputs: D.cfo.2024Q4, D.capex.2024Q4
- **[D.fcf.2025Q1] DEMO free cash flow (CFO less capex), 2025Q1** — 235851200.0 USD (derived) | 2025-03-31 | Retrieved: 2026-11-08T21:13:51Z | Inputs: R.cfo.2025Q1, R.capex.2025Q1
- **[D.fcf.2025Q2] DEMO free cash flow (CFO less capex), 2025Q2** — 246105600.0 USD (derived) | 2025-06-30 | Retrieved: 2026-11-08T21:13:51Z | Inputs: D.cfo.2025Q2, D.capex.2025Q2
- **[D.fcf.2025Q3] DEMO free cash flow (CFO less capex), 2025Q3** — 256360000.0 USD (derived) | 2025-09-30 | Retrieved: 2026-11-08T21:13:51Z | Inputs: D.cfo.2025Q3, D.capex.2025Q3
- **[D.fcf.2025Q4] DEMO free cash flow (CFO less capex), 2025Q4** — 287123200.0 USD (derived) | 2025-12-31 | Retrieved: 2026-11-08T21:13:51Z | Inputs: D.cfo.2025Q4, D.capex.2025Q4
- **[D.ttm.revenue] DEMO trailing-twelve-month revenue** — 10400000000.0 USD (derived) | 2025-12-31 | Retrieved: 2026-11-08T21:13:51Z | Inputs: R.revenue.2025Q1, R.revenue.2025Q2, R.revenue.2025Q3, D.revenue.2025Q4
- **[D.ttm.operating_income] DEMO trailing-twelve-month operating income** — 1872000000.0 USD (derived) | 2025-12-31 | Retrieved: 2026-11-08T21:13:51Z | Inputs: R.operating_income.2025Q1, R.operating_income.2025Q2, R.operating_income.2025Q3, D.operating_income.2025Q4
- **[D.ttm.net_income] DEMO trailing-twelve-month net income** — 1279800000.0 USD (derived) | 2025-12-31 | Retrieved: 2026-11-08T21:13:51Z | Inputs: R.net_income.2025Q1, R.net_income.2025Q2, R.net_income.2025Q3, D.net_income.2025Q4
- **[D.ttm.cfo] DEMO trailing-twelve-month cfo** — 1961440000.0 USD (derived) | 2025-12-31 | Retrieved: 2026-11-08T21:13:51Z | Inputs: R.cfo.2025Q1, D.cfo.2025Q2, D.cfo.2025Q3, D.cfo.2025Q4
- **[D.ttm.capex] DEMO trailing-twelve-month capex** — 936000000.0 USD (derived) | 2025-12-31 | Retrieved: 2026-11-08T21:13:51Z | Inputs: R.capex.2025Q1, D.capex.2025Q2, D.capex.2025Q3, D.capex.2025Q4
- **[D.ttm.dna] DEMO trailing-twelve-month dna** — 520000000.0 USD (derived) | 2025-12-31 | Retrieved: 2026-11-08T21:13:51Z | Inputs: R.dna.2025Q1, D.dna.2025Q2, D.dna.2025Q3, D.dna.2025Q4
- **[D.ttm.fcf] DEMO trailing-twelve-month free cash flow** — 1025440000.0 USD (derived) | 2025-12-31 | Retrieved: 2026-11-08T21:13:51Z | Inputs: D.ttm.cfo, D.ttm.capex
- **[M.price] DEMO closing share price** — 104.0 USD/share (reported) | 2026-02-27 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[R.shares] DEMO common shares outstanding** — 250000000.0 shares (reported) | 10-K | 2026-01-31 | filed 2026-02-15 | Source: synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[D.market_cap] DEMO market capitalization (price x basic shares)** — 26000000000.0 USD (derived) | 2026-02-27 | Retrieved: 2026-11-08T21:13:51Z | Inputs: M.price, R.shares
- **[D.enterprise_value] DEMO enterprise value (market cap + debt + NCI + preferred - cash)** — 29000000000.0 USD (derived) | 2026-02-27 | Retrieved: 2026-11-08T21:13:51Z | Inputs: D.market_cap, D.debt.2025Q4, R.cash.2025Q4
- **[A.growth_anchor] Base-case initial revenue growth** — 0.135802 ratio (assumed)
- **[A.ebit_margin] Base-case EBIT margin** — 0.19 ratio (assumed)
- **[A.tax_rate] Tax rate** — 0.21 ratio (assumed)
- **[A.dna_pct] D&A as share of revenue** — 0.05 ratio (assumed)
- **[A.capex_pct] Capex as share of revenue** — 0.09 ratio (assumed)
- **[A.nwc_pct] Working capital as share of incremental revenue** — 0.1 ratio (assumed)
- **[A.wacc] Weighted average cost of capital** — 0.09 ratio (assumed)
- **[A.terminal_growth] Terminal growth rate** — 0.025 ratio (assumed)
- **[A.scenario.bear] Bear scenario path** — growth 9.6% fading to 1.5%; EBIT margin 15.2%; probability 25% (assumed)
- **[A.scenario.base] Base scenario path** — growth 13.6% fading to 2.5%; EBIT margin 19.0%; probability 50% (assumed)
- **[A.scenario.bull] Bull scenario path** — growth 17.6% fading to 3.5%; EBIT margin 22.8%; probability 25% (assumed)
- **[D.value.bear] Bear DCF value per share** — 46.48 USD/share (derived) | Source: Investment OS valuation model | Inputs: A.growth_anchor, A.ebit_margin, A.wacc, A.terminal_growth, A.scenario.bear, D.enterprise_value
- **[D.value.base] Base DCF value per share** — 77.21 USD/share (derived) | Source: Investment OS valuation model | Inputs: A.growth_anchor, A.ebit_margin, A.wacc, A.terminal_growth, A.scenario.base, D.enterprise_value
- **[D.value.bull] Bull DCF value per share** — 113.88 USD/share (derived) | Source: Investment OS valuation model | Inputs: A.growth_anchor, A.ebit_margin, A.wacc, A.terminal_growth, A.scenario.bull, D.enterprise_value
- **[D.value.weighted] Probability-weighted DCF value per share** — 78.7 USD/share (derived) | Source: Investment OS valuation model | Inputs: D.value.bear, D.value.base, D.value.bull
- **[D.implied_fcff_cagr] Market-implied FCFF CAGR (reverse DCF)** — 0.1573 ratio (derived) | Source: Investment OS reverse DCF | Inputs: D.enterprise_value, A.wacc, A.terminal_growth, A.ebit_margin
- **[D.implied_revenue_cagr] Market-implied revenue CAGR (reverse DCF)** — 0.1754 ratio (derived) | Source: Investment OS reverse DCF | Inputs: D.enterprise_value, A.wacc, A.terminal_growth, A.ebit_margin
- **[D.implied_ebit_margin] Market-implied EBIT margin (reverse DCF)** — 0.2304 ratio (derived) | Source: Investment OS reverse DCF | Inputs: D.enterprise_value, A.wacc, A.terminal_growth, A.ebit_margin
- **[D.comps.ev_ebitda] Implied price at peer-median ev_ebitda (10.4x)** — 87.11 USD/share (derived) | Source: synthetic-source;synthetic-source;synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[D.comps.ev_revenue] Implied price at peer-median ev_revenue (2.3x)** — 82.8 USD/share (derived) | Source: synthetic-source;synthetic-source;synthetic-source | Retrieved: 2026-11-08T21:13:51Z
- **[D.comps.pe] Implied price at peer-median pe (17.3x)** — 88.48 USD/share (derived) | Source: synthetic-source;synthetic-source;synthetic-source | Retrieved: 2026-11-08T21:13:51Z

</details>
