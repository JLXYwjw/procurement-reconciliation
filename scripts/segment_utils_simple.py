# -*- coding: utf-8 -*-
"""
供应商分层标签工具 —— 基础可读版（segment_utils_simple.py）
=========================================================
这个文件做的事，和原版 segment_utils.py 完全一样：
  把聚类后的供应商按业务含义分成 4 层：
    - core_strategic（核心战略）：重复采购（活跃年数 >= 2）且支出最高的聚类
    - oneoff_large（一次性大额）：单年大额支出的聚类
    - regular（常规）：其余按支出排前面的
    - tail（长尾）：其余按支出排后面的

这个文件只依赖 pandas，可以独立单元测试，不需要跑全量数据。

运行方式：本文件是工具模块，被 supplier_cluster_simple.py 导入使用。
"""

import pandas as pd


# ------------------------------------------------------------------
# 核心函数：给每个聚类打业务标签
# ------------------------------------------------------------------
def label_tiers(prof):
    """根据聚类画像，给每个聚类分配业务层级名称。

    参数:
        prof: DataFrame，索引是聚类编号，列包括：
              n（供应商数）、spend（总支出）、med_spend（中位数支出）、
              med_seg_share（品类集中度中位数）、med_dept_share（部门集中度中位数）、
              med_years（活跃年数中位数）、med_freq（下单频率中位数）

    返回:
        pd.Series，索引是聚类编号，值是层级名称（core_strategic / oneoff_large /
        regular / tail）
    """

    # ---- 第一步：找出"核心战略"聚类 ----
    # 条件：活跃年数中位数 >= 2（即这个聚类的供应商是"回头客"）
    # 在这些聚类里，取总支出最高的那个作为核心
    recur_mask = prof["med_years"] >= 2
    recur = prof[recur_mask].sort_values("spend", ascending=False)

    if len(recur) > 0:
        core_c = recur.index[0]
    else:
        # 如果没有任何聚类满足"重复采购"，就退而求其次：取总支出最高的
        core_c = prof.sort_values("spend", ascending=False).index[0]

    # ---- 第二步：找出"一次性大额"聚类 ----
    # 条件：活跃年数中位数 < 2（即这个聚类的供应商基本只出现一年）
    # 在这些里取总支出最高的
    once_mask = prof["med_years"] < 2
    once = prof[once_mask].sort_values("spend", ascending=False)

    if len(once) > 0:
        oneoff_c = once.index[0]
    else:
        oneoff_c = None

    # ---- 第三步：剩下的聚类按支出排序，前一半叫"常规"，后一半叫"长尾" ----
    # 先收集所有不是 core 和 oneoff 的聚类编号，同时记下各自的支出金额
    rest_with_spend = []
    for c in prof.index:
        if c == core_c:
            continue
        if c is not None and oneoff_c is not None and c == oneoff_c:
            continue
        spend_val = prof.loc[c, "spend"]
        rest_with_spend.append((c, spend_val))

    # 按支出从高到低排序（用普通函数做 key，不用 lambda）
    def get_spend(item):
        return item[1]

    rest_with_spend.sort(key=get_spend, reverse=True)

    # 只保留聚类编号，丢掉支出金额
    rest = []
    for item in rest_with_spend:
        rest.append(item[0])

    # ---- 第四步：组装标签字典 ----
    names = {}
    names[core_c] = "core_strategic"

    if oneoff_c is not None:
        names[oneoff_c] = "oneoff_large"

    # rest 里第一个叫 regular，第二个叫 tail
    # （原版是 ["regular", "tail"][i]，这里改成 if 判断，更直观）
    for i, c in enumerate(rest):
        if i == 0:
            names[c] = "regular"
        elif i == 1:
            names[c] = "tail"
        else:
            # 理论上 rest 最多两个，但保险起见兜底
            names[c] = "tail"

    # 转成 Series，按原始 prof 的索引顺序排列
    result = pd.Series(names)
    result = result.reindex(prof.index)
    return result
