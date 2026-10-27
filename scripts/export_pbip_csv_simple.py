# -*- coding: utf-8 -*-
"""
导出 Power BI / Tableau 专用 CSV —— 基础可读版（export_pbip_csv_simple.py）
=========================================================================

  1. 把 parquet 转成 CSV 前，压平所有字符串里的换行符
     （否则 Power Query 会把一条记录撑成多行）
  2. 合并供应商名的大小写变体（'AMANDA WILLIS' 和 'Amanda Willis' 算同一个）
     （否则 Power BI 会报"列包含重复值"）
  3. 预计算图表直接可用的分析列：年月、部门分组（Top15+其他）、
     供应商分组（Top10+其他）、帕累托累计占比
  4. 输出 fact_procurement.csv 和 dim_supplier.csv

输出：
  data/pbip/fact_procurement.csv
  data/pbip/dim_supplier.csv

运行方式：
    python scripts/export_pbip_csv_simple.py

English:
Export Power BI / Tableau-ready CSVs (plain, readable version).

Steps:
  1. Flatten embedded newlines inside strings before CSV export
     (otherwise Power Query splits one record into multiple rows)
  2. Merge case variants of supplier names ('AMANDA WILLIS' vs 'Amanda
     Willis' become the same supplier) so Power BI does not report
     "column contains duplicate values"
  3. Precompute chart-ready analytical columns: year-month, department
     group (Top15 + others), supplier group (Top10 + others), Pareto
     cumulative share
  4. Write fact_procurement.csv and dim_supplier.csv

Output:
  data/pbip/fact_procurement.csv
  data/pbip/dim_supplier.csv

Run:
    python scripts/export_pbip_csv_simple.py
"""

import os
import re

import pandas as pd

# ------------------------------------------------------------------
# 0. 路径配置
# ------------------------------------------------------------------
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "data", "output")
DST = os.path.join(ROOT, "data", "pbip")
os.makedirs(DST, exist_ok=True)

# 换行/制表符匹配模式（用于压平文本）
WS_PATTERN = re.compile(r"[\r\n\t]+")


# ------------------------------------------------------------------
# 工具函数
# ------------------------------------------------------------------
def flatten_text(v):
    """把字符串里的换行/制表压成空格；None/NaN 保持 None。"""
    if v is None:
        return None
    if isinstance(v, float) and pd.isna(v):
        return None
    text = str(v)
    # 把连续的换行/制表符替换成单个空格，再去掉首尾空白
    text = WS_PATTERN.sub(" ", text)
    text = text.strip()
    return text


def norm_key(series):
    """供应商名规范化键：大写 + 去首尾空格。
    用 .fillna("").astype(str).str.upper().str.strip() 链式操作也行，
    这里改成逐行 for 循环。
    """
    result = []
    for v in series:
        if pd.isna(v):
            result.append("")
        else:
            text = str(v).upper().strip()
            result.append(text)
    return pd.Series(result, index=series.index)


