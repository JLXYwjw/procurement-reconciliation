# -*- coding: utf-8 -*-
"""Machine-learning steps for the procurement project (v2, business-focused).

Lessons from v1: treating total spend as an anomaly feature flags huge but
legitimate medical contracts (83% of spend) -> meaningless and indefensible.

v2 design:
- Supplier segmentation (KMeans): WHICH suppliers deserve negotiation.
- Unit-cost anomaly detection ONLY on goods purchases (comparable unit prices),
  per UNSPSC segment (MAD robust rule) -> a review list of suspicious lines.
- Flexible-method purchases listed as a separate process-review list.
- Service contracts (quantity=1, price = total) are NOT scored (not comparable).
"""
import os

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "data", "output")
df = pd.read_parquet(os.path.join(ROOT, "data", "output", "procurement_clean.parquet"))

print("ACQUISITION_TYPE_DIST")
print(df["acquisition_type"].value_counts(dropna=False).to_string())

# ---------------------------------------------------------------------------
# 1) Unit-cost anomaly detection on goods only (comparable unit prices)
# ---------------------------------------------------------------------------
goods = df.dropna(subset=["total_price", "quantity"]).copy()
goods = goods[goods["quantity"] > 0].copy()
goods["unit_cost"] = goods["total_price"] / goods["quantity"]
goods = goods[goods["unit_cost"] > 0].copy()

# goods vs services split by acquisition type (string contains 'Good')
goods["is_goods"] = goods["acquisition_type"].astype(str).str.contains("Good", case=False, na=False)
print("\nGOODS vs SERVICES (lines)")
print(goods["is_goods"].value_counts().to_string())

gg = goods[goods["is_goods"] & (goods["quantity"] >= 2)].copy()
# per-segment robust MAD outlier on unit cost (needs enough samples per segment)
seg_stats = (
    gg.groupby("segment")["unit_cost"]
    .agg(median="median", n="count")
    .reset_index()
)
seg_stats["mad"] = gg.groupby("segment")["unit_cost"].apply(
    lambda s: (s - s.median()).abs().median()
).reset_index(drop=True)
seg_stats = seg_stats[seg_stats["n"] >= 20].reset_index(drop=True)
gg = gg.merge(seg_stats[["segment", "median", "mad"]], on="segment", how="left")
gg = gg.dropna(subset=["median", "mad"]).copy()
gg["unit_cost_dev"] = (gg["unit_cost"] - gg["median"]) / gg["mad"].replace(0, np.nan)
gg["goods_outlier"] = gg["unit_cost_dev"] > 3

n_out = int(gg["goods_outlier"].sum())
print("\nGOODS_LINES_COMPARABLE", len(gg), "| UNIT_COST_OUTLIERS", n_out)
print("OUTLIER_SPEND", round(float(gg.loc[gg["goods_outlier"], "total_price"].sum()), 2))

top = gg[gg["goods_outlier"]].sort_values("total_price", ascending=False)
print("\nTOP_GOODS_OUTLIERS (by spend)")
print(top[["department", "supplier_name", "item_name", "quantity",
           "unit_price", "total_price", "segment", "method_class"]]
      .head(15).to_string())

# ---------------------------------------------------------------------------
# 2) Flexible-method purchases -> process-review list (business rule)
# ---------------------------------------------------------------------------
flex = df[df["method_class"] == "flexible"].copy()
print("\nFLEXIBLE_METHOD_SPEND", round(float(flex["total_price"].sum()), 2),
      "| LINES", len(flex))
fm = flex.groupby("acquisition_method")["total_price"].agg(["sum", "count"]).sort_values("sum", ascending=False)
print(fm.head(10).to_string())

# ---------------------------------------------------------------------------
# 3) Supplier segmentation is OWNED by supplier_cluster.py (v2, strategic
#    size x stickiness split). Removed here so ml_analysis does not overwrite
#    the v2 output with the old size-only split.
# ---------------------------------------------------------------------------

# persistence (anomaly + flexible lists only; segmentation owned elsewhere)
gg.to_parquet(os.path.join(OUT_DIR, "goods_anomaly.parquet"), index=False)
flex.to_parquet(os.path.join(OUT_DIR, "flexible_review.parquet"), index=False)
print("\nSAVED goods_anomaly / flexible_review")
