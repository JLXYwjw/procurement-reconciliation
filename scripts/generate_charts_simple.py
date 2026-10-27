# -*- coding: utf-8 -*-
"""
采购报告图表生成（英文版） —— 基础可读版（generate_charts_simple.py）
=====================================================================
这个文件做的事，和原版 generate_charts.py 完全一样：
  读入清洗后的采购数据和供应商分层结果，生成 8 张 PNG 图表，
  存到 assets/ 目录，供 HTML 报告嵌入。

每张图回答一个业务问题，标签全英文（面向招聘经理和采购方干系人）。

运行方式（和原版一样）：
    python scripts/generate_charts_simple.py
"""

import os

import matplotlib
matplotlib.use("Agg")  # 不弹窗，直接存文件
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# ------------------------------------------------------------------
# 0. 路径和配色配置
# ------------------------------------------------------------------
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "data", "output")
ASSET_DIR = os.path.join(ROOT, "assets")
os.makedirs(ASSET_DIR, exist_ok=True)

# 配色：主色是天蓝系，警示用砖红
BLUE = "#0ea5e9"    # sky-500（主数据色）
NAVY = "#0284c7"    # sky-600（强调色）
ORANGE = "#f59e0b"  # 琥珀色（高亮）
GREEN = "#10b981"   # 翡翠绿（正面/竞争性）
RED = "#f43f5e"     # 玫瑰红（警示）
GREY = "#94a3b8"    # 石板灰（中性）
LIGHT = "#bae6fd"   # 浅天蓝（次要）
SKY = "#7dd3fc"     # 天空蓝（浅色数据）


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
print("ROWS", len(df), "GRAND", round(grand, 2))

# ------------------------------------------------------------------
# 2. 月度支出趋势图
# ------------------------------------------------------------------
# 去掉 creation_date 为空的行，按月份重采样求和
mm = df.dropna(subset=["creation_date"]).set_index("creation_date")
mt = mm["total_price"].resample("MS").sum() / 1e9  # 转成十亿美元

fig, ax = plt.subplots(figsize=(10.5, 4.2))
ax.plot(mt.index, mt.values, marker="o", ms=3.5, lw=1.6, color=BLUE)
ax.fill_between(mt.index, mt.values, color=BLUE, alpha=0.10)

# 标注支出最高的那个月
peak = mt.idxmax()
ax.annotate(f"{mt.max():.0f}B\n{peak:%Y-%m}\ngiant med-settlement month",
            xy=(peak, mt.max()), xytext=(peak, mt.max() * 1.02),
            ha="center", fontsize=9, color=RED)

ax.set_title("Monthly Spend ($B) — lumpy, dominated by a few giant payments",
             fontsize=11, fontweight="bold")
ax.set_ylabel("Spend ($B)")
ax.grid(alpha=0.3, lw=0.5)
save_fig(fig, "monthly_trend.png")

# ------------------------------------------------------------------
# 3. Top10 供应商条形图
# ------------------------------------------------------------------
g = df.groupby("supplier_name")["total_price"].sum().sort_values(ascending=False).head(10)
g = g / 1e9

fig, ax = plt.subplots(figsize=(9, 4.4))

# 前3名用深色，其余用浅色（原版用列表推导式，这里改成 for 循环）
colors = []
for i in range(len(g)):
    if i < 3:
        colors.append(NAVY)
    else:
        colors.append(BLUE)

ax.barh(g.index[::-1], g.values[::-1], color=colors[::-1])

# 长名字截断（超过34个字符截断加省略号）
short_labels = []
for n in g.index[::-1]:
    if len(n) <= 34:
        short_labels.append(n)
    else:
        short_labels.append(n[:33] + "…")

ax.set_yticks(range(len(g)))
ax.set_yticklabels(short_labels, fontsize=8.5)
ax.set_title("Top-10 Suppliers by Spend ($B)  — 41.4% of total",
             fontsize=12, fontweight="bold")
