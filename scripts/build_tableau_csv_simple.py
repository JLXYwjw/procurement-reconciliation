# -*- coding: utf-8 -*-
"""
生成 Tableau 10.5 专用 CSV —— 基础可读版（build_tableau_csv_simple.py）
=======================================================================

  读入 export_pbip_csv_simple.py 导出的 CSV，生成 4 张 Tableau 专用表：
    1. tableau_fact_wide.csv      明细宽表（把供应商维表 join 进明细表）
    2. tableau_supplier_top500.csv 支出前500家供应商（散点图专用）
    3. tableau_supplier_all.csv    全量供应商（备查）
    4. tableau_top20.csv            支出前20家（条形图专用）

为什么用宽表：Tableau 10.5 不支持关系（Relationship），只能物理 JOIN。
为什么单独做供应商汇总表：帕累托等指标是供应商粒度的，在明细上 SUM 会重复计数。
为什么预计算分析字段：10.5 的表计算 XML 盲写极易出错，预计算零风险。

运行方式：
    python scripts/build_tableau_csv_simple.py

English:
Generate Tableau 10.5-specific CSVs (plain, readable version).

Reads the CSVs exported by export_pbip_csv_simple.py and builds 4 Tableau-ready tables:
  1. tableau_fact_wide.csv        - wide fact table (supplier dim joined in)
  2. tableau_supplier_top500.csv  - top-500 suppliers by spend (for scatter)
  3. tableau_supplier_all.csv     - all suppliers (reference)
  4. tableau_top20.csv            - top-20 suppliers (for bar chart)

Why a wide table: Tableau 10.5 does not support relationships, only
physical joins. Why separate supplier aggregates: Pareto-type metrics are
supplier-grained, so summing them on fact rows double-counts. Why
precomputed analytical fields: hand-writing 10.5 table-calc XML is error
prone; precomputing is zero-risk.

Run:
    python scripts/build_tableau_csv_simple.py
"""

import os
import re
import pandas as pd

# ------------------------------------------------------------------
# 0. 路径和列配置
# ------------------------------------------------------------------
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DST = os.path.join(ROOT, "data", "pbip")
OUT_FACT = os.path.join(DST, "tableau_fact_wide.csv")
OUT_DIM = os.path.join(DST, "tableau_supplier_top500.csv")
OUT_DIM_ALL = os.path.join(DST, "tableau_supplier_all.csv")
OUT_TOP20 = os.path.join(DST, "tableau_top20.csv")

WS_PATTERN = re.compile(r"[\r\n\t]+")

# 明细宽表的输出列顺序
FACT_COLS = [
    "creation_date", "year_month", "fiscal_year", "po_number",
    "acquisition_method", "method_class", "method_class_cn", "acquisition_type",
    "department", "dept_group", "supplier_name",
    "quantity", "unit_price", "total_price", "spend_b",
    "segment", "supplier_tier", "tier_cn",
    "supplier_total_spend", "supplier_order_count",
    "supplier_category_breadth", "supplier_years_active",
]

# dim 表的列改名映射
DIM_COLS = {
    "tier": "supplier_tier",
    "total_spend": "supplier_total_spend",
    "order_count": "supplier_order_count",
    "category_breadth": "supplier_category_breadth",
    "years_active": "supplier_years_active",
}

# 供应商汇总表的输出列
OUT_DIM_COLS = [
    "supplier_name", "supplier_rank", "total_spend_b", "total_spend",
    "order_count", "avg_order", "cum_share_pct", "category_breadth",
    "years_active", "tier_cn", "tier_order",
]

# 分层中文标签
TIER_CN = {
    "core_strategic": "核心战略",
    "regular": "常规",
    "tail": "长尾",
    "oneoff_large": "一次性大额",
}
TIER_ORDER = {"core_strategic": 1, "regular": 2, "tail": 3, "oneoff_large": 4}

# 采购方式中文标签
METHOD_CN = {"competitive": "竞争性", "exempt": "豁免", "flexible": "灵活"}


# ------------------------------------------------------------------
# 工具函数
# ------------------------------------------------------------------
def flat(v):
    """压平字符串里的换行/制表符。"""
    if v is None:
        return None
    if isinstance(v, float) and pd.isna(v):
        return None
    return WS_PATTERN.sub(" ", str(v)).strip()


