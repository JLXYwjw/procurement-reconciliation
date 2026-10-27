# -*- coding: utf-8 -*-
"""
采购报告图表生成（中文版） —— 基础可读版（generate_charts_zh_simple.py）
=====================================================================

  和英文版用同一份数据，生成中文版图表，输出 assets/*_zh.png，
  供中文 README 和中文网页使用。

运行方式：
    python scripts/generate_charts_zh_simple.py

English:
Procurement report charts, Chinese labels (plain, readable version).

Uses the same data as the English version but produces Chinese-labeled
charts, written to assets/*_zh.png for the Chinese README and the Chinese
web page.

Run:
    python scripts/generate_charts_zh_simple.py
"""

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# 中文字体配置
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC"]
plt.rcParams["axes.unicode_minus"] = False

# ------------------------------------------------------------------
# 0. 路径和配色配置
# ------------------------------------------------------------------
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "data", "output")
ASSET_DIR = os.path.join(ROOT, "assets")
os.makedirs(ASSET_DIR, exist_ok=True)

BLUE = "#0ea5e9"
NAVY = "#0284c7"
ORANGE = "#f59e0b"
GREEN = "#10b981"
GREY = "#94a3b8"
LIGHT = "#bae6fd"


# ------------------------------------------------------------------
# 工具函数：保存图片
# ------------------------------------------------------------------
def save_fig(fig, name):
    path = os.path.join(ASSET_DIR, name)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("SAVED", os.path.basename(path))


# ------------------------------------------------------------------
# 1. 读入数据
# ------------------------------------------------------------------
df = pd.read_parquet(os.path.join(OUT_DIR, "procurement_clean.parquet"))
grand = float(df["total_price"].sum())

# ------------------------------------------------------------------
# 2. 月度支出趋势
# ------------------------------------------------------------------
mm = df.dropna(subset=["creation_date"]).set_index("creation_date")
mt = mm["total_price"].resample("MS").sum() / 1e9

fig, ax = plt.subplots(figsize=(10.5, 4.2))
ax.plot(mt.index, mt.values, marker="o", ms=3.5, lw=1.6, color=BLUE)
ax.fill_between(mt.index, mt.values, color=BLUE, alpha=0.10)

peak = mt.idxmax()
ax.annotate(f"{mt.max():.0f}B\n{peak:%Y-%m}\n巨额医疗结算月",
            xy=(peak, mt.max()), xytext=(peak, mt.max() * 1.02),
            ha="center", fontsize=9, color="#f43f5e")

ax.set_title("月度支出（$B）—— 块状、由少数巨额支付主导", fontsize=11, fontweight="bold")
ax.set_ylabel("支出（$B）")
ax.grid(alpha=0.3, lw=0.5)
save_fig(fig, "monthly_trend_zh.png")

# ------------------------------------------------------------------
# 3. 头部供应商
# ------------------------------------------------------------------
g = df.groupby("supplier_name")["total_price"].sum().sort_values(ascending=False).head(10)
g = g / 1e9

fig, ax = plt.subplots(figsize=(9, 4.4))

colors = []
for i in range(len(g)):
    if i < 3:
        colors.append(NAVY)
    else:
        colors.append(BLUE)

ax.barh(g.index[::-1], g.values[::-1], color=colors[::-1])

short_labels = []
for n in g.index[::-1]:
    if len(n) <= 34:
        short_labels.append(n)
    else:
        short_labels.append(n[:33] + "…")

ax.set_yticks(range(len(g)))
ax.set_yticklabels(short_labels, fontsize=8.5)
ax.set_title("头部供应商支出（$B）—— 占总额 41.4%", fontsize=12, fontweight="bold")
ax.set_xlabel("支出（$B）")
ax.grid(axis="x", alpha=0.3, lw=0.5)
save_fig(fig, "top10_suppliers_zh.png")

# ------------------------------------------------------------------
# 4. 部门支出
# ------------------------------------------------------------------
dep = df.groupby("department")["total_price"].sum().sort_values(ascending=False).head(10)
dep_share = dep / grand