ax.set_xlabel("Spend ($B)")
ax.grid(axis="x", alpha=0.3, lw=0.5)
save_fig(fig, "top10_suppliers.png")

# ------------------------------------------------------------------
# 4. 部门支出条形图
# ------------------------------------------------------------------
dep = df.groupby("department")["total_price"].sum().sort_values(ascending=False).head(10)
dep_share = dep / grand

fig, ax = plt.subplots(figsize=(9, 4.6))
labels = dep.index[::-1]
vals = dep.values[::-1] / 1e9

# 去掉部门名里的"Department of "前缀，太长的截断
short_labels = []
for n in labels:
    n2 = n.replace("Department of ", "").replace(", Department of", "")
    if len(n2) <= 26:
        short_labels.append(n2)
    else:
        short_labels.append(n2[:25] + "…")

# 占比 > 10% 的部门用深色
bar_colors = []
for s in dep_share.values[::-1]:
    if s > 0.1:
        bar_colors.append(NAVY)
    else:
        bar_colors.append(BLUE)

ax.barh(range(len(labels)), vals, color=bar_colors)
ax.set_yticks(range(len(labels)))
ax.set_yticklabels(short_labels, fontsize=9)
ax.set_title("Spend by Department ($B)", fontsize=12, fontweight="bold")
ax.set_xlabel("Spend ($B)")

# 在条上标注百分比
for i, s in enumerate(dep_share.values[::-1]):
    ax.text(vals[i] + 0.4, i, f"{s*100:.1f}%", va="center", fontsize=8, color=GREY)

ax.grid(axis="x", alpha=0.3, lw=0.5)
save_fig(fig, "department.png")

# ------------------------------------------------------------------
# 5. UNSPSC 品类段条形图
# ------------------------------------------------------------------
seg = df.groupby("segment")["total_price"].sum().sort_values(ascending=False).head(8)
seg_share = seg / grand

fig, ax = plt.subplots(figsize=(8.5, 4.4))
labels = seg.index[::-1]
vals = seg.values[::-1] / 1e9
shares = seg_share.values[::-1]

# 段85（医疗）用橙色高亮，其余灰色
seg_colors = []
for l in labels:
    if l == "85":
        seg_colors.append(ORANGE)
    else:
        seg_colors.append(GREY)

ax.barh(range(len(labels)), vals, color=seg_colors)
ax.set_yticks(range(len(labels)))

# y轴标签：Segment XX
ytick_labels = []
for l in labels:
    ytick_labels.append(f"Segment {l}")
ax.set_yticklabels(ytick_labels, fontsize=10)

# 在条上标注金额和占比
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

ax.set_title("Top UNSPSC Segments by Spend ($B) — segment 85 (healthcare) = 73.9%",
             fontsize=11, fontweight="bold")
ax.set_xlabel("Spend ($B)")
ax.grid(axis="x", alpha=0.3, lw=0.5)
save_fig(fig, "category_segment.png")

# ------------------------------------------------------------------
# 6. 采购方式控制类别柱状图
# ------------------------------------------------------------------
mc = df.dropna(subset=["method_class"]).groupby("method_class")["total_price"].sum()

fig, ax = plt.subplots(figsize=(8, 4.2))
order = ["competitive", "exempt", "flexible"]

# 只保留实际存在的类别
present = []
for m in order:
    if m in mc.index:
        present.append(m)

vals = []
for m in present:
    vals.append(mc[m] / 1e9)

# 竞争性=绿，豁免=灰，灵活=橙
method_colors = [GREEN, GREY, ORANGE]
ax.bar(present, vals, color=method_colors[:len(present)])

# 在柱顶标注金额
for i, v in enumerate(vals):
    ax.text(i, v + 1, f"${v:.0f}B", ha="center", fontsize=10, fontweight="bold")

ax.set_title("Spend by Method Control Class ($B)", fontsize=12, fontweight="bold")
ax.set_ylabel("Spend ($B)")
ax.grid(axis="y", alpha=0.3, lw=0.5)
save_fig(fig, "method_control.png")

