# -*- coding: utf-8 -*-
"""
扩展业务指标分析 —— 基础可读版（analyze_extended_simple.py）
===========================================================

  1. 部门支出排名（Top12）
  2. 邮编/地点支出排名（Top10）
  3. UNSPSC 品类段支出排名（Top12）
  4. 月度支出趋势
  5. 采购方式的控制视角（竞争性/豁免/灵活）
  6. 控制卡（cal_card）占比检查

区别只是：本文件故意用最朴素的写法，每一步都写清楚了在做什么。

运行方式：
    python scripts/analyze_extended_simple.py

English:
Extended business-metric analysis (plain, readable version).

Steps:
  1. Top-12 spend ranking by department
  2. Top-10 spend ranking by postal code / location
  3. Top-12 spend ranking by UNSPSC category segment
  4. Monthly spend trend
  5. Procurement-method control view (competitive / exempt / flexible)
  6. Control-card (cal_card) share check

The code is deliberately written in the simplest style so that every step
clearly shows what it does.

Run:
    python scripts/analyze_extended_simple.py
"""

import os

import pandas as pd

# ------------------------------------------------------------------
# 0. 路径配置
# ------------------------------------------------------------------
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ------------------------------------------------------------------
# 1. 读入清洗后的采购数据
# ------------------------------------------------------------------
parquet_path = os.path.join(ROOT, "data", "output", "procurement_clean.parquet")
df = pd.read_parquet(parquet_path)
grand = float(df["total_price"].sum())

# ------------------------------------------------------------------
# 2. 部门支出排名（Top12）
# ------------------------------------------------------------------
print("===== DEPARTMENT (top 12 by spend) =====")
d = df.groupby("department")["total_price"].agg(["sum", "count"])
d = d.sort_values("sum", ascending=False)
d["share"] = d["sum"] / grand
print(d.head(12).to_string())

# ------------------------------------------------------------------
# 3. 地点（邮编）支出排名（Top10）
# ------------------------------------------------------------------
print("\n===== LOCATION (top 10 by spend) =====")
loc = df.groupby("zip_code")["total_price"].sum()
loc = loc.sort_values(ascending=False)
print(loc.head(10).to_string())
zip_present = int(df["zip_code"].notna().sum())
print("LOCATIONS_WITH_VALUE", zip_present, "of", len(df))

# ------------------------------------------------------------------
# 4. UNSPSC 品类段支出排名（Top12）
# ------------------------------------------------------------------
# 用 .astype("Int64").astype(str).str[:2] 链式操作也能取前 2 位，
# 这里改成逐行 for 循环，先处理缺失值，再取前两位。
print("\n===== UNSPSC (top 12 by spend) =====")

# 逐行生成 unspsc_segment 列：取 unspsc 的前两位作为品类段
segment_list = []
for code in df["unspsc"]:
    if pd.isna(code):
        segment_list.append(None)
    else:
        # 先转成整数再转字符串，去掉小数点后的 .0
        code_int = int(code)
        code_str = str(code_int)
        segment_list.append(code_str[:2])

# 把派生列拼回 DataFrame
u = df.copy()
u["unspsc_segment"] = segment_list

g = u.groupby("unspsc_segment")["total_price"].agg(["sum", "count"])
g = g.sort_values("sum", ascending=False)
g["share"] = g["sum"] / grand
print(g.head(12).to_string())
unspsc_present = int(u["unspsc"].notna().sum())
print("UNSPSC_PRESENT", unspsc_present, "of", len(u))

# ------------------------------------------------------------------
# 5. 月度支出趋势
# ------------------------------------------------------------------
# 去掉 creation_date 为空的行，按月份重采样求和
print("\n===== MONTHLY TREND (total price by month) =====")
mm = df.dropna(subset=["creation_date"]).set_index("creation_date")
mt = mm["total_price"].resample("MS").sum()
print(mt.to_string())

# ------------------------------------------------------------------
# 6. 采购方式控制视角
# ------------------------------------------------------------------
print("\n===== ACQUISITION METHOD: control view =====")
m = df.groupby("acquisition_method")["total_price"].agg(["sum", "count"])
m = m.sort_values("sum", ascending=False)
m["share"] = m["sum"] / grand
print(m.to_string())

# ------------------------------------------------------------------
# 7. 控制卡（cal_card）占比
# ------------------------------------------------------------------
# 如果表里有 cal_card 列，就算"YES"那部分的支出占比
if "cal_card" in df.columns:
    cal_spend = df.loc[df["cal_card"] == "YES", "total_price"].sum()
    cal_share = round(float(cal_spend) / grand, 4)
    print("CALCARD_YES_SHARE", cal_share)
else:
    print("CALCARD_YES_SHARE", "no col")