fig, ax = plt.subplots(figsize=(9, 4.6))
labels = dep.index[::-1]
vals = dep.values[::-1] / 1e9

short_labels = []
for n in labels:
    n2 = n.replace("Department of ", "").replace(", Department of", "")
    if len(n2) <= 26:
        short_labels.append(n2)
    else:
        short_labels.append(n2[:25] + "…")

bar_colors = []
for s in dep_share.values[::-1]:
    if s > 0.1:
        bar_colors.append(NAVY)
    else:
        bar_colors.append(BLUE)

ax.barh(range(len(labels)), vals, color=bar_colors)
ax.set_yticks(range(len(labels)))
ax.set_yticklabels(short_labels, fontsize=9)
ax.set_title("各部门支出（$B）", fontsize=12, fontweight="bold")
ax.set_xlabel("支出（$B）")

for i, s in enumerate(dep_share.values[::-1]):
    ax.text(vals[i] + 0.4, i, f"{s*100:.1f}%", va="center", fontsize=8, color=GREY)

ax.grid(axis="x", alpha=0.3, lw=0.5)
save_fig(fig, "department_zh.png")

# ------------------------------------------------------------------
# 5. 品类段
# ------------------------------------------------------------------
seg = df.groupby("segment")["total_price"].sum().sort_values(ascending=False).head(8)
seg_share = seg / grand

fig, ax = plt.subplots(figsize=(8.5, 4.4))
labels = seg.index[::-1]
vals = seg.values[::-1] / 1e9
shares = seg_share.values[::-1]

seg_colors = []
for l in labels:
    if l == "85":
        seg_colors.append(ORANGE)
    else:
        seg_colors.append(GREY)

ax.barh(range(len(labels)), vals, color=seg_colors)
ax.set_yticks(range(len(labels)))

ytick_labels = []
for l in labels:
    ytick_labels.append(f"Segment {l}")
ax.set_yticklabels(ytick_labels, fontsize=10)

for i in range(len(vals)):
    v = vals[i]
    s = shares[i]
    is_healthcare = labels[i] == "85"
    if is_healthcare:
        text_color = NAVY
        bold = "bold"
    else:
        text_color = GREY
        bold = "normal"
    ax.text(v + 0.5, i, f"${v:.1f}B · {s*100:.1f}%",
            va="center", fontsize=9, color=text_color, fontweight=bold)

ax.set_title("头部 UNSPSC 品类段支出（$B）—— 段 85（医疗）= 73.9%",
             fontsize=11, fontweight="bold")
ax.set_xlabel("支出（$B）")
ax.grid(axis="x", alpha=0.3, lw=0.5)
save_fig(fig, "category_segment_zh.png")

# ------------------------------------------------------------------
# 6. 采购方式控制
# ------------------------------------------------------------------
mc = df.dropna(subset=["method_class"]).groupby("method_class")["total_price"].sum()

fig, ax = plt.subplots(figsize=(8, 4.2))
order = ["competitive", "exempt", "flexible"]

present = []
for m in order:
    if m in mc.index:
        present.append(m)

vals = []
for m in present:
    vals.append(mc[m] / 1e9)

method_names = {"competitive": "竞争", "exempt": "豁免", "flexible": "灵活"}
method_colors = [GREEN, GREY, ORANGE]

x_labels = []
for m in present:
    x_labels.append(method_names[m])

ax.bar(x_labels, vals, color=method_colors[:len(present)])

for i, v in enumerate(vals):
    ax.text(i, v + 1, f"${v:.0f}B", ha="center", fontsize=10, fontweight="bold")

ax.set_title("各采购方式控制类别支出（$B）", fontsize=12, fontweight="bold")
ax.set_ylabel("支出（$B）")
ax.grid(axis="y", alpha=0.3, lw=0.5)
save_fig(fig, "method_control_zh.png")

# ------------------------------------------------------------------
# 7. 供应商分层
# ------------------------------------------------------------------
sup = pd.read_parquet(os.path.join(OUT_DIR, "supplier_segmentation.parquet"))
tier = sup.groupby("tier").agg(
    suppliers=("supplier_name", "count"),
    spend=("total_spend", "sum"),
)
tier["spend"] = tier["spend"] / 1e9

