# -*- coding: utf-8 -*-
"""
采购数据清洗 —— 基础可读版（clean_data_simple.py）
=================================================
这个文件做的事，和原版 clean_data.py 完全一样：
  1. 读入加州采购的原始 CSV（约 90.9 万物理行）
  2. 把"钱"、"日期"、"数量"这些字段从文本变成真正的数值
  3. 从脏数据里抠出邮编、品类段、采购方式分类这三个派生字段
  4. 挑出要用的列，存成一张干净的 parquet 表

区别只是：本文件故意用"最朴素的写法"（for 循环、if 判断、普通函数），
每一步都写清楚了在做什么、为什么，方便你从头读懂。

运行方式（和原版一样）：
    python scripts/clean_data_simple.py [--src 原始CSV路径]
"""

import argparse
import os

import numpy as np
import pandas as pd

# ------------------------------------------------------------------
# 0. 路径配置
# ------------------------------------------------------------------
# 找项目根目录（本文件在 scripts/ 下，上一级就是项目根目录）
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "data", "output")          # 清洗结果放这里
DATA_NAME = "PURCHASE ORDER DATA EXTRACT 2012-2015_0.csv"
DEFAULT_DATA = os.path.join(ROOT, "data", "raw", DATA_NAME)  # 原始文件默认位置

# 确保输出目录存在（没有就建一个）
os.makedirs(OUT_DIR, exist_ok=True)


# ------------------------------------------------------------------
# 1. 采购方式 → 管控分类 的对照表
# ------------------------------------------------------------------
# 原始数据里"采购方式"有几十种写法，我们按业务把它们归成 3 类：
#   competitive : 走竞争/框架的正式采购（正常）
#   exempt      : 法律上豁免竞争（如服务类，合法）
#   flexible    : 非常规方法，值得复核（不一定有问题，但要盯）
METHOD_CLASS = {
    "competitive": [
        "Formal Competitive", "Informal Competitive", "Statewide Contract",
        "WSCA/Coop", "CMAS", "SB/DVBE Option",
    ],
    "exempt": [
        "Services are specifically exempt by statute",
        "Services are specifically exempt by policy",
    ],
    "flexible": [
        "NCB", "Emergency Purchase", "Fair and Reasonable",
        "Statement of Qualifications", "Special Category Request (SCR)",
        "Master Service Agreement", "Master Purchase/Price Agreement",
        "State Programs", "Software License Program", "LCB", "CRP",
        "State Price Schedule",
    ],
}

# 把上面的表"反过来"：现在我们要的是「一个采购方式 → 它属于哪一类」。
# 这样拿到一行数据的 Acquisition Method，就能直接查出它的分类。
method_class_lookup = {}
for category, method_list in METHOD_CLASS.items():   # 外层：遍历 3 个分类
    for one_method in method_list:                   # 内层：遍历该分类下的所有写法
        method_class_lookup[one_method] = category   # 记录：这个写法属于这个分类


# ------------------------------------------------------------------
# 2. 解析金额：把 "$1,234.56" 这种文本变成 1234.56
# ------------------------------------------------------------------
def parse_amount(text):
    """把像 '$1,234.56' 的单元格解析成 float；空值保持空值。"""
    if pd.isna(text):          # 空值（NaN）直接返回 NaN，不做处理
        return np.nan
    s = str(text)              # 转成字符串
    s = s.replace("$", "")     # 去掉美元符号
    s = s.replace(",", "")     # 去掉千分位逗号
    s = s.replace(" ", "")     # 去掉空格
    s = s.strip()              # 去掉首尾空白
    try:
        return float(s)        # 剩下的就是纯数字，转成 float
    except Exception:
        return np.nan          # 转不出来（脏数据）就记为缺失


# ------------------------------------------------------------------
# 3. 判断一个日期"年份是否正常"
# ------------------------------------------------------------------
def is_plausible_year(dt):
    """年份落在 2000~2026 才算正常；NaN 是"合法缺失"，不算脏数据。"""
    if pd.isna(dt):            # 缺失值：保留原样
        return True
    return 2000 <= dt.year <= 2026


