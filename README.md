# Procurement & Purchase-Order Reconciliation Analysis

Analysis of a large, real CA statewide procurement extract to surface cost, concentration and control issues, ending in actionable recommendations.

**The business problem.** Procurement teams spend large sums with thousands of vendors but often cannot see where money concentrates, which purchases are uncontrolled (maverick / sole-source) and which line items carry anomalous unit prices. This project cleans a 346k-record procurement extract and quantifies those issues so purchasing can negotiate better and set controls.

## Status
- [x] Data inspection & cleaning (money `$`, dates, supplier names)
- [x] Initial metrics (total spend, PO/vendor counts, top-10 share, HHI, method & year distribution)
- [ ] Department / category / location breakdowns + monthly trend
- [ ] Machine learning: anomaly detection (Isolation Forest) + supplier segmentation (KMeans)
- [ ] Final HTML report (objective / cleaning / metrics / modeling / visualization / recommendations)

## Run
```bash
pip install -r requirements.txt
python scripts/clean_data.py
python scripts/analyze.py
```