tier_order = ["tail", "regular", "oneoff_large", "core_strategic"]
tier_labels = {
    "core_strategic": "核心（长期）",
    "oneoff_large": "一次性 / 大额",
    "regular": "常规",
    "tail": "长尾",
}
tier_colors = {
    "core_strategic": NAVY,
    "oneoff_large": ORANGE,
    "regular": BLUE,
    "tail": LIGHT,
}

fig, ax = plt.subplots(figsize=(8.6, 4.4))
for i, t in enumerate(tier_order):
    ax.barh(i, tier["spend"][t], color=tier_colors[t])

ax.set_yticks(range(len(tier_order)))
ytick_labels = []
for t in tier_order:
    ytick_labels.append(tier_labels[t])
ax.set_yticklabels(ytick_labels, fontsize=10)

for i, t in enumerate(tier_order):
    spend_val = tier["spend"][t]
    n_sup = int(tier["suppliers"][t])
    share = spend_val / tier["spend"].sum() * 100
    ax.text(spend_val + 0.4, i,
            f"${spend_val:.1f}B · {n_sup:,} 家 · {share:.1f}%",
            va="center", fontsize=9)

ax.set_title("供应商分层 —— 68.8% 支出来自一次性/大额，30.1% 为长期核心",
             fontsize=11, fontweight="bold")
ax.set_xlabel("支出（$B）")
ax.grid(axis="x", alpha=0.3, lw=0.5)
save_fig(fig, "supplier_tier_zh.png")

# ------------------------------------------------------------------
# 8. 医疗支出集中度
# ------------------------------------------------------------------
dep_sum = df.groupby("department")["total_price"].sum()
hc = dep_sum.get("Health Care Services, Department of", 0) / grand
rest = 1 - hc

fig, ax = plt.subplots(figsize=(7.4, 3.8))
ax.pie([hc, rest], labels=["Health Care Services", "其他所有部门"],
       autopct="%1.1f%%", colors=[ORANGE, LIGHT], startangle=90,
       textprops={"fontsize": 10})
ax.set_title("Health Care Services 占总支出 66.0%", fontsize=12, fontweight="bold")
save_fig(fig, "healthcare_concentration_zh.png")

# ------------------------------------------------------------------
# 9. 分层 × 采购方式
# ------------------------------------------------------------------
dfm = df.merge(sup[["supplier_name", "tier"]], on="supplier_name", how="left")

tiers = ["core_strategic", "oneoff_large", "regular", "tail"]
classes = ["competitive", "exempt", "flexible"]

sh = dfm.groupby(["tier", "method_class"])["total_price"].sum().unstack(fill_value=0)
sh = sh.div(sh.sum(axis=1), axis=0)
sh = sh.reindex(tiers).reindex(classes, axis=1).fillna(0)

fig, ax = plt.subplots(figsize=(9, 4.2))
bottom = np.zeros(len(tiers))
colors_m = {"competitive": GREEN, "exempt": GREY, "flexible": ORANGE}
legend_names = {"competitive": "竞争", "exempt": "豁免", "flexible": "灵活"}

for c in classes:
    vals = sh[c].values
    ax.bar(tiers, vals, bottom=bottom, color=colors_m[c], label=legend_names[c])
    bottom = bottom + vals

for i, t in enumerate(tiers):
    pct = sh["exempt"][t] * 100
    ax.text(i, 0.55, f"豁免 {pct:.0f}%", ha="center", va="center",
            fontsize=9, fontweight="bold")

ax.set_title("各分层采购方式占比 —— 豁免集中于长期核心，而非一次性/大额",
             fontsize=10.5, fontweight="bold")
ax.legend(fontsize=8)
ax.set_ylabel("分层支出占比")
ax.grid(axis="y", alpha=0.3, lw=0.5)
save_fig(fig, "method_by_tier_zh.png")

print("DONE")