# ------------------------------------------------------------------
# 4. 主流程
# ------------------------------------------------------------------
def main():
    # ---- 4.1 解析命令行参数，拿到原始文件路径 ----
    parser = argparse.ArgumentParser(description="清洗加州采购数据")
    parser.add_argument("--src", default=None, help=f"原始CSV路径（默认 {DEFAULT_DATA}）")
    args = parser.parse_args()
    src = args.src if args.src else DEFAULT_DATA

    # 文件不存在就报错退出，避免后面一堆诡异报错
    if not os.path.isfile(src):
        print(f"找不到原始文件：{src}")
        print("请用 --src 指定正确路径，例如：python scripts/clean_data_simple.py --src datasets/xxx.csv")
        return

    # ---- 4.2 读入原始 CSV ----
    df = pd.read_csv(src, encoding="utf-8")

    # ---- 4.3 把关键字段从文本转成真正的数值/日期 ----
    # 金额：Unit Price / Total Price
    df["unit_price"] = df["Unit Price"].apply(parse_amount)
    df["total_price"] = df["Total Price"].apply(parse_amount)

    # 数量：转成数值，转不出来的记为 NaN
    df["quantity"] = pd.to_numeric(df["Quantity"], errors="coerce")

    # 日期：按 "月/日/年" 格式解析，解析失败的记为 NaN
    df["creation_date"] = pd.to_datetime(
        df["Creation Date"], format="%m/%d/%Y", errors="coerce"
    )
    df["purchase_date"] = pd.to_datetime(
        df["Purchase Date"], format="%m/%d/%Y", errors="coerce"
    )

    # ---- 4.4 日期"年份合理性"检查 ----
    # 原始 Purchase Date 很脏（年份从 1911 到 2912 都有）。
    # 我们只保留年份在 2000~2026 的，其余变成缺失，
    # 免得下游分析不小心用到一个荒谬的日期。
    good_creation = []                     # 逐行判断创建日期
    for dt in df["creation_date"]:
        if is_plausible_year(dt):
            good_creation.append(dt)       # 年份正常：保留
        else:
            good_creation.append(None)     # 年份离谱：置为缺失
    df["creation_date"] = good_creation

    good_purchase = []                     # 逐行判断采购日期
    for dt in df["purchase_date"]:
        if is_plausible_year(dt):
            good_purchase.append(dt)
        else:
            good_purchase.append(None)
    df["purchase_date"] = good_purchase

    # ---- 4.5 派生字段1：邮编 zip_code ----
    # 原始 Location 字段长这样："94299\n(38.57, -121.48)"
    # 我们只要开头的 5 位邮编。
    zip_list = []
    for loc in df["Location"]:
        text = str(loc)                     # 转成字符串
        first_line = text.split("\n")[0]    # 取换行前第一行（就是邮编）
        zip_str = first_line.strip()        # 去掉首尾空白
        # 只有"刚好是 5 位数字"才认为真的是邮编，否则记为缺失
        if len(zip_str) == 5 and zip_str.isdigit():
            zip_list.append(zip_str)
        else:
            zip_list.append(None)
    df["zip_code"] = zip_list

    # ---- 4.6 派生字段2：UNSPSC 品类段 segment ----
    # UNSPSC 是 8 位商品分类码，前 2 位代表"大品类"（比如 85 是医疗）。
    segment_list = []
    for code in df["Normalized UNSPSC"]:
        if pd.isna(code):                   # 没有分类码：记为缺失
            segment_list.append(None)
        else:
            code_str = str(int(code))       # 先转 int 再转 str，去掉小数点后的 .0
            segment_list.append(code_str[:2])   # 取前 2 位作为品类段
    df["segment"] = segment_list

    # ---- 4.7 派生字段3：采购方式管控分类 method_class ----
    # 用前面建好的对照表，把每个采购方式归到 competitive / exempt / flexible
    method_list = []
    for m in df["Acquisition Method"]:
        if m in method_class_lookup:
            method_list.append(method_class_lookup[m])   # 能查到：给分类
        else:
            method_list.append(None)                     # 查不到：记缺失
    df["method_class"] = method_list

    # ---- 4.8 挑出我们要用的列，并改成好读的英文列名 ----
    # 原版列名有的太长、有的有空格，统一改成下划线小写，方便后面脚本用。
    old_names = [
        "creation_date", "purchase_date", "Fiscal Year",
        "Purchase Order Number", "Requisition Number",
        "Acquisition Type", "Acquisition Method", "method_class",
        "Department Name", "Supplier Name", "Supplier Code",
        "Item Name", "Item Description", "quantity",
        "unit_price", "total_price", "Normalized UNSPSC", "segment",
        "zip_code", "Location",
    ]
    new_names = {
        "Fiscal Year": "fiscal_year",
        "Purchase Order Number": "po_number",
        "Requisition Number": "requisition_number",
        "Acquisition Type": "acquisition_type",
        "Acquisition Method": "acquisition_method",
        "Department Name": "department",
        "Supplier Name": "supplier_name",
        "Supplier Code": "supplier_code",
        "Item Name": "item_name",
        "Item Description": "item_description",
        "Normalized UNSPSC": "unspsc",
        "Location": "location_raw",
    }

    # 只保留上面列表里的列（按这个顺序）
    clean = df[old_names]
    # 逐列改名：找到要改名的，改成新名字
    clean = clean.rename(columns=new_names)

    # ---- 4.9 存成干净的 parquet，并打印质量统计 ----
    out_path = os.path.join(OUT_DIR, "procurement_clean.parquet")
    clean.to_parquet(out_path, index=False)

    print("ROWS", len(clean))
    print("OUT", out_path)
    print("CREATION_DATE_VALID", int(clean["creation_date"].notna().sum()),
          "INVALID_OR_MISSING", int(clean["creation_date"].isna().sum()))
    print("PURCHASE_DATE_VALID", int(clean["purchase_date"].notna().sum()),
          "INVALID_OR_MISSING", int(clean["purchase_date"].isna().sum()))
    print("METHOD_CLASS_DIST")
    print(clean["method_class"].value_counts(dropna=False).to_string())
    print("ZIP_PRESENT", int(clean["zip_code"].notna().sum()))
    print("SEGMENT_PRESENT", int(clean["segment"].notna().sum()))


if __name__ == "__main__":
    main()