# ------------------------------------------------------------------
# 主流程
# ------------------------------------------------------------------
def main():
    # ---- 1. 读入已归并+压平换行的 CSV ----
    fact = pd.read_csv(os.path.join(DST, "fact_procurement.csv"),
                       dtype=str, keep_default_na=False)
    dim = pd.read_csv(os.path.join(DST, "dim_supplier.csv"),
                      dtype=str, keep_default_na=False)

    # 把数值列转成真正的数值类型
    for c in ("quantity", "unit_price", "total_price"):
        fact[c] = pd.to_numeric(fact[c].replace("", None), errors="coerce")
    for c in ("total_spend", "order_count", "category_breadth", "years_active"):
        dim[c] = pd.to_numeric(dim[c].replace("", None), errors="coerce")

    # 明细宽表：先取基础列
    fact = fact[["creation_date", "fiscal_year", "po_number", "acquisition_method",
                 "method_class", "acquisition_type", "department", "supplier_name",
                 "quantity", "unit_price", "total_price", "segment"]].copy()

    # 供应商汇总表用原始列名的一份；明细 JOIN 用改名后的
    dim_raw = dim.copy()
    dim = dim[["supplier_name"] + list(DIM_COLS)].rename(columns=DIM_COLS)

    # ---- 2. 明细宽表：把供应商维表 join 进来 ----
    merged = fact.merge(dim, on="supplier_name", how="left")

    # 2.1 年月（取 creation_date 前7位 = YYYY-MM）
    year_month_list = []
    for d in merged["creation_date"]:
        text = str(d)
        year_month_list.append(text[:7])
    merged["year_month"] = year_month_list

    # 2.2 十亿单位金额
    merged["spend_b"] = merged["total_price"] / 1e9

    # 2.3 部门分组：Top15 保留原名，其余合并
    dept_sum = merged.groupby("department")["total_price"].sum().sort_values(ascending=False)
    top15_set = set(dept_sum.head(15).index)

    dept_group_list = []
    for dept in merged["department"]:
        if dept in top15_set:
            dept_group_list.append(dept)
        else:
            dept_group_list.append("其他 96 个部门")
    merged["dept_group"] = dept_group_list

    # 2.4 中文标签
    method_cn_list = []
    for mc in merged["method_class"]:
        if mc in METHOD_CN:
            method_cn_list.append(METHOD_CN[mc])
        else:
            method_cn_list.append("未分类")
    merged["method_class_cn"] = method_cn_list

    tier_cn_list = []
    for tier in merged["supplier_tier"]:
        if tier in TIER_CN:
            tier_cn_list.append(TIER_CN[tier])
        else:
            tier_cn_list.append("未分层")
    merged["tier_cn"] = tier_cn_list

    # 压平所有字符串列的换行
    for c in merged.columns:
        if pd.api.types.is_string_dtype(merged[c]) or merged[c].dtype == object:
            flattened = []
            for v in merged[c]:
                flattened.append(flat(v))
            merged[c] = flattened

    # 按指定列顺序输出
    merged = merged[FACT_COLS]
    merged.to_csv(OUT_FACT, index=False, encoding="utf-8", lineterminator="\n")

    # ---- 3. 供应商汇总表（一供应商一行） ----
    sup = dim_raw[dim_raw["supplier_name"].astype(bool)].copy()
    sup = sup.sort_values("total_spend", ascending=False, kind="mergesort").reset_index(drop=True)

    total = sup["total_spend"].sum()

    # 排名
    sup["supplier_rank"] = range(1, len(sup) + 1)

    # 十亿单位
    sup["total_spend_b"] = sup["total_spend"] / 1e9

    # 累计占比
    sup["cum_share_pct"] = sup["total_spend"].cumsum() / total * 100

    # 平均订单金额
    safe_orders = sup["order_count"].replace(0, pd.NA)
    sup["avg_order"] = sup["total_spend"] / safe_orders

    # 中文分层标签
    tier_cn_list2 = []
    for t in sup["tier"]:
        if t in TIER_CN:
            tier_cn_list2.append(TIER_CN[t])
        else:
            tier_cn_list2.append("未分层")
    sup["tier_cn"] = tier_cn_list2

    # 分层排序号
    tier_order_list = []
    for t in sup["tier"]:
        if t in TIER_ORDER:
            tier_order_list.append(TIER_ORDER[t])
        else:
            tier_order_list.append(9)
    sup["tier_order"] = tier_order_list

    # 压平字符串
    for c in ("supplier_name", "tier_cn"):
        flattened = []
        for v in sup[c]:
            flattened.append(flat(v))
        sup[c] = flattened

    sup = sup[OUT_DIM_COLS]
    sup.to_csv(OUT_DIM_ALL, index=False, encoding="utf-8", lineterminator="\n")

    # ---- 4. Top500 供应商（散点图专用） ----
    sup500 = sup.head(500).copy()
    sup500.to_csv(OUT_DIM, index=False, encoding="utf-8", lineterminator="\n")

    # ---- 5. Top20 单独成表 ----
    top20 = sup.sort_values("supplier_rank").head(20).copy()
    top20 = top20[["supplier_name", "supplier_rank", "total_spend_b", "order_count", "tier_cn"]]
    top20.to_csv(OUT_TOP20, index=False, encoding="utf-8", lineterminator="\n")

    # ---- 6. 报告输出 ----
    outputs = [
        (OUT_FACT, merged),
        (OUT_DIM, sup500),
        (OUT_DIM_ALL, sup),
        (OUT_TOP20, top20),
    ]
    for path, df_out in outputs:
        size = os.path.getsize(path) / 1024 / 1024
        print(f"{os.path.basename(path)}: {len(df_out):,} 行  {len(df_out.columns)} 列  {size:.1f} MB")

    # ---- 7. 自检：换行 / 列数 ----
    import csv as _csv
    for path in (OUT_FACT, OUT_DIM, OUT_DIM_ALL, OUT_TOP20):
        with open(path, encoding="utf-8", newline="") as f:
            rd = _csv.reader(f)
            header = next(rd)
            nl = 0
            bad = 0
            n = 0
            for row in rd:
                n += 1
                if len(row) != len(header):
                    bad += 1
                has_nl = False
                for v in row:
                    if "\n" in v or "\r" in v:
                        has_nl = True
                        break
                if has_nl:
                    nl += 1
        print(f"  自检 {os.path.basename(path)}: {n:,} 行 | 嵌入换行 {nl} | 列错位 {bad}")

    # ---- 8. 关键结论核对 ----
    print()
    print("=== 关键结论（供标题写死前核对）===")
    print(f"总支出 ${total/1e9:.1f}B | 供应商 {len(sup):,} 家")
    top10_pct = sup.head(10)["total_spend"].sum() / total * 100
    top20_pct = sup.head(20)["total_spend"].sum() / total * 100
    print(f"Top10 供应商占比 {top10_pct:.1f}%")
    print(f"Top20 供应商占比 {top20_pct:.1f}%")

    ds = merged.groupby("dept_group")["total_price"].sum().sort_values(ascending=False)
    tot = ds.sum()
    other_dept = "其他 96 个部门"
    top15_pct = ds[ds.index != other_dept].sum() / tot * 100
    print(f"Top15 部门占比 {top15_pct:.1f}%")
    print("  最大部门:", ds.index[0], f"${ds.iloc[0]/1e9:.2f}B", f"({ds.iloc[0]/tot*100:.1f}%)")

    ms = merged.groupby("method_class_cn")["total_price"].sum().sort_values(ascending=False)
    print("采购控制:", end=" ")
    method_dict = {}
    for k, v in ms.items():
        method_dict[k] = f"${v/1e9:.0f}B ({v/tot*100:.1f}%)"
    print(method_dict)

    ts = merged.groupby("tier_cn")["total_price"].sum().sort_values(ascending=False)
    print("供应商分层支出:", end=" ")
    tier_dict = {}
    for k, v in ts.items():
        tier_dict[k] = f"${v/1e9:.1f}B ({v/tot*100:.1f}%)"
    print(tier_dict)


if __name__ == "__main__":
    main()