# ------------------------------------------------------------------
# 7. 供应商分层条形图
# ------------------------------------------------------------------
sup = pd.read_parquet(os.path.join(OUT_DIR, "supplier_segmentation.parquet"))
tier = sup.groupby("tier").agg(
    suppliers=("supplier_name", "count"),
    spend=("total_spend", "sum"),
    med_years=("years_active", "median"),
)
tier["spend"] = tier["spend"] / 1e9

tier_order = ["tail", "regular", "oneoff_large", "core_strategic"]
tier_labels = {
    "core_strategic": "Core (recurring)",
    "oneoff_large": "One-off / large",
    "regular": "Regular",
    "tail": "Tail",
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

# 在条上标注金额、供应商数、占比
for i, t in enumerate(tier_order):
    spend_val = tier["spend"][t]
    n_sup = int(tier["suppliers"][t])
    share = spend_val / tier["spend"].sum() * 100
    ax.text(spend_val + 0.4, i,
            f"${spend_val:.1f}B · {n_sup:,} vendors · {share:.1f}%",
            va="center", fontsize=9)

ax.set_title("Supplier Segmentation — 68.8% of spend is one-off/large, 30.1% recurring core",
             fontsize=11, fontweight="bold")
ax.set_xlabel("Spend ($B)")
ax.grid(axis="x", alpha=0.3, lw=0.5)
save_fig(fig, "supplier_tier.png")

# ------------------------------------------------------------------
# 8. 医疗支出集中度饼图
# ------------------------------------------------------------------
dep_sum = df.groupby("department")["total_price"].sum()
hc = dep_sum.get("Health Care Services, Department of", 0) / grand
rest = 1 - hc

fig, ax = plt.subplots(figsize=(7.4, 3.8))
ax.pie([hc, rest], labels=["Health Care Services", "All other departments"],
       autopct="%1.1f%%", colors=[ORANGE, LIGHT], startangle=90,
       textprops={"fontsize": 10})
ax.set_title("Health Care Services = 66.0% of total spend",
             fontsize=12, fontweight="bold")
save_fig(fig, "healthcare_concentration.png")

# ------------------------------------------------------------------
# 9. 分层 × 采购方式 堆叠条形图
# ------------------------------------------------------------------
# 原版说明：异常检测图已移除（MAD 标记率26%不可靠），goods_anomaly.parquet 保留作为可复现证据
dfm = df.merge(sup[["supplier_name", "tier"]], on="supplier_name", how="left")

tiers = ["core_strategic", "oneoff_large", "regular", "tail"]
classes = ["competitive", "exempt", "flexible"]

sh = dfm.groupby(["tier", "method_class"])["total_price"].sum().unstack(fill_value=0)
sh = sh.div(sh.sum(axis=1), axis=0)
sh = sh.reindex(tiers).reindex(classes, axis=1).fillna(0)

fig, ax = plt.subplots(figsize=(9, 4.2))
bottom = np.zeros(len(tiers))
colors_m = {"competitive": GREEN, "exempt": GREY, "flexible": ORANGE}

for c in classes:
    vals = sh[c].values
    ax.bar(tiers, vals, bottom=bottom, color=colors_m[c], label=c)
    bottom = bottom + vals

# 在中间标注"豁免"占比
for i, t in enumerate(tiers):
    pct = sh["exempt"][t] * 100
    ax.text(i, 0.55, f"exempt {pct:.0f}%", ha="center", va="center",
            fontsize=9, fontweight="bold")

ax.set_title("Method control share by tier — exempt concentrates in recurring core, not one-off",
             fontsize=10.5, fontweight="bold")
ax.legend(fontsize=8)
ax.set_ylabel("Share of tier spend")
ax.grid(axis="y", alpha=0.3, lw=0.5)
save_fig(fig, "method_by_tier.png")

print("DONE")
