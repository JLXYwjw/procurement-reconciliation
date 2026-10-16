# Procurement Spend Reconciliation & Supplier Performance — Analysis Plan

## 1. Business Objectives (driven by the business)
A public-sector buyer (California statewide procurement, 2012–2015, real public data) needs to answer:
- **Spend reconciliation**: 346K purchases totaling $151B — where did it go: which departments, to which suppliers, for what, how much, and under which procurement method.
- **Concentration & risk**: Is spend too concentrated in a few categories/suppliers? What share is exempt or flexible procurement, and are there high-risk lines to review?
- **Supplier management**: Value-tier suppliers — which are strategic core, which can be negotiated down or re-sourced.
- **Delivery**: Actionable cost-recovery (negotiate the concentrated categories, review anomalous unit prices) and procurement-control recommendations.

## 2. Data
- Source: `data/raw/` (California open procurement data; Kaggle `sohier/large-purchases-by-the-state-of-ca`).
- Fields include: department, supplier, category (UNSPSC segment), procurement method, unit price, quantity, amount, date, etc.
- Time: 2012–2015.
- Known dirty features: messy date fields, amount/unit-price outliers, missing/inconsistent supplier and category codes.

## 3. Cleaning & Preprocessing
- Parse dates and fix dirty date fields; handle negative/malformed amounts and quantities.
- Derive: spend aggregates (by department/category/supplier/quarter), procurement-method flag, supplier profile features (spend, count, concentration, unit-price level).
- Unify units; treat missing values explicitly (keep or drop, documented).

## 4. Metrics
- Spend reconciliation: total spend; distribution and share by department / category (UNSPSC segment) / supplier; concentration (top N% of categories/suppliers).
- Procurement method: competitive vs exempt vs flexible spend (amount and share).
- Supplier: spend, line count, average unit price, dependency (share of single-supplier spend).
- Anomaly: outlier unit-price rate and related spend (potential overpayment).

## 5. Modeling (used only where the business needs it; explain principle/why/how)
- Objective A (supplier value tiers): **KMeans clustering** on spend scale/stability/concentration features to split suppliers into strategic / regular / tail tiers, guiding differentiated negotiation and risk control — chosen because clustering finds unsupervised groups and has low distributional assumptions.
- Objective B (unit-price outlier detection): **MAD / quantile robust thresholds** to flag purchases whose unit price deviates strongly within a category, as an audit / recovery cue — because amounts are heavy-tailed and non-normal, mean thresholds are unreliable; robust statistics are used.
- DL judgment: rows are many but the task is tabular/classification with no sequence or high-dimensional structure; DL adds little and is hard to explain — DL is not used, with the reason stated.
- Metrics: clustering silhouette / between-group differences; outlier count and related spend; honest limits on sample and definitions.

## 6. Visualizations (each chart Insight + Action)
- Spend concentration (segment share, highlighting healthcare at 73.9%).
- Procurement-method control (competitive/exempt/flexible spend comparison).
- Department/category spend distribution; top-supplier bars.
- Supplier tiers (KMeans bands).
- Monthly/quarterly spend trend.
- Unit-price outlier review list (related spend + deviation ratio).

## 7. Recommendations (landing)
- Cost recovery: negotiate the concentrated categories (healthcare) and key suppliers; review the outlier unit-price list for recovery.
- Method control: add process constraints where exempt/flexible spend is high.
- Suppliers: tiered operations — maintain strategic suppliers, consolidate/switch tail suppliers.
- Next step: line-level PO↔payment reconciliation needs bank statements, listed as an external data gap.

## 8. Deliverables
- Bilingual reports: `report/` (EN + ZH each) plus root `index.html` / `index.zh-CN.html`.
- Repo: scripts/tests/data(raw/output) + README + requirements; data/raw and parquet excluded from git; local git committed in small steps.
