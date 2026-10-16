# Procurement & Purchase-Order Reconciliation Analysis

Analysis of a large, real CA statewide procurement extract to surface cost, concentration and control issues, ending in actionable recommendations.

**The business problem.** Procurement teams spend large sums with thousands of vendors but often cannot see where money concentrates, which purchases are uncontrolled (maverick / sole-source) and which line items carry anomalous unit prices. This project cleans a 346k-record procurement extract and quantifies those issues so purchasing can negotiate better and set controls.

## Status
- [x] Data inspection & cleaning (money `$`, dates, supplier names)
- [x] Initial metrics (total spend, PO/vendor counts, top-10 share, HHI, method & year distribution)
- [x] Department / category / location breakdowns + monthly trend
- [x] Machine learning: unit-cost review queue (MAD) + supplier segmentation (KMeans) + flexible-method review list
- [x] Charts (`assets/`) + full report (**open `index.html`** — objective / cleaning / metrics / modeling / visualization / recommendations)
- [x] Tests (`tests/`)

## Report
Open **`index.html`** in a browser for the full 6-part report (business objective → cleaning → metrics → modeling → visualization → recommendations).

## Run
```bash
pip install -r requirements.txt
python scripts/clean_data.py      # raw CSV -> output/procurement_clean.parquet
python scripts/analyze.py         # headline metrics
python scripts/analyze_extended.py# department / category / monthly trend
python scripts/ml_analysis.py     # segmentation + review lists -> output/*.parquet
python scripts/generate_charts.py # charts -> assets/*.png
python -m pytest tests -q         # unit + report + (when present) output contract tests
```

## Key findings
- **$151.2B** spend, 200,533 POs, 24,732 suppliers; top-10 suppliers = **41.4%**.
- **Health Care Services = 66%** of spend; UNSPSC segment 85 (healthcare) = **73.9%**.
- **8 core suppliers = 35.4%** of spend (all healthcare-payer orgs) → the consolidation lever.
- **$6.36B** of flexible-method spend → a process-review list.
- 32k unit-cost flags are mostly large, legitimate buys → used as a review queue, not a verdict.
