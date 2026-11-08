# Sample data

## Included: synthetic data only

These files are **simulated and are not market data**. They use a fixed seed and exist to validate the Alternative Data Lab against answers known in advance.

| File | Contents | Expected verdict at zero publication lag |
|---|---|---|
| `synthetic_prices.csv` | Simulated weekly price | Target series |
| `synthetic_signal_informative.csv` | Planted relationship with next-week return | Survives out of sample |
| `synthetic_signal_noise.csv` | Independent noise | No reliable incremental information |
| `synthetic_signal_leaky.csv` | Contains next week's return | Leakage suspected |

## Not included: real price series

Market-price files are not redistributed. To download UNG, XLU, SPY and VST series for local use from Yahoo Finance via `yfinance`:

```bash
python scripts/build_sample_data.py
```

These files stay on your machine and are excluded by `.gitignore`. Check Yahoo's terms for your use.
