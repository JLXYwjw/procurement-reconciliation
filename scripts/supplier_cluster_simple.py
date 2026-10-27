# -*- coding: utf-8 -*-
"""
供应商分层聚类 v2 —— 基础可读版（supplier_cluster_simple.py）
===========================================================

  1. 给每个供应商构建"业务特征"：总支出、平均订单、下单频率、活跃年数、
     品类集中度、部门依赖度
  2. 用 KMeans 聚类（k=4），把供应商分成 4 类
  3. 按业务含义给每类打标签：核心战略 / 一次性大额 / 常规 / 长尾
  4. 验证"核心类"不只是"支出前N名"（v1 版的问题就是聚类等于按支出排序）
  5. 结果存成 supplier_segmentation.parquet

为什么 v2 要这么设计：
  v1 的教训是——用"规模"特征做 KMeans，结果等于"按总支出排序取前N"，
  聚类没有带来任何新信息。v2 故意加入"粘性"（活跃年数、下单频率）
  和"集中度"（品类、部门）这些"按支出排序看不到"的特征，
  让聚类真正区分出"大额但只来一次"和"中等但长期合作"的供应商。

运行方式：
    python scripts/supplier_cluster_simple.py

English:
Supplier segmentation clustering v2 (plain, readable version).

Steps:
  1. Build business features per supplier: total spend, average order,
     order frequency, active years, category concentration, department
     dependence
  2. Cluster with KMeans (k=4)
  3. Label each cluster by business meaning: core-strategic / one-off
     large / regular / tail
  4. Verify that the "core" cluster is not simply "top-N by spend"
     (the v1 problem was that clustering reduced to sorting by spend)
  5. Save supplier_segmentation.parquet

Why v2 is designed this way: v1's lesson is that using only "scale"
features makes KMeans equivalent to "sort by total spend and take the
top-N" - clustering adds no information. v2 deliberately adds "stickiness"
(active years, order frequency) and "concentration" (category, department)
features that sorting by spend cannot see, so clustering truly separates
"large but one-time" suppliers from "medium but long-term" ones.

Run:
    python scripts/supplier_cluster_simple.py
"""

import os

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

# 导入分层标签工具函数
from segment_utils_simple import label_tiers

# ------------------------------------------------------------------
# 0. 路径配置
# ------------------------------------------------------------------
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "data", "output")

# ------------------------------------------------------------------
# 1. 读入清洗后的采购数据
# ------------------------------------------------------------------
parquet_path = os.path.join(OUT_DIR, "procurement_clean.parquet")
df = pd.read_parquet(parquet_path)

# ------------------------------------------------------------------
# 2. 按供应商汇总基础特征
# ------------------------------------------------------------------
# 每个供应商一行：总支出、订单数、行数、品类广度、活跃年数
sup = df.groupby("supplier_name").agg(
    total_spend=("total_price", "sum"),
    order_count=("po_number", "nunique"),
    line_count=("total_price", "count"),
    category_breadth=("segment", "nunique"),
    years_active=("fiscal_year", "nunique"),
).reset_index()


# ------------------------------------------------------------------
# 3. 计算"品类集中度"和"部门集中度"
# ------------------------------------------------------------------
# 对每个供应商，找出它花钱最多的那个品类段 / 那个部门，
# 然后算"这个品类/部门占该供应商总支出的比例"。
# 比例越高 = 这个供应商越"专一"（只做一类生意）。
def add_top_share(sup_df, col_name):
    """给 sup_df 加上一列 top_{col_name}_spend：
    每个供应商在 col_name 这个维度上花钱最多的那个值的总金额。
    """
    # 按 供应商 + col_name 分组求和
    t = df.groupby(["supplier_name", col_name])["total_price"].sum().reset_index()
    # 按供应商分组，每个供应商只保留支出最高的那一行
    t = t.sort_values("total_price", ascending=False)
    t = t.groupby("supplier_name").head(1)
    # 改列名
    new_col = "top_" + col_name + "_spend"
    t = t.rename(columns={"total_price": new_col})
    # 合并回主表
    result = sup_df.merge(t[["supplier_name", new_col]], on="supplier_name", how="left")
    return result


# 加上品类集中度和部门集中度两列
sup = add_top_share(sup, "segment")
dept_top = add_top_share(sup, "department")
sup = sup.merge(
    dept_top[["supplier_name", "top_department_spend"]],
    on="supplier_name", how="left"
)

# ---- 计算占比：top品类支出 / 总支出 ----
# 总支出为 0 的情况记为 NaN（避免除零）
safe_spend = sup["total_spend"].replace(0, np.nan)
sup["top_segment_share"] = sup["top_segment_spend"] / safe_spend
sup["top_department_share"] = sup["top_department_spend"] / safe_spend

# ---- 平均订单金额 = 总支出 / 订单数 ----
safe_orders = sup["order_count"].replace(0, np.nan)
sup["avg_order"] = sup["total_spend"] / safe_orders

# ---- 下单频率 = 订单数 / 活跃年数 ----
safe_years = sup["years_active"].replace(0, np.nan)
sup["order_freq"] = sup["order_count"] / safe_years

