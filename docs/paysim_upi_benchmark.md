# PaySim UPI-like Benchmark

`scripts/build_paysim_upi_benchmark.py` streams the local PaySim CSV in chunks and produces a small deterministic sample of aggregate transaction-behaviour profiles.

It retains profiles with at least three observed transactions and selects the most active 500 profiles, avoiding a benchmark dominated by one-off transactions.

Run from the repository root:

```powershell
.\backend\.venv\Scripts\python.exe scripts\build_paysim_upi_benchmark.py `
  --input-path data\raw\paysim\PS_20174392719_1491204439457_log.csv
```

## What it produces

- transaction frequency and active-hour count;
- average and median ticket size;
- merchant-payment and P2P-transfer ratios;
- aggregate credit/outflow amounts;
- activity regularity.

Transaction types are only mapped for an illustrative UPI-like benchmark:

| PaySim type | Benchmark label |
| --- | --- |
| `PAYMENT` | merchant payment |
| `TRANSFER` | P2P transfer |
| `CASH_IN` | account credit |
| `CASH_OUT` | cash/debit outflow |
| `DEBIT` | scheduled debit |

## Strict boundary

PaySim is a synthetic mobile-money fraud dataset. It is **not Indian UPI data**, not a live connector, and is not used by live NADI underwriting. The generated output excludes original and destination account identifiers, excludes fraud labels, and exists only to benchmark privacy-preserving aggregate feature distributions.
