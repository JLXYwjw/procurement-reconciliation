# -*- coding: utf-8 -*-
"""Extended business metrics for the procurement project.

Covers: department, category (UNSPSC), location, monthly trend, and
an initial control/competition view of acquisition methods.
"""
import os

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
df = pd.read_parquet(os.path.join(ROOT, "output", "procurement_clean.parquet"))
grand = float(df["total_price"].sum())

print("===== DEPARTMENT (top 12 by spend) =====")
d = df.groupby("department")["total_price"].agg(["sum", "count"]).sort_values("sum", ascending=False)
d["share"] = d["sum"] / grand
print(d.head(12).to_string())

print("\n===== LOCATION (top 10 by spend) =====")
loc = df.groupby("zip_code")["total_price"].sum().sort_values(ascending=False)
print(loc.head(10).to_string())
print("LOCATIONS_WITH_VALUE", int(df["zip_code"].notna().sum()), "of", len(df))

print("\n===== UNSPSC (top 12 by spend) =====")
u = df.copy()
u["unspsc_segment"] = u["unspsc"].astype("Int64").astype(str).str[:2]
g = u.groupby("unspsc_segment")["total_price"].agg(["sum", "count"]).sort_values("sum", ascending=False)
g["share"] = g["sum"] / grand
print(g.head(12).to_string())
print("UNSPSC_PRESENT", int(u["unspsc"].notna().sum()), "of", len(u))

print("\n===== MONTHLY TREND (total price by month) =====")
mm = df.dropna(subset=["creation_date"]).set_index("creation_date")
mt = mm["total_price"].resample("MS").sum()
print(mt.to_string())

print("\n===== ACQUISITION METHOD: control view =====")
m = df.groupby("acquisition_method")["total_price"].agg(["sum", "count"]).sort_values("sum", ascending=False)
m["share"] = m["sum"] / grand
print(m.to_string())
print("CALCARD_YES_SHARE", round(float(df.loc[df["cal_card"] == "YES", "total_price"].sum()) / grand, 4) if "cal_card" in df.columns else "no col")
