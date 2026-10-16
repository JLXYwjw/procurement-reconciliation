# Procurement & Purchase-Order Reconciliation Analysis

Analysis of a large, real CA statewide procurement extract to surface cost, concentration and control issues, ending in actionable recommendations.

**The business problem.** The state pays huge sums through thousands of purchase orders but often cannot see where money concentrates, which payments are uncontrolled (exempt / flexible channels), and which payees need reconciliation. This project cleans a 346k-record procurement extract and quantifies those issues so finance & procurement can target reconciliation, governance and strategic-supplier work where it matters.

## Status
- [x] Data inspection & cleaning (money `$`, dates, supplier names)
- [x] Initial metrics (total spend, PO/vendor counts, CR4/CR8, top-10 share, method & year distribution)
- [x] Department / category / location breakdowns + monthly trend
- [x] Machine learning: supplier segmentation (KMeans, strategic split) + flexible/exempt method review
- [x] Charts (`assets/`) + full report (**open `index.html`** — objective / cleaning / metrics / modeling / recommendations, each chart with insight + action)
- [x] Tests (`tests/`)

## Report
Open **`index.html`** in a browser for the full report (business objective → cleaning → metrics → modeling → recommendations).

## Run
```bash
pip install -r requirements.txt
python scripts/clean_data.py      # raw CSV -> output/procurement_clean.parquet
python scripts/analyze.py         # headline metrics (CR4/CR8, top-10, HHI)
python scripts/analyze_extended.py# department / category / monthly trend
python scripts/supplier_cluster.py# KMeans supplier segmentation -> output/supplier_segmentation.parquet
python scripts/ml_analysis.py     # flexible/exempt review lists -> output/*.parquet
python scripts/generate_charts.py # charts -> assets/*.png
python -m pytest tests -q         # unit + report + output contract tests
```

## Key findings
- **$151.2B** spend, 200,533 POs, 24,732 suppliers; CR4 = **26.5%**, CR8 = **37.4%**, top-10 = **41.4%** (all healthcare-payer orgs).
- **Health Care Services = 66%** of spend; UNSPSC segment 85 (healthcare) = **73.9%**.
- Spend is **lumpy**: one-off/large settlements = **68.8%** of spend (4,583 payees), while a **30.1% recurring core** (1,921 multi-year partners) is the strategic-relationship tier — a split a spend ranking cannot produce.
- **40.1% of spend is legally exempt** (documented rationale needed) and **$6.36B** is flexible-method (process-review list).
- A unit-cost outlier screen was **evaluated and dropped** (2-digit segment too coarse; ~26% flag rate unreliable) — kept as reproducible evidence that a SKU/market-price baseline is required before any price verdict.

## Recommendations (summary)
1. Stand up a healthcare-payment **reconciliation** workstream (claims vs invoice vs PO, rate & settlement audit) for the one-off/large tier.
2. Attach a documented rationale to **exempt** spend + sample-review the **flexible** $6.36B.
3. Manage the 1,921 **recurring-core** suppliers as strategic accounts.
4. Build a SKU / market-price **baseline** before any unit-price verdict.
