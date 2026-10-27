# -*- coding: utf-8 -*-
"""
机器学习分析 —— 基础可读版（ml_analysis_simple.py）
=================================================
这个文件做的事，和原版 ml_analysis.py 完全一样：
  1. 采购类型分布统计
  2. 货物单价异常检测（只在可比的货物类采购上做，按 UNSPSC 品类段分组，
     用 MAD 稳健规则标记异常行）
  3. 灵活采购方式清单（流程复核用）
  4. 结果存成 goods_anomaly.parquet 和 flexible_review.parquet

v2 的设计思路（v1 的教训）：
  v1 把"总支出大"当成异常特征，结果把 83% 的医疗合同全标成异常——
  又大又合法，毫无意义。v2 只在"可比单价"上做异常检测：
  只有货物类（quantity >= 2）、同一品类段内，单价偏离中位数太远才算异常。
  服务类合同（quantity=1，价格=总价）不参与比较，因为不可比。

运行方式（和原版一样）：
    python scripts/ml_analysis_simple.py
"""

import os

import numpy as np
import pandas as pd

# ------------------------------------------------------------------
# 0. 路径配置
# ------------------------------------------------------------------
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "data", "output")

# ------------------------------------------------------------------
# 1. 读入清洗后的采购数据
# ------------------------------------------------------------------
parquet_path = os.path.join(ROOT, "data", "output", "procurement_clean.parquet")
df = pd.read_parquet(parquet_path)

# ------------------------------------------------------------------
# 2. 采购类型分布
# ------------------------------------------------------------------
print("ACQUISITION_TYPE_DIST")
print(df["acquisition_type"].value_counts(dropna=False).to_string())

# ------------------------------------------------------------------
# 3. 货物单价异常检测
# ------------------------------------------------------------------
# ---- 3.1 筛选出"可比"的货物行 ----
# 条件：total_price 和 quantity 都不为空，quantity > 0
goods = df.dropna(subset=["total_price", "quantity"]).copy()
goods = goods[goods["quantity"] > 0].copy()

# 计算单价 = 总价 / 数量
goods["unit_cost"] = goods["total_price"] / goods["quantity"]

# 单价必须 > 0（负数或零没有比较意义）
goods = goods[goods["unit_cost"] > 0].copy()

# ---- 3.2 区分货物 vs 服务 ----
# 原版用 .str.contains("Good", case=False, na=False) 链式操作，
# 这里改成逐行判断：acquisition_type 里是否包含 "Good"（不区分大小写）
is_goods_list = []
for atype in goods["acquisition_type"]:
    text = str(atype).lower()
    if "good" in text:
        is_goods_list.append(True)
    else:
        is_goods_list.append(False)
goods["is_goods"] = is_goods_list

print("\nGOODS vs SERVICES (lines)")
print(goods["is_goods"].value_counts().to_string())

# ---- 3.3 只保留货物类且数量 >= 2 的行（数量=1的不可比） ----
gg = goods[goods["is_goods"] & (goods["quantity"] >= 2)].copy()

# ---- 3.4 按品类段计算 MAD（中位数绝对偏差） ----
# MAD = 中位数(|x - 中位数(x)|)，是比标准差更稳健的异常检测指标
# 原版用 lambda 一行算，这里改成普通函数
def calc_mad(series):
    """计算一组数的 MAD（中位数绝对偏差）。"""
    med = series.median()
    deviations = (series - med).abs()
    return deviations.median()


# 按品类段分组，算每个段的中位数和 MAD
seg_median = gg.groupby("segment")["unit_cost"].median()
seg_count = gg.groupby("segment")["unit_cost"].count()
seg_mad = gg.groupby("segment")["unit_cost"].apply(calc_mad)

# 组装成统计表
seg_stats = pd.DataFrame({
    "median": seg_median,
    "n": seg_count,
    "mad": seg_mad,
}).reset_index()

# 只保留样本量 >= 20 的品类段（样本太少统计不可靠）
seg_stats = seg_stats[seg_stats["n"] >= 20].reset_index(drop=True)

# 把中位数和 MAD 合并回明细行
gg = gg.merge(seg_stats[["segment", "median", "mad"]], on="segment", how="left")
gg = gg.dropna(subset=["median", "mad"]).copy()

# ---- 3.5 计算偏离度，标记异常 ----
# 偏离度 = (单价 - 段中位数) / MAD
# MAD 为 0 的情况记为 NaN（避免除零）
safe_mad = gg["mad"].replace(0, np.nan)
gg["unit_cost_dev"] = (gg["unit_cost"] - gg["median"]) / safe_mad

# 偏离度 > 3 倍 MAD 就算异常（经典稳健异常检测阈值）
gg["goods_outlier"] = gg["unit_cost_dev"] > 3

# ---- 3.6 打印异常统计 ----
n_outliers = int(gg["goods_outlier"].sum())
print("\nGOODS_LINES_COMPARABLE", len(gg), "| UNIT_COST_OUTLIERS", n_outliers)

outlier_spend = round(float(gg.loc[gg["goods_outlier"], "total_price"].sum()), 2)
print("OUTLIER_SPEND", outlier_spend)

# 打印支出最高的 15 个异常行
top_outliers = gg[gg["goods_outlier"]].sort_values("total_price", ascending=False)
print("\nTOP_GOODS_OUTLIERS (by spend)")
print(top_outliers[["department", "supplier_name", "item_name", "quantity",
                    "unit_price", "total_price", "segment", "method_class"]]
      .head(15).to_string())

# ------------------------------------------------------------------
# 4. 灵活采购方式清单（流程复核用）
# ------------------------------------------------------------------
# method_class == "flexible" 的采购 = 非常规方法，值得复核
flex = df[df["method_class"] == "flexible"].copy()

flex_spend = round(float(flex["total_price"].sum()), 2)
print("\nFLEXIBLE_METHOD_SPEND", flex_spend, "| LINES", len(flex))

fm = flex.groupby("acquisition_method")["total_price"].agg(["sum", "count"])
fm = fm.sort_values("sum", ascending=False)
print(fm.head(10).to_string())

# ------------------------------------------------------------------
# 5. 保存结果
# ------------------------------------------------------------------
# 注意：供应商分层（segmentation）由 supplier_cluster.py 负责，
# 这里不重复生成，避免覆盖 v2 的结果。
gg.to_parquet(os.path.join(OUT_DIR, "goods_anomaly.parquet"), index=False)
flex.to_parquet(os.path.join(OUT_DIR, "flexible_review.parquet"), index=False)
print("\nSAVED goods_anomaly / flexible_review")