# ------------------------------------------------------------------
# 1. 合并供应商大小写变体
# ------------------------------------------------------------------
def merge_supplier_variants(fact, dim):
    """把大小写变体的供应商合并成一个，保证 dim 侧 supplier_name 唯一。

    合并规则：
      · 显示名 = 该组里 total_spend 最大的那条的原始写法
      · total_spend / order_count / line_count 求和
      · category_breadth / years_active 取最大
      · avg_order / order_freq / top_*_share 重算
      · tier 取该组里 total_spend 最大的那条
    """
    fact = fact.copy()
    dim = dim.copy()

    # 给两张表都加上规范化键列
    fact["_k"] = norm_key(fact["supplier_name"])
    dim["_k"] = norm_key(dim["supplier_name"])

    # 每组里金额最大的行索引（用于取显示名和 tier）
    idx = dim.groupby("_k")["total_spend"].idxmax()
    canon = dim.loc[idx].set_index("_k")["supplier_name"]
    tier_map = dim.loc[idx].set_index("_k")["tier"]

    # 按规范化键分组聚合
    g = dim.groupby("_k", as_index=False).agg(
        total_spend=("total_spend", "sum"),
        order_count=("order_count", "sum"),
        line_count=("line_count", "sum"),
        category_breadth=("category_breadth", "max"),
        years_active=("years_active", "max"),
        top_segment_spend=("top_segment_spend", "max"),
        top_department_spend=("top_department_spend", "max"),
    )

    # 给合并后的表加上显示名和 tier
    g["supplier_name"] = g["_k"].map(canon)
    g["tier"] = g["_k"].map(tier_map)

    # 重算平均订单和下单频率
    safe_orders = g["order_count"].replace(0, pd.NA)
    g["avg_order"] = g["total_spend"] / safe_orders

    safe_years = g["years_active"].replace(0, pd.NA)
    g["order_freq"] = g["order_count"] / safe_years

    # 重算集中度占比
    safe_spend = g["total_spend"].replace(0, pd.NA)
    g["top_segment_share"] = (g["top_segment_spend"] / safe_spend).fillna(0)
    g["top_department_share"] = (g["top_department_spend"] / safe_spend).fillna(0)

    # 列顺序对齐原始 dim
    order = [
        "supplier_name", "total_spend", "order_count", "line_count",
        "category_breadth", "years_active", "top_segment_spend",
        "top_department_spend", "top_segment_share",
        "top_department_share", "avg_order", "order_freq", "tier",
    ]
    dim_out = g[order].copy()

    # fact 表的供应商名映射到统一显示名
    fact["supplier_name"] = fact["_k"].map(canon).fillna(fact["supplier_name"])
    fact = fact.drop(columns=["_k"])

    # 校验：dim 侧在大小写不敏感下必须唯一
    dup = norm_key(dim_out["supplier_name"]).duplicated().sum()
    assert dup == 0, f"dim 仍有 {dup} 个大小写重复"

    print(f"  供应商归并: {len(dim):,} -> {len(dim_out):,} 行（合并 {len(dim) - len(dim_out)} 组变体）")
    return fact, dim_out


# ------------------------------------------------------------------
# 2. 补上图表直接可用的分析列
# ------------------------------------------------------------------
def add_analysis_cols(fact):
    """给 fact 表加上预计算的分析列。

    为什么不在 DAX 里做：
      · year_month —— 直接用 creation_date 当轴会展开成 1015 个点
      · dept_group —— 111 个部门全画出来是一堆乱线，Top15 + 其他 才可读
      · dept_cum_share —— 帕累托累计曲线，做到行级后图表用 MAX() 聚合即可
    """
    df = fact.copy()
    spend = pd.to_numeric(df["total_price"], errors="coerce")

    # ---- 2.1 年月 + 月份序号 ----
    d = pd.to_datetime(df["creation_date"], errors="coerce")
    df["year_month"] = d.dt.strftime("%Y-%m")
    df["month_no"] = d.dt.month.astype("Int64")

    # ---- 2.2 控制类别中文标签 ----
    method_cn = {"competitive": "竞争性", "exempt": "豁免", "flexible": "灵活"}
    cn_labels = []
    for mc in df["method_class"]:
        if mc in method_cn:
            cn_labels.append(method_cn[mc])
        else:
            cn_labels.append("未分类")
    df["method_class_cn"] = cn_labels

    # ---- 2.3 部门分组：Top15 保留原名，其余合并 ----
    dept_spend = spend.groupby(df["department"]).sum().sort_values(ascending=False)
    total_dept = dept_spend.sum()
    n_other = max(len(dept_spend) - 15, 0)
    other_label = f"其他 {n_other} 个部门"

    # 收集前15名的部门名
    top15_depts = []
    for name in dept_spend.head(15).index:
        top15_depts.append(name)
    top15_set = set(top15_depts)

    # 逐行判断：在前15里就保留原名，否则归为"其他"
    dept_group_list = []
    for dept in df["department"]:
        if dept in top15_set:
            dept_group_list.append(dept)
        else:
            dept_group_list.append(other_label)
    df["dept_group"] = dept_group_list

    # ---- 2.4 部门排名 + 累计占比（帕累托） ----
    # 排名顺序：前15按支出排，然后是"其他"
    ordered_depts = list(top15_depts)
    if n_other > 0:
        ordered_depts.append(other_label)

    # 建排名字典：第1名=1，第2名=2...
    dept_rank_map = {}
    for i, name in enumerate(ordered_depts):
        dept_rank_map[name] = i + 1

    # 逐行映射排名
    dept_rank_list = []
    for dg in df["dept_group"]:
        if dg in dept_rank_map:
            dept_rank_list.append(dept_rank_map[dg])
        else:
            dept_rank_list.append(99)
    df["dept_rank"] = dept_rank_list

    # 算每个分组的累计占比
    grp_spend = spend.groupby(df["dept_group"]).sum().reindex(ordered_depts)
    cum_share = grp_spend.cumsum() / total_dept

    # 逐行映射累计占比
    cum_share_list = []
    for dg in df["dept_group"]:
        if dg in cum_share.index:
            cum_share_list.append(cum_share[dg])
        else:
            cum_share_list.append(None)
    df["dept_cum_share"] = cum_share_list

    print(f"  部门分组: {len(dept_spend)} → {len(ordered_depts)} 组（Top15 + 「{other_label}」）")
    first_share = cum_share.iloc[0] * 100
    fourth_share = cum_share.iloc[3] * 100
    idx15 = min(14, len(cum_share) - 1)
    fifteenth_share = cum_share.iloc[idx15] * 100
    print(f"  Top1 部门占比 {first_share:.1f}% | Top4 {fourth_share:.1f}% | Top15 {fifteenth_share:.1f}%")

    # ---- 2.5 供应商分组：Top10 保留原名，其余合并 ----
    # 必须做：24,465 个供应商直接当条形图维度 = 24,465 根条，
    # 渲染出来是一坨黑块。做成 Top10 + 其他 后是 11 根条。
    sup_spend = spend.groupby(df["supplier_name"]).sum().sort_values(ascending=False)
    n_other_sup = max(len(sup_spend) - 10, 0)
    sup_other = f"其他 {n_other_sup:,} 家"

    top10_sups = []
    for name in sup_spend.head(10).index:
        top10_sups.append(name)
    top10_set = set(top10_sups)

    sup_group_list = []
    for sup_name in df["supplier_name"]:
        if sup_name in top10_set:
            sup_group_list.append(sup_name)
        else:
            sup_group_list.append(sup_other)
    df["supplier_group"] = sup_group_list

    # 供应商排名
    ordered_sups = list(top10_sups)
    if n_other_sup > 0:
        ordered_sups.append(sup_other)

    sup_rank_map = {}
    for i, name in enumerate(ordered_sups):
        sup_rank_map[name] = i + 1

    sup_rank_list = []
    for sg in df["supplier_group"]:
        if sg in sup_rank_map:
            sup_rank_list.append(sup_rank_map[sg])
        else:
            sup_rank_list.append(99)
    df["supplier_rank"] = sup_rank_list

    print(f"  供应商分组: {len(sup_spend):,} → {len(ordered_sups)} 组（Top10 + 「{sup_other}」」）")
    return df


