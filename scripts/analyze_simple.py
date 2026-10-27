# -*- coding: utf-8 -*-
"""
业务指标分析 —— 基础可读版（analyze_simple.py）
=================================================

  1. 读入清洗好的采购明细表（procurement_clean.parquet）
  2. 回答第一批业务问题：总共花了多少钱、钱集中在谁身上
     （Top10 占比、CR4、CR8、HHI）
  3. 按采购方式、按财年汇总支出

区别只是：本文件故意用最朴素的写法（for 循环、if 判断、普通函数），
每一步都写清楚了在做什么、为什么。

运行方式：
    python scripts/analyze_simple.py

English:
Business-metric analysis (plain, readable version).

Steps:
  1. Read the cleaned procurement table (procurement_clean.parquet)
  2. Answer the first batch of business questions: how much was spent in
     total, and how concentrated the spend is (Top-10 share, CR4, CR8, HHI)
  3. Summarize spend by procurement method and by fiscal year

The code uses the plainest style on purpose (for-loops, if-statements,
ordinary functions) and every step states what it does and why.

Run:
    python scripts/analyze_simple.py
"""

import os

import pandas as pd

# ------------------------------------------------------------------
# 0. 路径配置
# ------------------------------------------------------------------
# 找项目根目录（本文件在 scripts/ 下，上一级就是项目根目录）
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ------------------------------------------------------------------
# 1. 读入清洗后的采购数据
# ------------------------------------------------------------------
parquet_path = os.path.join(ROOT, "data", "output", "procurement_clean.parquet")
df = pd.read_parquet(parquet_path)

# ------------------------------------------------------------------
# 2. 总体数字：总支出、订单数、供应商数
# ------------------------------------------------------------------
total_sum = round(float(df["total_price"].sum()), 2)
unique_po = int(df["po_number"].nunique())
unique_supplier = int(df["supplier_name"].nunique())

print("TOTAL_PRICE_SUM", total_sum)
print("UNIQUE_PO", unique_po)
print("UNIQUE_SUPPLIER", unique_supplier)

# ------------------------------------------------------------------
# 3. 供应商集中度分析
# ------------------------------------------------------------------
# 按供应商汇总支出，从高到低排序
g = df.groupby("supplier_name")["total_price"].sum().sort_values(ascending=False)
grand = float(df["total_price"].sum())

# Top10 供应商拿走了多少比例
top10_share = round(float(g.head(10).sum()) / grand, 4)
print("TOP10_SHARE", top10_share)

# CR4 / CR8：前4家 / 前8家占总支出的比例
# （比 HHI 更直观地回答"钱依赖谁"这个问题）
cr4 = float(g.head(4).sum()) / grand
cr8 = float(g.head(8).sum()) / grand
print("CR4", round(cr4, 4))
print("CR8", round(cr8, 4))

# HHI（赫芬达尔指数）：每个供应商份额的平方和
# 作为集中度的辅助参考指标
share = g / g.sum()
hhi_value = round(float((share ** 2).sum()), 5)
print("HHI", hhi_value)

# 打印前 10 名供应商明细
print("TOP10_SUPPLIERS")
print(g.head(10).to_string())

# ------------------------------------------------------------------
# 4. 按采购方式汇总
# ------------------------------------------------------------------
# 每种采购方式的总支出和行数，按支出从高到低排
m = df.groupby("acquisition_method")["total_price"].agg(["sum", "count"])
m = m.sort_values("sum", ascending=False)
print("METHOD_DIST")
print(m.head(12).to_string())

# ------------------------------------------------------------------
# 5. 按财年汇总
# ------------------------------------------------------------------
# 每个财年的总支出和行数
d = df.groupby("fiscal_year")["total_price"].agg(["sum", "count"])
d = d.sort_values("sum", ascending=False)
print("YEAR_DIST")
print(d.head(8).to_string())