# ------------------------------------------------------------------
# 4. 准备聚类用的特征矩阵
# ------------------------------------------------------------------
# 注意：top_segment_share 和 top_department_share 故意不作为聚类特征。
# 因为对于只买一样东西、只来一年的供应商，这两个值永远是 1.0，
# 会把聚类又拉回"按规模切分"的老路。
# 我们真正要区分的是"规模 × 粘性 × 频率"：
#   大额但只来一次 vs 中等但长期合作（后者才是战略客户）。
FEATURE_COLS = ["total_spend", "avg_order", "order_count", "order_freq", "years_active"]

X = sup[FEATURE_COLS].copy()

# 偏态处理：对几个右偏的金额/计数列做 log1p（ln(1+x)），让分布更对称
for c in ["total_spend", "avg_order", "order_count", "order_freq"]:
    # 先把负数截到 0（理论上没有负数，但保险）
    X[c] = np.log1p(X[c].clip(lower=0))

# 缺失值填 0
X = X.fillna(0)

# 标准化（均值为 0，标准差为 1）
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

# ------------------------------------------------------------------
# 5. 选聚类数 k
# ------------------------------------------------------------------
# 轮廓系数（silhouette score）会偏向 k=2，但那只是"一大一小"两坨，
# 对业务分析没用。我们要的是"核心/关键/常规/长尾"四层可解释的划分，
# 所以直接选 k=4（业务选择，不是轮廓系数最优）。
sil_scores = {}
for k in range(2, 7):
    km = KMeans(n_clusters=k, n_init=10, random_state=42)
    labels = km.fit_predict(X_scaled)
    score = float(silhouette_score(X_scaled, labels))
    sil_scores[k] = score

# 打印轮廓系数（用字典逐行记录）
print("SILHOUETTE", end=" ")
sil_dict = {}
for k, v in sil_scores.items():
    sil_dict[k] = round(v, 3)
print(sil_dict)

K = 4  # 业务选择：四层划分
print("CHOSEN_K", K)

# ------------------------------------------------------------------
# 6. 执行 KMeans 聚类
# ------------------------------------------------------------------
km = KMeans(n_clusters=K, n_init=10, random_state=42)
sup["cluster"] = km.fit_predict(X_scaled)

# ------------------------------------------------------------------
# 7. 按聚类画像给每个聚类打业务标签
# ------------------------------------------------------------------
# 先算每个聚类的统计画像
prof = sup.groupby("cluster").agg(
    n=("supplier_name", "count"),
    spend=("total_spend", "sum"),
    med_spend=("total_spend", "median"),
    med_seg_share=("top_segment_share", "median"),
    med_dept_share=("top_department_share", "median"),
    med_years=("years_active", "median"),
    med_freq=("order_freq", "median"),
)
prof = prof.sort_values("spend", ascending=False)

print("CLUSTER_PROFILE")
print(prof.to_string())

# 用 segment_utils 里的规则给聚类打标签
label_map = label_tiers(prof).to_dict()
sup["tier"] = sup["cluster"].map(label_map)

# ------------------------------------------------------------------
# 8. 验证："核心类"不只是"支出前N名"
# ------------------------------------------------------------------
# 取出核心战略类的供应商集合
core_suppliers = set(sup[sup["tier"] == "core_strategic"]["supplier_name"])

# 按支出排名的前 8/10/20 名
g = df.groupby("supplier_name")["total_price"].sum().sort_values(ascending=False)

# 算交集大小
overlap8 = len(core_suppliers & set(g.head(8).index))
overlap10 = len(core_suppliers & set(g.head(10).index))
overlap20 = len(core_suppliers & set(g.head(20).index))

print("CORE_SIZE", len(core_suppliers),
      "overlap top8", overlap8,
      "top10", overlap10,
      "top20", overlap20)

# 前20名里有多少是核心类的（用 for 循环统计）
top20_core = []
for name in g.head(20).index:
    if name in core_suppliers:
        top20_core.append(name)
print("TOP20_CORE_MEMBERS", top20_core)

# 核心类里有多少不在前20名（这些是"中等支出但长期合作"的战略客户）
core_outside = []
for name in core_suppliers:
    if name not in set(g.head(20).index):
        core_outside.append(name)
core_outside.sort()
print("CORE_OUTSIDE_TOP20", core_outside[:10])

# ------------------------------------------------------------------
# 9. 分层汇总
# ------------------------------------------------------------------
ts = sup.groupby("tier").agg(
    suppliers=("supplier_name", "count"),
    spend=("total_spend", "sum"),
)
ts["spend_share"] = ts["spend"] / ts["spend"].sum()
print("TIER_SUMMARY")
print(ts.to_string())

# ------------------------------------------------------------------
# 10. 保存结果
# ------------------------------------------------------------------
out_path = os.path.join(OUT_DIR, "supplier_segmentation.parquet")
sup.drop(columns=["cluster"]).to_parquet(out_path, index=False)
print("SAVED supplier_segmentation.parquet")