# ------------------------------------------------------------------
# 3. 导出 DataFrame 到 CSV
# ------------------------------------------------------------------
def export_frame(df, out_name):
    df = df.copy()

    # datetime 列转字符串；字符串列压平换行
    for c in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[c]):
            df[c] = df[c].dt.strftime("%Y-%m-%d")
        elif pd.api.types.is_string_dtype(df[c]) or df[c].dtype == object:
            # 逐行压平
            flattened = []
            for v in df[c]:
                flattened.append(flatten_text(v))
            df[c] = flattened

    out = os.path.join(DST, out_name)
    df.to_csv(out, index=False, encoding="utf-8", lineterminator="\n")
    size_mb = os.path.getsize(out) / 1024 / 1024
    print(f"{out_name}: {len(df):,} 行  {len(df.columns)} 列  {size_mb:.1f} MB")


# ------------------------------------------------------------------
# 4. 主流程
# ------------------------------------------------------------------
def main():
    print("导出 CSV（压平换行 + 归一供应商大小写）...")

    fact = pd.read_parquet(os.path.join(SRC, "procurement_clean.parquet"))
    dim = pd.read_parquet(os.path.join(SRC, "supplier_segmentation.parquet"))

    fact, dim = merge_supplier_variants(fact, dim)
    fact = add_analysis_cols(fact)

    export_frame(fact, "fact_procurement.csv")
    export_frame(dim, "dim_supplier.csv")

    # 交叉验证：fact 的供应商名必须都能在 dim 找到（大小写不敏感）
    fk = set(norm_key(fact["supplier_name"]))
    dk = set(norm_key(dim["supplier_name"]))
    missing = fk - dk
    print(f"  交叉校验: fact 供应商 key 数 {len(fk)}, dim key 数 {len(dk)}, "
          f"fact 独有 {len(missing)}")


if __name__ == "__main__":
    main()
