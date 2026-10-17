# -*- coding: utf-8 -*-
r"""
生成 Tableau 10.5 专用 CSV（两张表：明细宽表 + 供应商汇总）。

★ 为什么必须是一张宽表（明细）：
  Tableau 10.5（2018-02）不支持 2020.2 才引入的「关系（Relationship）」，
  只能做物理 JOIN。所以把 dim_supplier 的字段直接 join 进明细表。

★ 为什么还要第二张「供应商汇总」表：
  帕累托 / Top20 供应商 / 分层占比 全部是【供应商粒度】的指标。
  如果在 34.6 万行明细上 SUM(supplier_total_spend)，同一个供应商会被
  重复计算 N 次（N = 它的订单行数），结果完全错误。
  所以单独给一张一供应商一行的表，从根上避免重复计数。

★ 为什么把分析字段预先算进 CSV，而不是在 Tableau 里用表计算：
  10.5 的表计算 XML（RUNNING_SUM 等）需要精确的 addressing/partitioning 声明，
  盲写极易出错；而且每错一次用户就要重开一次 Tableau。
  预计算 = 零风险，且与 Python/matplotlib 报告的数字完全一致。

★ 为什么不用 .hyper：
  本机 Tableau 10.5 内置 Hyper 是 2018 年第一代，读不了
  tableauhyperapi 0.0.26784（2025 版）生成的格式。CSV 是 10.5 最稳入口。

输出：
  data/pbip/tableau_fact_wide.csv          明细宽表（346,018 行 × 22 列，含分析辅助列）
  data/pbip/tableau_supplier_top500.csv    支出前 500 家供应商（散点图专用，覆盖 92.7%）
  data/pbip/tableau_supplier_all.csv       全量 24,465 家（备查，不注册为数据源）
  data/pbip/tableau_top20.csv              支出前 20 家（条形图专用，零筛选）
"""
import os
import re
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DST = os.path.join(ROOT, "data", "pbip")
OUT_FACT = os.path.join(DST, "tableau_fact_wide.csv")
OUT_DIM = os.path.join(DST, "tableau_supplier_top500.csv")
OUT_DIM_ALL = os.path.join(DST, "tableau_supplier_all.csv")
OUT_TOP20 = os.path.join(DST, "tableau_top20.csv")

_WS = re.compile(r"[\r\n\t]+")

# 明细宽表的输出列（顺序即 Tableau 里的 ordinal）
FACT_COLS = [
    "creation_date", "year_month", "fiscal_year", "po_number",
    "acquisition_method", "method_class", "method_class_cn", "acquisition_type",
    "department", "dept_group", "supplier_name",
    "quantity", "unit_price", "total_price", "spend_b",
    "segment", "supplier_tier", "tier_cn",
    "supplier_total_spend", "supplier_order_count",
    "supplier_category_breadth", "supplier_years_active",
]

DIM_COLS = {
    "tier": "supplier_tier",
    "total_spend": "supplier_total_spend",
    "order_count": "supplier_order_count",
    "category_breadth": "supplier_category_breadth",
    "years_active": "supplier_years_active",
}

OUT_DIM_COLS = [
    "supplier_name", "supplier_rank", "total_spend_b", "total_spend",
    "order_count", "avg_order", "cum_share_pct", "category_breadth",
    "years_active", "tier_cn", "tier_order",
]

TIER_CN = {
    "core_strategic": "核心战略",
    "regular": "常规",
    "tail": "长尾",
    "oneoff_large": "一次性大额",
}
TIER_ORDER = {"core_strategic": 1, "regular": 2, "tail": 3, "oneoff_large": 4}

METHOD_CN = {"competitive": "竞争性", "exempt": "豁免", "flexible": "灵活"}


def flat(v):
    if v is None:
        return None
    if isinstance(v, float) and pd.isna(v):
        return None
    return _WS.sub(" ", str(v)).strip()


