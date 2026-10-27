# -*- coding: utf-8 -*-
"""
生成 Tableau .hyper 数据源 —— 基础可读版（build_hyper_simple.py）
=================================================================

  把 data/output/ 下的两张 parquet 表直接写到一个 .hyper 文件里，
  Tableau Desktop 双击即可连接。

输出：ProcurementReconciliation.hyper
  含两张表：
    fact_procurement (346k 行)  — 主表
    dim_supplier    (24.7k 行) — 供应商维表

运行方式：
    python scripts/build_hyper_simple.py

English:
Generate a Tableau .hyper data source (plain, readable version).

Writes the two cleaned parquet tables under data/output/ into a single
.hyper file that Tableau Desktop can connect to by double-clicking.

Output: ProcurementReconciliation.hyper
  Two tables inside:
    fact_procurement (346k rows)  - fact table
    dim_supplier    (24.7k rows)  - supplier dimension

Run:
    python scripts/build_hyper_simple.py

Note: depends on the tableauhyperapi SDK; without it only a syntax check is possible.
"""

import os

import pandas as pd
from tableauhyperapi import (
    HyperProcess, Connection, CreateMode, TableName,
    TableDefinition, SqlType, Inserter, Telemetry, Nullability,
)

# ------------------------------------------------------------------
# 0. 路径配置
# ------------------------------------------------------------------
# 项目根目录：根据本脚本位置向上两级得到（scripts/ 的上级 = 项目根），
# 不写死绝对路径，项目放到任何目录都能跑。
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARQUET_DIR = os.path.join(ROOT, "data", "output")
HYPER_PATH = os.path.join(ROOT, "ProcurementReconciliation.hyper")


# ------------------------------------------------------------------
# 1. 类型映射：pandas dtype → Tableau SqlType
# ------------------------------------------------------------------
def pandas_to_hyper_type(dtype, col_name):
    """把 pandas 的列类型转成 Tableau Hyper 的 SQL 类型。"""
    if pd.api.types.is_integer_dtype(dtype):
        # 用 bigint 避免溢出（total_price 可达 1e10）
        return SqlType.big_int()
    if pd.api.types.is_float_dtype(dtype):
        return SqlType.double()
    if pd.api.types.is_bool_dtype(dtype):
        return SqlType.boolean()
    if pd.api.types.is_datetime64_any_dtype(dtype):
        # 含日期+时间，统一用 timestamp
        return SqlType.timestamp()
    # 其余都是字符串
    return SqlType.text()


# ------------------------------------------------------------------
# 2. 值转换：把 pandas 单元值转成 hyper 能接受的 Python 值
# ------------------------------------------------------------------
def to_hyper_compatible(v):
    """处理 NaN → None，numpy datetime → Python datetime。"""
    if pd.isna(v):
        return None
    # numpy datetime64 → Python datetime（tableauhyperapi 不认 np.datetime64）
    if isinstance(v, pd.Timestamp):
        return v.to_pydatetime()
    # pandas/numpy datetime64
    if hasattr(v, "to_pydatetime"):
        return v.to_pydatetime()
    return v


# ------------------------------------------------------------------
# 3. 把一个 DataFrame 写成 hyper 里的一张表
# ------------------------------------------------------------------
def write_table(connection, df, table_name, schema="public"):
    """把 DataFrame 写成 .hyper 里的一张表。

    步骤：
      1. 用原始 dtype 推断 SqlType
      2. 创建表
      3. 插入数据（逐行转换类型）
    """
    # 3.1 推断每列的 SQL 类型
    col_types = []
    for c in df.columns:
        sql_type = pandas_to_hyper_type(df[c].dtype, c)
        col_types.append((c, sql_type))

    # 3.2 创建表
    columns_def = []
    for c, t in col_types:
        col_def = TableDefinition.Column(
            name=c, type=t, nullability=Nullability.NULLABLE
        )
        columns_def.append(col_def)

    tbl_def = TableDefinition(
        table_name=TableName(schema, table_name),
        columns=columns_def,
    )
    connection.catalog.create_table(tbl_def)
    print(f"  + 表 {schema}.{table_name} 创建完成 ({len(df.columns)} 列)")

    # 3.3 分类列类型（用于逐行转换）
    datetime_cols = set()
    int_cols = set()
    float_cols = set()
    bool_cols = set()

    for c in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[c]):
            datetime_cols.add(c)
        elif pd.api.types.is_integer_dtype(df[c]) and not pd.api.types.is_bool_dtype(df[c]):
            int_cols.add(c)
        elif pd.api.types.is_float_dtype(df[c]):
            float_cols.add(c)
        elif pd.api.types.is_bool_dtype(df[c]):
            bool_cols.add(c)

    # 3.4 逐行构造要插入的数据
    rows = []
    for rec in df.to_records(index=False):
        new_row = []
        for c, v in zip(df.columns, rec):
            if c in datetime_cols:
                if pd.isna(v):
                    new_row.append(None)
                else:
                    new_row.append(pd.Timestamp(v).to_pydatetime())
            elif c in int_cols:
                # pandas nullable Int64 可能是 pd.NA
                if pd.isna(v):
                    new_row.append(None)
                else:
                    new_row.append(int(v))
            elif c in float_cols:
                if pd.isna(v):
                    new_row.append(None)
                else:
                    new_row.append(float(v))
            elif c in bool_cols:
                if pd.isna(v):
                    new_row.append(None)
                else:
                    new_row.append(bool(v))
            else:
                # 字符串列
                if pd.isna(v):
                    new_row.append(None)
                else:
                    new_row.append(str(v))
        rows.append(tuple(new_row))

    # 3.5 批量插入（每批 10000 行）
    with Inserter(connection, tbl_def) as inserter:
        BATCH = 10000
        for i in range(0, len(rows), BATCH):
            batch = rows[i:i + BATCH]
            inserter.add_rows(batch)
        inserter.execute()

    print(f"    插入 {len(rows):,} 行")


# ------------------------------------------------------------------
# 4. 主流程
# ------------------------------------------------------------------
def main():
    # 读 parquet（保留 datetime 类型）
    fact = pd.read_parquet(os.path.join(PARQUET_DIR, "procurement_clean.parquet"))
    dim = pd.read_parquet(os.path.join(PARQUET_DIR, "supplier_segmentation.parquet"))

    print("读取 parquet 完成:")
    print(f"  fact_procurement: {len(fact):,} 行  {len(fact.columns)} 列")
    print(f"  dim_supplier:     {len(dim):,} 行  {len(dim.columns)} 列")

    # 删掉旧 .hyper
    if os.path.exists(HYPER_PATH):
        os.remove(HYPER_PATH)
        print(f"删除旧文件: {HYPER_PATH}")

    print(f"\n启动 Hyper 引擎，写入: {HYPER_PATH}")

    with HyperProcess(telemetry=Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU) as hyper:
        with Connection(endpoint=hyper.endpoint,
                        database=HYPER_PATH,
                        create_mode=CreateMode.CREATE_AND_REPLACE) as conn:
            write_table(conn, fact, "fact_procurement")
            write_table(conn, dim, "dim_supplier")

            # 验证：列出 public schema 下的表
            print(f"\n验证 .hyper 里的表:")
            tables = conn.catalog.get_table_names("public")
            for t in tables:
                cnt = conn.execute_list_query(
                    f'SELECT COUNT(*) FROM {t}')[0][0]
                print(f"  {t.schema_name}.{t.name}: {cnt:,} 行")

    print(f"\n完成。Tableau Desktop 打开 → 连接到数据源 → 选 ProcurementReconciliation.hyper")


if __name__ == "__main__":
    main()
