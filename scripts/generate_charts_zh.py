# -*- coding: utf-8 -*-
"""为采购项目生成中文版图表（用于中文 README 与中文网页）。
基于 output/ 同一份清洗数据与供应商分层，输出 assets/*_zh.png。
"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC"]
plt.rcParams["axes.unicode_minus"] = False

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "output")
ASSET_DIR = os.path.join(ROOT, "assets")
os.makedirs(ASSET_DIR, exist_ok=True)

BLUE = "#0ea5e9"; NAVY = "#0284c7"; ORANGE = "#f59e0b"
GREEN = "#10b981"; GREY = "#94a3b8"; LIGHT = "#bae6fd"

def _save(fig, name):
    path = os.path.join(ASSET_DIR, name)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("SAVED", os.path.basename(path))

df = pd.read_parquet(os.path.join(OUT_DIR, "procurement_clean.parquet"))
grand = float(df["total_price"].sum())

# 1 月度支出趋势
mm = df.dropna(subset=["creation_date"]).set_index("creation_date")
mt = mm["total_price"].resample("MS").sum() / 1e9
fig, ax = plt.subplots(figsize=(10.5, 4.2))
ax.plot(mt.index, mt.values, marker="o", ms=3.5, lw=1.6, color=BLUE)
ax.fill_between(mt.index, mt.values, color=BLUE, alpha=0.10)
peak = mt.idxmax()
ax.annotate(f"{mt.max():.0f}B\n{peak:%Y-%m}\n巨额医疗结算月",
            xy=(peak, mt.max()), xytext=(peak, mt.max()*1.02), ha="center", fontsize=9, color="#f43f5e")
ax.set_title("月度支出（$B）—— 块状、由少数巨额支付主导", fontsize=11, fontweight="bold")
ax.set_ylabel("支出（$B）")
ax.grid(alpha=0.3, lw=0.5)
_save(fig, "monthly_trend_zh.png")

# 2 头部供应商
g = df.groupby("supplier_name")["total_price"].sum().sort_values(ascending=False).head(10) / 1e9
fig, ax = plt.subplots(figsize=(9, 4.4))
colors = [NAVY if i < 3 else BLUE for i in range(len(g))]
ax.barh(g.index[::-1], g.values[::-1], color=colors[::-1])
short = [n if len(n) <= 34 else n[:33] + "…" for n in g.index[::-1]]
ax.set_yticks(range(len(g)))
ax.set_yticklabels(short, fontsize=8.5)
ax.set_title("头部供应商支出（$B）—— 占总额 41.4%", fontsize=12, fontweight="bold")
ax.set_xlabel("支出（$B）")
ax.grid(axis="x", alpha=0.3, lw=0.5)
_save(fig, "top10_suppliers_zh.png")

# 3 部门支出
dep = df.groupby("department")["total_price"].sum().sort_values(ascending=False).head(10)
dep_share = dep / grand
fig, ax = plt.subplots(figsize=(9, 4.6))
labels = dep.index[::-1]
vals = dep.values[::-1] / 1e9
short = [n.replace("Department of ", "").replace(", Department of", "") for n in labels]
short = [n if len(n) <= 26 else n[:25] + "…" for n in short]
ax.barh(range(len(labels)), vals, color=[NAVY if s > 0.1 else BLUE for s in dep_share.values[::-1]])
ax.set_yticks(range(len(labels)))
ax.set_yticklabels(short, fontsize=9)
ax.set_title("各部门支出（$B）", fontsize=12, fontweight="bold")
ax.set_xlabel("支出（$B）")
for i, s in enumerate(dep_share.values[::-1]):
    ax.text(vals[i]+0.4, i, f"{s*100:.1f}%", va="center", fontsize=8, color=GREY)
ax.grid(axis="x", alpha=0.3, lw=0.5)
_save(fig, "department_zh.png")

# 4 类目段
seg = df.groupby("segment")["total_price"].sum().sort_values(ascending=False).head(8)
seg_share = seg / grand
fig, ax = plt.subplots(figsize=(8.5, 4.4))
labels = seg.index[::-1]; vals = seg.values[::-1] / 1e9; shares = seg_share.values[::-1]
colors = [ORANGE if l == "85" else GREY for l in labels]
ax.barh(range(len(labels)), vals, color=colors)
ax.set_yticks(range(len(labels)))
ax.set_yticklabels([f"Segment {l}" for l in labels], fontsize=10)
for i, (v, s) in enumerate(zip(vals, shares)):
    hi = labels[i] == "85"
    ax.text(v+0.5, i, f"${v:.1f}B · {s*100:.1f}%", va="center", fontsize=9,
            color=NAVY if hi else GREY, fontweight="bold" if hi else "normal")
ax.set_title("头部 UNSPSC 类目段支出（$B）—— 段 85（医疗）= 73.9%", fontsize=11, fontweight="bold")
ax.set_xlabel("支出（$B）")
ax.grid(axis="x", alpha=0.3, lw=0.5)
_save(fig, "category_segment_zh.png")

# 5 采购方式管控
mc = df.dropna(subset=["method_class"]).groupby("method_class")["total_price"].sum()
fig, ax = plt.subplots(figsize=(8, 4.2))
order = ["competitive", "exempt", "flexible"]
present = [m for m in order if m in mc.index]
vals = [mc[m]/1e9 for m in present]
names = {"competitive": "竞争", "exempt": "豁免", "flexible": "灵活"}
ax.bar([names[m] for m in present], vals, color=[GREEN, GREY, ORANGE])
for i, v in enumerate(vals):
    ax.text(i, v+1, f"${v:.0f}B", ha="center", fontsize=10, fontweight="bold")
ax.set_title("各采购方式控制类别支出（$B）", fontsize=12, fontweight="bold")
ax.set_ylabel("支出（$B）")
ax.grid(axis="y", alpha=0.3, lw=0.5)
_save(fig, "method_control_zh.png")

# 6 供应商分层
sup = pd.read_parquet(os.path.join(OUT_DIR, "supplier_segmentation.parquet"))
tier = sup.groupby("tier").agg(suppliers=("supplier_name", "count"), spend=("total_spend", "sum"))
tier["spend"] = tier["spend"] / 1e9
order = ["tail", "regular", "oneoff_large", "core_strategic"]
labels = {"core_strategic": "核心（长期）", "oneoff_large": "一次性 / 大额", "regular": "常规", "tail": "长尾"}
colors = {"core_strategic": NAVY, "oneoff_large": ORANGE, "regular": BLUE, "tail": LIGHT}
fig, ax = plt.subplots(figsize=(8.6, 4.4))
for i, t in enumerate(order):
    ax.barh(i, tier["spend"][t], color=colors[t])
ax.set_yticks(range(len(order)))
ax.set_yticklabels([labels[t] for t in order], fontsize=10)
for i, t in enumerate(order):
    share = tier["spend"][t] / tier["spend"].sum() * 100
    ax.text(tier["spend"][t]+0.4, i, f"${tier['spend'][t]:.1f}B · {int(tier['suppliers'][t]):,} 家 · {share:.1f}%",
            va="center", fontsize=9)
ax.set_title("供应商分层 —— 68.8% 支出来自一次性/大额，30.1% 为长期核心", fontsize=11, fontweight="bold")
ax.set_xlabel("支出（$B）")
ax.grid(axis="x", alpha=0.3, lw=0.5)
_save(fig, "supplier_tier_zh.png")

# 7 医疗支出集中度
dep_sum = df.groupby("department")["total_price"].sum()
hc = dep_sum.get("Health Care Services, Department of", 0) / grand
rest = 1 - hc
fig, ax = plt.subplots(figsize=(7.4, 3.8))
ax.pie([hc, rest], labels=["Health Care Services", "其他所有部门"],
       autopct="%1.1f%%", colors=[ORANGE, LIGHT], startangle=90, textprops={"fontsize": 10})
ax.set_title("Health Care Services 占总支出 66.0%", fontsize=12, fontweight="bold")
_save(fig, "healthcare_concentration_zh.png")

# 8 分层 × 采购方式
dfm = df.merge(sup[["supplier_name", "tier"]], on="supplier_name", how="left")
tiers = ["core_strategic", "oneoff_large", "regular", "tail"]
classes = ["competitive", "exempt", "flexible"]
sh = dfm.groupby(["tier", "method_class"])["total_price"].sum().unstack(fill_value=0)
sh = sh.div(sh.sum(axis=1), axis=0).reindex(tiers).reindex(classes, axis=1).fillna(0)
fig, ax = plt.subplots(figsize=(9, 4.2))
bottom = np.zeros(len(tiers))
colors_m = {"competitive": GREEN, "exempt": GREY, "flexible": ORANGE}
for c in classes:
    vals = sh[c].values
    ax.bar(tiers, vals, bottom=bottom, color=colors_m[c], label={"competitive": "竞争", "exempt": "豁免", "flexible": "灵活"}[c])
    bottom += vals
for i, t in enumerate(tiers):
    pct = sh["exempt"][t] * 100
    ax.text(i, 0.55, f"豁免 {pct:.0f}%", ha="center", va="center", fontsize=9, fontweight="bold")
ax.set_title("各分层采购方式占比 —— 豁免集中于长期核心，而非一次性/大额", fontsize=10.5, fontweight="bold")
ax.legend(fontsize=8)
ax.set_ylabel("分层支出占比")
ax.grid(axis="y", alpha=0.3, lw=0.5)
_save(fig, "method_by_tier_zh.png")

print("DONE")
