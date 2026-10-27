# Procurement & Purchase-Order Reconciliation Analysis
![CI](https://github.com/JLXYwjw/procurement-reconciliation/actions/workflows/ci.yml/badge.svg)


Analysis of a large, real CA statewide procurement extract to surface cost, concentration and control issues, ending in actionable recommendations.

**Scope note.** "Reconciliation" here is **data-level**: collapsing a dirty 909k-line extract into one consistent, deduplicated, matchable purchase-order table. Business-level payment reconciliation (claims vs invoices vs POs) needs claims/invoice data this extract lacks — the report quantifies that gap and lists it as the next step rather than claiming to have done it.

**The business problem.** The state pays huge sums through thousands of purchase orders but often cannot see where money concentrates, which payments are uncontrolled (exempt / flexible channels), and which payees need reconciliation. This project cleans a 346k-record procurement extract and quantifies those issues so finance & procurement can target reconciliation, governance and strategic-supplier work where it matters.

## Status
- [x] Data inspection & cleaning (money `$`, dates, supplier names)
- [x] Initial metrics (total spend, PO/vendor counts, CR4/CR8, top-10 share, method & year distribution)
- [x] Department / category / location breakdowns + monthly trend
- [x] Machine learning: supplier segmentation (KMeans, strategic split) + flexible/exempt method review
- [x] Charts (`assets/`) + full report (**open `index.html`** — objective / cleaning / metrics / modeling / recommendations, each chart with insight + action)
- [x] Tests (`tests/`)

## Report
Open **`index.html`** in a browser for the full report (business objective → cleaning → metrics → modeling → recommendations). GitHub does not render HTML in-repo — preview the key charts below:

## Visuals

![Healthcare concentration](assets/healthcare_concentration.png)
![Top 10 suppliers](assets/top10_suppliers.png)
![Method control](assets/method_control.png)

## Run
```bash
pip install -r requirements.txt
python scripts/clean_data_simple.py      # raw CSV -> data/output/procurement_clean.parquet
python scripts/analyze_simple.py         # headline metrics (CR4/CR8, top-10, HHI)
python scripts/analyze_extended_simple.py# department / category / monthly trend
python scripts/supplier_cluster_simple.py# KMeans supplier segmentation -> output/supplier_segmentation.parquet
python scripts/ml_analysis_simple.py     # flexible/exempt review lists -> output/*.parquet
python scripts/generate_charts_simple.py # charts -> assets/*.png
python -m pytest tests -q         # unit + report + output contract tests
```

## Key findings
- **$151.2B** spend, 200,533 POs, 24,732 suppliers; CR4 = **26.5%**, CR8 = **37.4%**, top-10 = **41.4%** (all healthcare-payer orgs).
- **Health Care Services = 66%** of spend; UNSPSC segment 85 (healthcare) = **73.9%**.
- Spend is **lumpy**: one-off/large settlements = **68.8%** of spend (4,583 payees), while a **30.1% recurring core** (1,921 multi-year partners) is the strategic tier — a split a spend ranking cannot produce. ~58% of that core is public bodies (intergovernmental transfers); ~42% is private strategic suppliers.
- **40.1% of spend is legally exempt**, concentrated in the recurring core (59.7%) — mostly intergovernmental transfers — while the one-off/large tier is mostly competitive (≈66%); **$6.36B** is flexible-method (process-review list).
- **Data quality**: raw Purchase Date is dirty (years 1911–2912); 17,634 absurd values are nulled (0 rows lost); creation_date (2012–2015, clean) drives the time trends.
- A unit-cost outlier screen was **evaluated and dropped** (2-digit segment too coarse; ~26% flag rate unreliable) — kept as reproducible evidence that a SKU/market-price baseline is required before any price verdict.

## Recommendations (summary)
1. Run payment **reconciliation** on the one-off/large tier (claims vs invoice vs PO, rate & settlement audit) — flagged as the next step needing claims/invoice data.
2. Document exempt spend in the core + sample-review the flexible $6.36B.
3. Manage the ~42% **private** recurring-core suppliers as strategic accounts; govern the public bodies.
4. Build a SKU / market-price **baseline** before any unit-price verdict.

## Data source

The raw extract lives in `data/raw/` (excluded from git — clone this repo, then download the data yourself).

| File | What it is | Kaggle download |
|---|---|---|
| `PURCHASE ORDER DATA EXTRACT 2012-2015_0.csv` | CA statewide purchase-order extract, ~346k records, 2012–2015 | `kaggle datasets download -d sohier/large-purchases-by-the-state-of-ca -p data/raw --unzip` |

- **Kaggle page:** https://www.kaggle.com/datasets/sohier/large-purchases-by-the-state-of-ca
- **Official source:** California Open Data Portal (`data.ca.gov`) statewide procurement / purchase-order export.
- Honest note: the file here is the official CA PO extract; the Kaggle mirror (`sohier/large-purchases`) covers the same CA procurement domain — exact column coverage may differ.

```bash
pip install kaggle
kaggle datasets download -d sohier/large-purchases-by-the-state-of-ca -p data/raw --unzip
# requires a kaggle.json / KAGGLE_USERNAME + KAGGLE_KEY
```

## CI / Quality Gate

Every push or pull request runs a [GitHub Actions](.github/workflows/ci.yml) workflow: a quality gate checks that English docs contain no Chinese, every referenced chart exists, and the bilingual README + index are all present; then `pytest` runs the test suite.

![CI](https://github.com/JLXYwjw/procurement-reconciliation/actions/workflows/ci.yml/badge.svg)
