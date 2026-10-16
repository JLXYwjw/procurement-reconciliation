# -*- coding: utf-8 -*-
"""Generate the visualization charts for the procurement report.

Reads the cleaned table and the ML outputs, and writes PNG charts under
assets/ that the HTML report embeds. Each chart answers one business question.
English labels only (font-safe) - this report is meant to be shown to hiring
managers / procurement stakeholders.
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "output")
ASSET_DIR = os.path.join(ROOT, "assets")
os.makedirs(ASSET_DIR, exist_ok=True)

BLUE = "#0ea5e9"    # sky-500 (primary data)
NAVY = "#0284c7"    # sky-600 (deep emphasis)
ORANGE = "#f59e0b"  # amber / golden (highlight)
GREEN = "#10b981"   # emerald (positive / competitive)
RED = "#f43f5e"     # rose (flag / alert)
GREY = "#94a3b8"    # slate-400 (neutral)
LIGHT = "#bae6fd"   # sky-200 (secondary)
SKY = "#7dd3fc"     # sky-300 (light data)


def _save(fig, name):
    path = os.path.join(ASSET_DIR, name)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("SAVED", os.path.basename(path))


df = pd.read_parquet(os.path.join(OUT_DIR, "procurement_clean.parquet"))
grand = float(df["total_price"].sum())
print("ROWS", len(df), "GRAND", round(grand, 2))

# --- 1) Monthly spend trend (fiscal-year year-end peaks) -------------------
mm = df.dropna(subset=["creation_date"]).set_index("creation_date")
mt = mm["total_price"].resample("MS").sum() / 1e9
fig, ax = plt.subplots(figsize=(10.5, 4.2))
ax.plot(mt.index, mt.values, marker="o", ms=3.5, lw=1.6, color=BLUE)
ax.fill_between(mt.index, mt.values, color=BLUE, alpha=0.10)
peak = mt.idxmax()
ax.annotate(f"{mt.max():.0f}B\n{peak:%Y-%m}\ngiant med-settlement month",
            xy=(peak, mt.max()), xytext=(peak, mt.max() * 1.02),
            ha="center", fontsize=9, color=RED)
ax.set_title("Monthly Spend ($B) — lumpy, dominated by a few giant payments",
             fontsize=11, fontweight="bold")
ax.set_ylabel("Spend ($B)")
ax.grid(alpha=0.3, lw=0.5)
_save(fig, "monthly_trend.png")

# --- 2) Top-10 suppliers ----------------------------------------------------
g = df.groupby("supplier_name")["total_price"].sum().sort_values(ascending=False).head(10) / 1e9
fig, ax = plt.subplots(figsize=(9, 4.4))
colors = [NAVY if i < 3 else BLUE for i in range(len(g))]
ax.barh(g.index[::-1][:8][::-1] if False else g.index[::-1],
        g.values[::-1], color=colors[::-1])
# shorten long names for readability
short = [n if len(n) <= 34 else n[:33] + "…" for n in g.index[::-1]]
ax.set_yticks(range(len(g)))
ax.set_yticklabels(short, fontsize=8.5)
ax.set_title("Top-10 Suppliers by Spend ($B)  — 41.4% of total", fontsize=12, fontweight="bold")
ax.set_xlabel("Spend ($B)")
ax.grid(axis="x", alpha=0.3, lw=0.5)
_save(fig, "top10_suppliers.png")

# --- 3) Department breakdown ------------------------------------------------
dep = df.groupby("department")["total_price"].sum().sort_values(ascending=False).head(10)
dep_share = dep / grand
fig, ax = plt.subplots(figsize=(9, 4.6))
labels = dep.index[::-1]
vals = dep.values[::-1] / 1e9
short = [n.replace("Department of ", "").replace(", Department of", "")
         for n in labels]
short = [n if len(n) <= 26 else n[:25] + "…" for n in short]
ax.barh(range(len(labels)), vals, color=[NAVY if s > 0.1 else BLUE
                                         for s in dep_share.values[::-1]])
ax.set_yticks(range(len(labels)))
ax.set_yticklabels(short, fontsize=9)
ax.set_title("Spend by Department ($B)", fontsize=12, fontweight="bold")
ax.set_xlabel("Spend ($B)")
for i, s in enumerate(dep_share.values[::-1]):
    ax.text(vals[i] + 0.4, i, f"{s*100:.1f}%", va="center", fontsize=8, color=GREY)
ax.grid(axis="x", alpha=0.3, lw=0.5)
_save(fig, "department.png")

# --- 4) UNSPSC segment (horizontal bars, unambiguous labels) ----------------
seg = df.groupby("segment")["total_price"].sum().sort_values(ascending=False).head(8)
seg_share = seg / grand
fig, ax = plt.subplots(figsize=(8.5, 4.4))
labels = seg.index[::-1]
vals = seg.values[::-1] / 1e9
shares = seg_share.values[::-1]
colors = [ORANGE if l == "85" else GREY for l in labels]
ax.barh(range(len(labels)), vals, color=colors)
ax.set_yticks(range(len(labels)))
ax.set_yticklabels([f"Segment {l}" for l in labels], fontsize=10)
for i, (v, s) in enumerate(zip(vals, shares)):
    hi = labels[i] == "85"
    ax.text(v + 0.5, i, f"${v:.1f}B · {s*100:.1f}%", va="center", fontsize=9,
            color=NAVY if hi else GREY, fontweight="bold" if hi else "normal")
ax.set_title("Top UNSPSC Segments by Spend ($B) — segment 85 (healthcare) = 73.9%",
             fontsize=11, fontweight="bold")
ax.set_xlabel("Spend ($B)")
ax.grid(axis="x", alpha=0.3, lw=0.5)
_save(fig, "category_segment.png")

# --- 5) Acquisition-method control class (competitive / exempt / flexible) --
mc = df.dropna(subset=["method_class"]).groupby("method_class")["total_price"].sum()
fig, ax = plt.subplots(figsize=(8, 4.2))
order = ["competitive", "exempt", "flexible"]
present = [m for m in order if m in mc.index]
vals = [mc[m] / 1e9 for m in present]
ax.bar(present, vals, color=[GREEN, GREY, ORANGE])
for i, v in enumerate(vals):
    ax.text(i, v + 1, f"${v:.0f}B", ha="center", fontsize=10, fontweight="bold")
ax.set_title("Spend by Method Control Class ($B)", fontsize=12, fontweight="bold")
ax.set_ylabel("Spend ($B)")
ax.grid(axis="y", alpha=0.3, lw=0.5)
_save(fig, "method_control.png")

# --- 6) Supplier segmentation (KMeans tiers, strategic split) ----------------
sup = pd.read_parquet(os.path.join(OUT_DIR, "supplier_segmentation.parquet"))
tier = sup.groupby("tier").agg(
    suppliers=("supplier_name", "count"),
    spend=("total_spend", "sum"),
    med_years=("years_active", "median"),
)
tier["spend"] = tier["spend"] / 1e9
order = ["tail", "regular", "oneoff_large", "core_strategic"]
labels = {
    "core_strategic": "Core (recurring)",
    "oneoff_large": "One-off / large",
    "regular": "Regular",
    "tail": "Tail",
}
colors = {"core_strategic": NAVY, "oneoff_large": ORANGE, "regular": BLUE, "tail": LIGHT}
fig, ax = plt.subplots(figsize=(8.6, 4.4))
for i, t in enumerate(order):
    ax.barh(i, tier["spend"][t], color=colors[t])
ax.set_yticks(range(len(order)))
ax.set_yticklabels([labels[t] for t in order], fontsize=10)
for i, t in enumerate(order):
    share = tier["spend"][t] / tier["spend"].sum() * 100
    ax.text(tier["spend"][t] + 0.4, i,
            f"${tier['spend'][t]:.1f}B · {int(tier['suppliers'][t]):,} vendors · {share:.1f}%",
            va="center", fontsize=9)
ax.set_title("Supplier Segmentation — 68.8% of spend is one-off/large, 30.1% recurring core",
             fontsize=11, fontweight="bold")
ax.set_xlabel("Spend ($B)")
ax.grid(axis="x", alpha=0.3, lw=0.5)
_save(fig, "supplier_tier.png")

# --- 7) Healthcare concentration (Health Care Services vs rest) -------------
dep_sum = df.groupby("department")["total_price"].sum()
hc = dep_sum.get("Health Care Services, Department of", 0) / grand
rest = 1 - hc
fig, ax = plt.subplots(figsize=(7.4, 3.8))
ax.pie([hc, rest], labels=["Health Care Services", "All other departments"],
       autopct="%1.1f%%", colors=[ORANGE, LIGHT], startangle=90,
       textprops={"fontsize": 10})
ax.set_title("Health Care Services = 66.0% of total spend", fontsize=12, fontweight="bold")
_save(fig, "healthcare_concentration.png")

# --- 8) Unit-cost outliers: they are large but legitimate buys --------------
gg = pd.read_parquet(os.path.join(OUT_DIR, "goods_anomaly.parquet"))
gg["unit_cost"] = gg["total_price"] / gg["quantity"]
fig, ax = plt.subplots(figsize=(9, 4.2))
norm = gg[~gg["goods_outlier"]]
out = gg[gg["goods_outlier"]]
ax.scatter(norm["quantity"], norm["unit_cost"], s=4, alpha=0.25, color=BLUE,
           label=f"normal ({len(norm):,})")
ax.scatter(out["quantity"], out["unit_cost"], s=6, alpha=0.6, color=RED,
           label=f"flagged ({len(out):,})")
ax.set_xscale("log")
ax.set_yscale("log")
ax.set_xlabel("Quantity (log)")
ax.set_ylabel("Unit cost $ (log)")
ax.set_title("Unit-cost Outliers — mostly large but legitimate vehicle/medical buys",
             fontsize=11, fontweight="bold")
ax.legend(fontsize=8)
ax.grid(alpha=0.3, lw=0.4)
_save(fig, "unit_cost_outliers.png")

print("DONE")
