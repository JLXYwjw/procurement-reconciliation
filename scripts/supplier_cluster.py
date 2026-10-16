# -*- coding: utf-8 -*-
"""Supplier segmentation v2 (strategic, not just top-spend).

v1 failure (self-review): KMeans on size-based features reproduced "sort by
total spend, take top-N" - core overlapped ~6-7/8 with top spenders, i.e. the
clustering added no insight over a Pareto cut.

v2 design - build features that a top-N cut CANNOT see:
  * category focus (top-segment share)  - specialised vs multi-category
  * department dependence (top-dept share) - single-payer reliance
  * stickiness (years active, order frequency) - recurring vs one-off
  * scale (total spend, avg order)
Then cluster and label by business role; verify that "core" is NOT simply the
top spenders.
"""
import os

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "output")
df = pd.read_parquet(os.path.join(OUT_DIR, "procurement_clean.parquet"))

# ---- build purpose-built features per supplier -----------------------------
sup = (
    df.groupby("supplier_name")
    .agg(
        total_spend=("total_price", "sum"),
        order_count=("po_number", "nunique"),
        line_count=("total_price", "count"),
        category_breadth=("segment", "nunique"),
        years_active=("fiscal_year", "nunique"),
    )
    .reset_index()
)

def _top_share(col):
    t = df.groupby(["supplier_name", col])["total_price"].sum().reset_index()
    t = t.sort_values("total_price", ascending=False).groupby("supplier_name").head(1)
    t = t.rename(columns={"total_price": "top_" + col + "_spend"})
    return sup.merge(t[["supplier_name", "top_" + col + "_spend"]], on="supplier_name", how="left")

sup = _top_share("segment").merge(_top_share("department")[["supplier_name", "top_department_spend"]],
                                  on="supplier_name", how="left")
sup["top_segment_share"] = sup["top_segment_spend"] / sup["total_spend"].replace(0, np.nan)
sup["top_department_share"] = sup["top_department_spend"] / sup["total_spend"].replace(0, np.nan)
sup["avg_order"] = sup["total_spend"] / sup["order_count"].replace(0, np.nan)
sup["order_freq"] = sup["order_count"] / sup["years_active"].replace(0, np.nan)

FEATS = ["total_spend", "avg_order", "order_count", "order_freq", "years_active"]
# NOTE: top_segment_share / top_department_share are intentionally NOT used as
# clustering features - for single-item/single-year suppliers they are always
# 1.0 (distorted) and they co-vary with spend, dragging the split back to a
# pure size cut. The separation we actually want is size x stickiness x
# frequency: big-but-one-off vs mid-but-recurring (strategic).
# skew handling before scaling
X = sup[FEATS].copy()
for c in ["total_spend", "avg_order", "order_count", "order_freq"]:
    X[c] = np.log1p(X[c].clip(lower=0))
X = X.fillna(0)
Xs = StandardScaler().fit_transform(X)

# ---- choose k ---------------------------------------------------------------
# Silhouette favors k=2, but that is one "big" blob + one "small" blob - useless
# for a negotiation story. We want a business-resolvable split:
#   core_strategic / key_account / regular / tail.
sil = {}
for k in range(2, 7):
    km = KMeans(n_clusters=k, n_init=10, random_state=42)
    lab = km.fit_predict(Xs)
    sil[k] = float(silhouette_score(Xs, lab))
print("SILHOUETTE", {k: round(v, 3) for k, v in sil.items()})
K = 4  # business choice, not silhouette argmax
print("CHOSEN_K", K)

km = KMeans(n_clusters=K, n_init=10, random_state=42)
sup["cluster"] = km.fit_predict(Xs)

# ---- label clusters by business role from their profile --------------------
prof = sup.groupby("cluster").agg(
    n=("supplier_name", "count"),
    spend=("total_spend", "sum"),
    med_spend=("total_spend", "median"),
    med_seg_share=("top_segment_share", "median"),
    med_dept_share=("top_department_share", "median"),
    med_years=("years_active", "median"),
    med_freq=("order_freq", "median"),
).sort_values("spend", ascending=False)
print("CLUSTER_PROFILE")
print(prof.to_string())

# spend-based rank label first, then refine
# Label by BUSINESS ROLE, not by spend rank:
#   core_strategic = the high-spend cluster whose suppliers RECUR (multi-year)
#   oneoff_large   = the high-spend cluster of single/low-frequency big buys
#   regular / tail = the rest by spend.
recur = prof[prof["med_years"] >= 2].sort_values("spend", ascending=False)
core_c = recur.index[0] if len(recur) else prof.sort_values("spend", ascending=False).index[0]
once = prof[prof["med_years"] < 2].sort_values("spend", ascending=False)
oneoff_c = once.index[0] if len(once) else None
rest = [c for c in prof.index if c not in (core_c, oneoff_c)]
rest = sorted(rest, key=lambda c: prof.loc[c, "spend"], reverse=True)
names = {core_c: "core_strategic"}
if oneoff_c is not None:
    names[oneoff_c] = "oneoff_large"
for i, c in enumerate(rest):
    names[c] = ["regular", "tail"][i]
prof["tier"] = pd.Series(names).reindex(prof.index)
label_map = names
sup["tier"] = sup["cluster"].map(label_map)

# ---- verify core is NOT just top spenders ----------------------------------
core = set(sup[sup["tier"] == "core_strategic"]["supplier_name"])
g = df.groupby("supplier_name")["total_price"].sum().sort_values(ascending=False)
overlap8 = len(core & set(g.head(8).index))
overlap10 = len(core & set(g.head(10).index))
overlap20 = len(core & set(g.head(20).index))
print("CORE_SIZE", len(core), "overlap top8", overlap8, "top10", overlap10, "top20", overlap20)
print("TOP20_CORE_MEMBERS", [n for n in g.head(20).index if n in core])
print("CORE_OUTSIDE_TOP20", sorted(set(core) - set(g.head(20).index))[:10])

ts = sup.groupby("tier").agg(suppliers=("supplier_name", "count"), spend=("total_spend", "sum"))
ts["spend_share"] = ts["spend"] / ts["spend"].sum()
print("TIER_SUMMARY")
print(ts.to_string())

sup.drop(columns=["cluster"]).to_parquet(os.path.join(OUT_DIR, "supplier_segmentation.parquet"), index=False)
print("SAVED supplier_segmentation.parquet")
