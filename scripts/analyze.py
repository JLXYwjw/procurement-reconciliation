# -*- coding: utf-8 -*-
"""Business metrics from the cleaned procurement table.

Answers the first business questions: how much was spent, where money
concentrates (top-10 share, HHI), and how purchases are made.
"""
import os

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
df = pd.read_parquet(os.path.join(ROOT, "output", "procurement_clean.parquet"))

print("TOTAL_PRICE_SUM", round(float(df["total_price"].sum()), 2))
print("UNIQUE_PO", int(df["po_number"].nunique()))
print("UNIQUE_SUPPLIER", int(df["supplier_name"].nunique()))

g = df.groupby("supplier_name")["total_price"].sum().sort_values(ascending=False)
grand = float(df["total_price"].sum())
print("TOP10_SHARE", round(float(g.head(10).sum()) / grand, 4))
# Concentration: CR4 / CR8 are more legible than HHI for a payee-concentration
# story; HHI is kept as a secondary note.
cr4 = float(g.head(4).sum()) / grand
cr8 = float(g.head(8).sum()) / grand
print("CR4", round(cr4, 4))
print("CR8", round(cr8, 4))
share = g / g.sum()
print("HHI", round(float((share ** 2).sum()), 5))
print("TOP10_SUPPLIERS")
print(g.head(10).to_string())

m = df.groupby("acquisition_method")["total_price"].agg(["sum", "count"]).sort_values("sum", ascending=False)
print("METHOD_DIST")
print(m.head(12).to_string())

d = df.groupby("fiscal_year")["total_price"].agg(["sum", "count"]).sort_values("sum", ascending=False)
print("YEAR_DIST")
print(d.head(8).to_string())
