# -*- coding: utf-8 -*-
"""
Tableau .twb 静态校验 —— 基础可读版（validate_twb_simple.py）
===========================================================

  对生成的 .twb 文件做 12 项静态检查：
    [1] XML 可解析
    [2] 顶层元素与顺序正确
    [3] datasource 字段与真实 CSV 列完全一致
    [4] 每个 column-instance 带 pivot='key'
    [5] column-instance 指向已声明的 column
    [6] rows/cols/encodings 引用都能找到对应实例
    [7] filter 与 slices 配套
    [8] sort 引用可解析
    [9] pane 子元素顺序 = mark → encodings → style
   [10] windows 与 worksheets 一一对应
   [11] 数据源目录真实存在
   [12] 颜色值全部小写十六进制
   [+]  dashboard 区域检查（坐标/重叠/引用）

运行方式：
    python scripts/validate_twb_simple.py

English:
Tableau .twb static validator (plain, readable version).

Runs 12 static checks on the generated .twb file:
  [1]  XML parses
  [2]  top-level elements and order are correct
  [3]  datasource fields match the real CSV columns exactly
  [4]  every column-instance carries pivot='key'
  [5]  column-instance points to a declared column
  [6]  rows/cols/encodings references resolve
  [7]  filters and slices go together
  [8]  sort references resolve
  [9]  pane child order = mark -> encodings -> style
  [10] windows and worksheets correspond 1:1
  [11] the data-source directory really exists
  [12] all color values are lowercase hex
  [+]  dashboard region checks (coordinates / overlap / references)

Run:
    python scripts/validate_twb_simple.py
"""

import os
import re
import sys
import xml.etree.ElementTree as ET

import pandas as pd

# ------------------------------------------------------------------
# 0. 路径配置
# ------------------------------------------------------------------
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TWB = os.path.join(ROOT, "ProcurementReconciliation_Tableau105.twb")
CSV_DIR = os.path.join(ROOT, "data", "pbip")

# 全局结果列表
FAILS = []
WARNS = []


# ------------------------------------------------------------------
# 工具函数
# ------------------------------------------------------------------
def ok(msg):
    print(f"  [OK]   {msg}")


def bad(msg):
    print(f"  [FAIL] {msg}")
    FAILS.append(msg)


def warn(msg):
    print(f"  [WARN] {msg}")
    WARNS.append(msg)


def strip_brackets(s):
    """[field] → field。"""
    if s:
        return s.strip("[]")
    return s