def main() -> None:
    # 读【已归并+压平换行】的 CSV（export_pbip_csv.py 的产物），
    # 保证 PowerBI 和 Tableau 两套数据源用的是同一份供应商归并结果
    fact = pd.read_csv(os.path.join(DST, "fact_procurement.csv"),
                       dtype=str, keep_default_na=False)
    dim = pd.read_csv(os.path.join(DST, "dim_supplier.csv"), dtype=str,
                      keep_default_na=False)

    for c in ("quantity", "unit_price", "total_price"):
        fact[c] = pd.to_numeric(fact[c].replace("", None), errors="coerce")
    for c in ("total_spend", "order_count", "category_breadth", "years_active"):
        dim[c] = pd.to_numeric(dim[c].replace("", None), errors="coerce")

    fact = fact[["creation_date", "fiscal_year", "po_number", "acquisition_method",
                 "method_class", "acquisition_type", "department", "supplier_name",
                 "quantity", "unit_price", "total_price", "segment"]].copy()
    # 供应商汇总表用【原始列名】的一份，明细 JOIN 用改名后的
    dim_raw = dim.copy()
    dim = dim[["supplier_name"] + list(DIM_COLS)].rename(columns=DIM_COLS)

    # ---------- 明细宽表 ----------
    merged = fact.merge(dim, on="supplier_name", how="left")

    # 1) 年月（字符串，避开 10.5 的日期层级聚合问题）
    merged["year_month"] = merged["creation_date"].str[:7]

    # 2) 十亿单位金额（图上直接显示 B，不用自定义数字格式）
    merged["spend_b"] = merged["total_price"] / 1e9

    # 3) 部门分组：Top15 保留原名，其余合并，避免 111 个部门挤爆条形图
    dept_sum = merged.groupby("department")["total_price"].sum().sort_values(ascending=False)
    top15 = set(dept_sum.head(15).index)
    merged["dept_group"] = merged["department"].where(
        merged["department"].isin(top15), "其他 96 个部门")

    # 4) 中文标签
    merged["method_class_cn"] = merged["method_class"].map(METHOD_CN).fillna("未分类")
    merged["tier_cn"] = merged["supplier_tier"].map(TIER_CN).fillna("未分层")

    # 压平所有字符串列换行
    for c in merged.columns:
        if pd.api.types.is_string_dtype(merged[c]) or merged[c].dtype == object:
            merged[c] = merged[c].map(flat)

    merged = merged[FACT_COLS]
    merged.to_csv(OUT_FACT, index=False, encoding="utf-8", lineterminator="\n")

    # ---------- 供应商汇总表（一供应商一行）----------
    sup = dim_raw[dim_raw["supplier_name"].astype(bool)].copy()
    sup = sup.sort_values("total_spend", ascending=False, kind="mergesort").reset_index(drop=True)
    total = sup["total_spend"].sum()
    sup["supplier_rank"] = range(1, len(sup) + 1)
    sup["total_spend_b"] = sup["total_spend"] / 1e9
    sup["cum_share_pct"] = sup["total_spend"].cumsum() / total * 100
    sup["avg_order"] = sup["total_spend"] / sup["order_count"].replace(0, pd.NA)
    sup["tier_cn"] = sup["tier"].map(TIER_CN).fillna("未分层")
    sup["tier_order"] = sup["tier"].map(TIER_ORDER).fillna(9).astype(int)
    for c in ("supplier_name", "tier_cn"):
        sup[c] = sup[c].map(flat)
    sup = sup[OUT_DIM_COLS]
    sup.to_csv(OUT_DIM_ALL, index=False, encoding="utf-8", lineterminator="\n")

    # ---------- Top500 供应商（散点图专用）----------
    # 为什么只取 500：全量 24,465 家里 97%（23,766 家）金额 < $10M，
    # 在散点图上会全部糊在左下角，既慢又一团黑。Top500 已覆盖 92.7% 支出，
    # 且 137 家 $0.1B 以上的供应商全部在列 —— 异常点一个不丢。
    sup500 = sup.head(500).copy()
    sup500.to_csv(OUT_DIM, index=False, encoding="utf-8", lineterminator="\n")

    # ---------- Top20 单独成表（20 行）----------
    # 为什么不在 Tableau 里用筛选器取前 20：
    #   quantitative filter 的 filter-group/included-values 属性在 10.5 里
    #   写法没十足把握，一旦有偏差图会静默空白（不报错，更难查）。
    #   直接给一张 20 行的表 = 零筛选、零转义、零风险。
    top20 = sup.sort_values("supplier_rank").head(20).copy()
    top20 = top20[["supplier_name", "supplier_rank", "total_spend_b", "order_count", "tier_cn"]]
    top20.to_csv(OUT_TOP20, index=False, encoding="utf-8", lineterminator="\n")

    # ---------- 报告 ----------
    for path, df in ((OUT_FACT, merged), (OUT_DIM, sup500),
                     (OUT_DIM_ALL, sup), (OUT_TOP20, top20)):
        size = os.path.getsize(path) / 1024 / 1024
        print(f"{os.path.basename(path)}: {len(df):,} 行  {len(df.columns)} 列  {size:.1f} MB")

    # 自检：换行 / 列数
    import csv as _csv
    for path in (OUT_FACT, OUT_DIM, OUT_DIM_ALL, OUT_TOP20):
        with open(path, encoding="utf-8", newline="") as f:
            rd = _csv.reader(f)
            h = next(rd)
            nl = bad = n = 0
            for row in rd:
                n += 1
                if len(row) != len(h):
                    bad += 1
                if any("\n" in v or "\r" in v for v in row):
                    nl += 1
        print(f"  自检 {os.path.basename(path)}: {n:,} 行 | 嵌入换行 {nl} | 列错位 {bad}")

    # 关键结论核对（必须和 matplotlib 报告一致）
    print()
    print("=== 关键结论（供标题写死前核对）===")
    print(f"总支出 ${total/1e9:.1f}B | 供应商 {len(sup):,} 家")
    print(f"Top10 供应商占比 {sup.head(10)['total_spend'].sum()/total*100:.1f}%")
    print(f"Top20 供应商占比 {sup.head(20)['total_spend'].sum()/total*100:.1f}%")
    ds = merged.groupby("dept_group")["total_price"].sum().sort_values(ascending=False)
    tot = ds.sum()
    print(f"Top15 部门占比 {ds[ds.index!='其他 96 个部门'].sum()/tot*100:.1f}%")
    print("  最大部门:", ds.index[0], f"${ds.iloc[0]/1e9:.2f}B", f"({ds.iloc[0]/tot*100:.1f}%)")
    ms = merged.groupby("method_class_cn")["total_price"].sum().sort_values(ascending=False)
    print("采购控制:", {k: f"${v/1e9:.0f}B ({v/tot*100:.1f}%)" for k, v in ms.items()})
    ts = merged.groupby("tier_cn")["total_price"].sum().sort_values(ascending=False)
    print("供应商分层支出:", {k: f"${v/1e9:.1f}B ({v/tot*100:.1f}%)" for k, v in ts.items()})


if __name__ == "__main__":
    main()