# ------------------------------------------------------------------
# 主流程
# ------------------------------------------------------------------
def main():
    if not os.path.exists(TWB):
        print(f"找不到 {TWB}")
        return 1

    print("=" * 66)
    print("Tableau .twb 静态校验（10.5 语法）")
    print("=" * 66)

    # ---- [1] XML 可解析 ----
    print("\n[1] XML 可解析")
    try:
        tree = ET.parse(TWB)
        root = tree.getroot()
        ok(f"解析成功，root={root.tag} version={root.get('version')}")
    except ET.ParseError as e:
        bad(f"XML 解析失败: {e}")
        return 1

    # ---- [2] 顶层元素与顺序 ----
    print("\n[2] 顶层元素与顺序")
    kids = [c.tag for c in root]
    expect = ["preferences", "style-theme", "datasources", "worksheets"]
    if "dashboards" in kids:
        expect.append("dashboards")
    expect.append("windows")
    if kids == expect:
        ok(f"顺序正确: {' → '.join(kids)}")
    else:
        bad(f"顺序/内容不符: 实际 {kids} / 期望 {expect}")
    if root.get("version") != "10.5":
        bad(f"version 应为 10.5，实际 {root.get('version')}")
    else:
        ok("version=10.5")

    # ---- [3] datasource 字段 vs 真实 CSV 列 ----
    print("\n[3] datasource 字段与 CSV 列一致")
    ds_elems = {}
    for d in root.find("datasources"):
        ds_elems[d.get("name")] = d

    for ds_name, ds in ds_elems.items():
        cap = ds.get("caption")
        conn = ds.find(".//connection[@class='textscan']")
        if conn is None:
            bad(f"{cap}: 找不到 textscan connection")
            continue
        directory = conn.get("directory")
        filename = conn.get("filename")
        csv_path = os.path.join(directory.replace("/", os.sep), filename)
        if not os.path.exists(csv_path):
            bad(f"{cap}: CSV 不存在 {csv_path}")
            continue
        real_cols = list(pd.read_csv(csv_path, nrows=0).columns)
        declared = []
        for c in ds.findall("column"):
            declared.append(strip_brackets(c.get("name")))

        miss = []
        for c in real_cols:
            if c not in declared:
                miss.append(c)
        extra = []
        for c in declared:
            if c not in real_cols:
                extra.append(c)

        if miss or extra:
            bad(f"{cap}: CSV {len(real_cols)} 列 / 声明 {len(declared)} 列 | 缺 {miss} | 多 {extra}")
        else:
            ok(f"{cap}: {len(declared)} 列与 CSV 完全一致")

        # relation 的 columns 块也要对得上
        rel_cols = ds.findall(".//relation/columns/column")
        if len(rel_cols) != len(real_cols):
            bad(f"{cap}: relation columns 声明 {len(rel_cols)} 个，CSV 有 {len(real_cols)} 列")
        meta = ds.findall(".//metadata-records/metadata-record[@class='column']")
        if len(meta) != len(real_cols):
            bad(f"{cap}: metadata-record {len(meta)} 条，CSV 有 {len(real_cols)} 列")

    # ---- [4]~[5] 逐个 worksheet：pivot / 悬空引用 ----
    print("\n[4] column-instance 的 pivot / 悬空引用")
    for w in root.find("worksheets"):
        wname = w.get("name")
        deps = w.find("table/view/datasource-dependencies")
        if deps is None:
            bad(f"{wname}: 缺少 datasource-dependencies")
            continue
        declared = set()
        for c in deps.findall("column"):
            declared.add(strip_brackets(c.get("name")))
        insts = deps.findall("column-instance")
        inst_names = set()
        for i in insts:
            inst_names.add(strip_brackets(i.get("name")))

        no_pivot = []
        for i in insts:
            if i.get("pivot") is None:
                no_pivot.append(i.get("name"))
        if no_pivot:
            bad(f"{wname}: 这些实例缺 pivot='key' -> {no_pivot}")

        dangling = []
        for i in insts:
            col_name = strip_brackets(i.get("column"))
            if col_name not in declared:
                dangling.append((i.get("name"), col_name))
        if dangling:
            bad(f"{wname}: 实例指向未声明列 -> {dangling}")

        if not no_pivot and not dangling:
            ok(f"{wname}: {len(declared)} 列 / {len(insts)} 实例，pivot 与引用均正确")

    # ---- [6] rows/cols/encodings 引用可解析 ----
    print("\n[5] rows/cols/encodings 引用可解析")
    for w in root.find("worksheets"):
        wname = w.get("name")
        deps = w.find("table/view/datasource-dependencies")
        inst_names = set()
        for i in deps.findall("column-instance"):
            inst_names.add(strip_brackets(i.get("name")))

        refs = []
        for tag in ("rows", "cols"):
            e = w.find(f"table/{tag}")
            if e is not None and e.text:
                found = re.findall(r"\[([^\]]+)\]", e.text)
                refs += found
        for enc in w.findall(".//pane/encodings/*"):
            col_attr = enc.get("column", "")
            found = re.findall(r"\[([^\]]+)\]", col_attr)
            refs += found

        # 去掉 datasource 名前缀
        filtered_refs = []
        for r in refs:
            if r not in ds_elems:
                filtered_refs.append(r)
        refs = filtered_refs

        unresolved = sorted(set(r for r in refs if r not in inst_names))
        if unresolved:
            bad(f"{wname}: 引用找不到实例 -> {unresolved}")
        else:
            ok(f"{wname}: {len(refs)} 处引用全部有对应实例")

    # ---- [7] filter 与 slices 配套 ----
    print("\n[6] filter 与 slices 配套")
    for w in root.find("worksheets"):
        wname = w.get("name")
        view = w.find("table/view")
        filters = view.findall("filter")
        slices = view.find("slices")
        fcols = []
        for f in filters:
            fcols.append(f.get("column"))
        scols = []
        if slices is not None:
            for c in slices.findall("column"):
                scols.append(c.text)
        for fc in fcols:
            if fc not in scols:
                bad(f"{wname}: filter 列 {fc} 未出现在 slices")
        if filters:
            all_ok = True
            for fc in fcols:
                if fc not in scols:
                    all_ok = False
            if all_ok:
                ok(f"{wname}: {len(filters)} 个 filter 都已登记到 slices")
        if not filters:
            ok(f"{wname}: 无 filter")
        # filter 的闭合与 min/max
        for f in filters:
            cls = f.get("class")
            if cls == "quantitative":
                if f.find("min") is None or f.find("max") is None:
                    bad(f"{wname}: quantitative filter 缺 min/max")

    # ---- [8] sort 引用可解析 ----
    print("\n[7] sort 引用可解析")
    for w in root.find("worksheets"):
        wname = w.get("name")
        view = w.find("table/view")
        deps = view.find("datasource-dependencies")
        inst_names = set()
        for i in deps.findall("column-instance"):
            inst_names.add(strip_brackets(i.get("name")))
        for s in view.findall("sort"):
            refs = []
            for attr in ("column", "using"):
                v = s.get(attr)
                if v:
                    found = re.findall(r"\[([^\]]+)\]", v)
                    for r in found:
                        if r not in ds_elems:
                            refs.append(r)
            un = [r for r in refs if r not in inst_names]
            if un:
                bad(f"{wname}: sort 引用未声明实例 {un}")
            else:
                ok(f"{wname}: sort({s.get('direction')}) 引用正确")

    # ---- [9] pane 子元素顺序 ----
    print("\n[8] pane 子元素顺序 = mark → encodings → style")
    pane_order_bad = False
    for w in root.find("worksheets"):
        wname = w.get("name")
        for pane in w.findall(".//pane"):
            tags = [c.tag for c in pane]
            order = [t for t in tags if t in ("mark", "encodings", "style")]
            expect_order = [t for t in ("mark", "encodings", "style") if t in order]
            if order != expect_order:
                bad(f"{wname}: pane 子元素顺序 {order}，应为 {expect_order}")
                pane_order_bad = True
    if not pane_order_bad:
        ok("全部 pane 的元素顺序正确")

    # ---- [10] windows 与 worksheets 对应 ----
    print("\n[9] windows 与 worksheets 对应")
    ws_names = set()
    for w in root.find("worksheets"):
        ws_names.add(w.get("name"))
    win_names = set()
    for w in root.find("windows"):
        if w.get("class") == "worksheet":
            win_names.add(w.get("name"))
    if ws_names != win_names:
        bad(f"不一致: sheets={sorted(ws_names)} / windows={sorted(win_names)}")
    else:
        ok(f"{len(ws_names)} 个工作表与窗口一一对应")

    # ---- [9b] dashboard 专项检查 ----
    print("\n[9b] dashboard 区域检查")
    dash_elems = root.find("dashboards")
    if dash_elems is None:
        ok("无 dashboard（跳过）")
    else:
        for dash in dash_elems:
            dname = dash.get("name")
            size = dash.find("size")
            if size is None:
                bad(f"{dname}: 缺少 <size>")
            zones = dash.findall(".//zone")
            if not zones:
                bad(f"{dname}: 没有 zone")
                continue
            ok_ids = True
            # 引用的工作表必须存在
            for z in zones:
                nm = z.get("name")
                if nm and z.get("type") is None and nm not in ws_names:
                    bad(f"{dname}: zone 引用了不存在的工作表 '{nm}'")
                    ok_ids = False
            # 坐标范围 0–100000
            for z in zones:
                for attr in ("x", "y", "w", "h"):
                    v = z.get(attr)
                    if v is None:
                        bad(f"{dname}: zone id={z.get('id')} 缺 {attr}")
                        ok_ids = False
                    elif not (0 <= float(v) <= 100000):
                        bad(f"{dname}: zone id={z.get('id')} 的 {attr}={v} 越界")
                        ok_ids = False
            # 同一父级下的子 zone 不得重叠
            for parent in zones:
                kids2 = list(parent)
                if len(kids2) < 2:
                    continue
                rects = []
                for z in kids2:
                    try:
                        rects.append((z.get("id"),
                                      float(z.get("x")), float(z.get("y")),
                                      float(z.get("w")), float(z.get("h"))))
                    except (TypeError, ValueError):
                        ok_ids = False
                        continue
                for i in range(len(rects)):
                    for j in range(i + 1, len(rects)):
                        i1, x1, y1, w1, h1 = rects[i]
                        i2, x2, y2, w2, h2 = rects[j]
                        ox = min(x1 + w1, x2 + w2) - max(x1, x2)
                        oy = min(y1 + h1, y2 + h2) - max(y1, y2)
                        if ox > 0 and oy > 0:
                            bad(f"{dname}: zone {i1} 与 {i2} 重叠 ({ox:.0f}×{oy:.0f})")
                            ok_ids = False
                # 子区域不超出父级
                px, py, pw, ph = (float(parent.get("x")), float(parent.get("y")),
                                  float(parent.get("w")), float(parent.get("h")))
                for i, x, y, w, h in rects:
                    if x < px or y < py or x + w > px + pw + 1 or y + h > py + ph + 1:
                        bad(f"{dname}: zone {i} 超出父容器范围")
                        ok_ids = False
            # id 唯一
            ids = []
            for z in zones:
                ids.append(z.get("id"))
            if len(ids) != len(set(ids)):
                bad(f"{dname}: zone id 有重复 {ids}")
                ok_ids = False
            if ok_ids:
                ok(f"{dname}: {len(zones)} 个 zone，坐标合法、无重叠、引用完整")

    # ---- [10] 数据源目录存在 ----
    print("\n[10] 数据源目录存在")
    for ds_name, ds in ds_elems.items():
        conn = ds.find(".//connection[@class='textscan']")
        d = conn.get("directory")
        if os.path.isdir(d):
            ok(f"{ds.get('caption')}: 目录存在 {d}")
        else:
            bad(f"{ds.get('caption')}: 目录不存在 {d}")

    # ---- [11] 颜色值必须小写十六进制 ----
    print("\n[11] 颜色值必须小写十六进制")
    raw = open(TWB, encoding="utf-8").read()
    hexes = set(re.findall(r"#[0-9A-Fa-f]{6}", raw))
    bad_hex = []
    for h in sorted(hexes):
        if not re.fullmatch(r"#[0-9a-f]{6}", h):
            bad_hex.append(h)
    if bad_hex:
        bad(f"大写/非法颜色值: {bad_hex}")
    else:
        ok(f"{len(hexes)} 个颜色值全部小写合法")

    # ---- [12] datasource 子元素顺序 ----
    print("\n[12] datasource 子元素顺序")
    order_ok = True
    for ds_name, ds in ds_elems.items():
        tags = [c.tag for c in ds]
        if "aliases" in tags and "style" in tags:
            if tags.index("aliases") > tags.index("style"):
                bad(f"{ds.get('caption')}: aliases 出现在 style 之后（XSD 要求在前）")
                order_ok = False
        if "style" in tags:
            si = tags.index("style")
            late_cols = []
            for t in tags[si:]:
                if t == "column":
                    late_cols.append(t)
            if late_cols:
                bad(f"{ds.get('caption')}: 有 column 出现在 style 之后")
                order_ok = False
    if order_ok:
        ok("aliases / column 均在 style 之前")

    # ---- 汇总 ----
    print("\n" + "=" * 66)
    if FAILS:
        print(f"FAIL  共 {len(FAILS)} 项问题")
        for f in FAILS:
            print(f"  · {f}")
        return 1
    print("PASS  全部通过")
    if WARNS:
        print(f"（另有 {len(WARNS)} 条警告）")
    print("=" * 66)
    return 0


if __name__ == "__main__":
    sys.exit(main())
