# -*- coding: utf-8 -*-
r"""
Tableau .twb 静态校验（针对 10.5 语法）。

为什么需要这个：手写 XML 最怕「引用了不存在的字段」——Tableau 打开时
不会说"某字段不存在"，而是整个工作簿加载失败或图空白，很难定位。
所以把能静态查的全部查掉。

检查项：
  [1] XML 可解析
  [2] 必备顶层元素与顺序（preferences → style-theme → datasources → worksheets → windows）
  [3] 每个 datasource 的字段声明与真实 CSV 列完全一致（无多、无缺）
  [4] 每个 column-instance 都带 pivot='key'（10.5 XSD 必需）
  [5] 每个 column-instance 指向的 column 已在同层声明
  [6] worksheet 的 rows/cols/encodings 引用都能在 deps 里找到实例
  [7] <filter> 的列都出现在 <slices> 里
  [8] <sort> 的 column/using 都是已声明实例
  [9] pane 内元素顺序 = mark → encodings → style
  [10] windows 里的工作表名与 worksheets 一致
  [11] 文件名里的目录真实存在

用法：python scripts/validate_twb.py
"""
import os
import re
import sys
import xml.etree.ElementTree as ET

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TWB = os.path.join(ROOT, "ProcurementReconciliation_Tableau105.twb")
CSV_DIR = os.path.join(ROOT, "data", "pbip")

FAILS = []
WARNS = []


def ok(msg):
    print(f"  [OK]   {msg}")


def bad(msg):
    print(f"  [FAIL] {msg}")
    FAILS.append(msg)


def warn(msg):
    print(f"  [WARN] {msg}")
    WARNS.append(msg)


def strip_brackets(s):
    """[field] -> field；注意 ET.get 返回的是带方括号的原始串"""
    return s.strip("[]") if s else s


def main() -> int:
    if not os.path.exists(TWB):
        print(f"找不到 {TWB}")
        return 1

    print("=" * 66)
    print("Tableau .twb 静态校验（10.5 语法）")
    print("=" * 66)

    # [1] XML
    print("\n[1] XML 可解析")
    try:
        tree = ET.parse(TWB)
        root = tree.getroot()
        ok(f"解析成功，root={root.tag} version={root.get('version')}")
    except ET.ParseError as e:
        bad(f"XML 解析失败: {e}")
        return 1

    # [2] 顶层结构与顺序
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

    # [3] datasource 字段 vs 真实 CSV 列
    print("\n[3] datasource 字段与 CSV 列一致")
    ds_elems = {d.get("name"): d for d in root.find("datasources")}
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
        declared = [strip_brackets(c.get("name")) for c in ds.findall("column")]
        miss = [c for c in real_cols if c not in declared]
        extra = [c for c in declared if c not in real_cols]
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

    # [4]~[9] 逐个 worksheet
    print("\n[4] column-instance 的 pivot / 悬空引用")
    for w in root.find("worksheets"):
        wname = w.get("name")
        deps = w.find("table/view/datasource-dependencies")
        if deps is None:
            bad(f"{wname}: 缺少 datasource-dependencies")
            continue
        declared = {strip_brackets(c.get("name")) for c in deps.findall("column")}
        insts = deps.findall("column-instance")
        inst_names = {strip_brackets(i.get("name")) for i in insts}

        no_pivot = [i.get("name") for i in insts if i.get("pivot") is None]
        if no_pivot:
            bad(f"{wname}: 这些实例缺 pivot='key' -> {no_pivot}")
        dangling = [(i.get("name"), strip_brackets(i.get("column")))
                    for i in insts if strip_brackets(i.get("column")) not in declared]
        if dangling:
            bad(f"{wname}: 实例指向未声明列 -> {dangling}")
        if not no_pivot and not dangling:
            ok(f"{wname}: {len(declared)} 列 / {len(insts)} 实例，pivot 与引用均正确")

    print("\n[5] rows/cols/encodings 引用可解析")
    for w in root.find("worksheets"):
        wname = w.get("name")
        deps = w.find("table/view/datasource-dependencies")
        inst_names = {strip_brackets(i.get("name")) for i in deps.findall("column-instance")}
        refs = []
        for tag in ("rows", "cols"):
            e = w.find(f"table/{tag}")
            if e is not None and e.text:
                refs += re.findall(r"\[([^\]]+)\]", e.text)
        for enc in w.findall(".//pane/encodings/*"):
            refs += re.findall(r"\[([^\]]+)\]", enc.get("column", ""))
        # 去掉 datasource 名前缀
        refs = [r for r in refs if r not in ds_elems]
        unresolved = sorted({r for r in refs if r not in inst_names})
        if unresolved:
            bad(f"{wname}: 引用找不到实例 -> {unresolved}")
        else:
            ok(f"{wname}: {len(refs)} 处引用全部有对应实例")

    print("\n[6] filter 与 slices 配套")
    for w in root.find("worksheets"):
        wname = w.get("name")
        view = w.find("table/view")
        filters = view.findall("filter")
        slices = view.find("slices")
        fcols = [f.get("column") for f in filters]
        scols = [c.text for c in slices.findall("column")] if slices is not None else []
        for fc in fcols:
            if fc not in scols:
                bad(f"{wname}: filter 列 {fc} 未出现在 slices")
        if filters and all(fc in scols for fc in fcols):
            ok(f"{wname}: {len(filters)} 个 filter 都已登记到 slices")
        if not filters:
            ok(f"{wname}: 无 filter")
        # filter 的闭合与 min/max
        for f in filters:
            cls = f.get("class")
            if cls == "quantitative":
                if f.find("min") is None or f.find("max") is None:
                    bad(f"{wname}: quantitative filter 缺 min/max")

    print("\n[7] sort 引用可解析")
    for w in root.find("worksheets"):
        wname = w.get("name")
        view = w.find("table/view")
        deps = view.find("datasource-dependencies")
        inst_names = {strip_brackets(i.get("name")) for i in deps.findall("column-instance")}
        for s in view.findall("sort"):
            refs = []
            for attr in ("column", "using"):
                v = s.get(attr)
                if v:
                    refs += [r for r in re.findall(r"\[([^\]]+)\]", v) if r not in ds_elems]
            un = [r for r in refs if r not in inst_names]
            if un:
                bad(f"{wname}: sort 引用未声明实例 {un}")
            else:
                ok(f"{wname}: sort({s.get('direction')}) 引用正确")

    print("\n[8] pane 子元素顺序 = mark → encodings → style")
    for w in root.find("worksheets"):
        wname = w.get("name")
        for pane in w.findall(".//pane"):
            tags = [c.tag for c in pane]
            order = [t for t in tags if t in ("mark", "encodings", "style")]
            expect_order = [t for t in ("mark", "encodings", "style") if t in order]
            if order != expect_order:
                bad(f"{wname}: pane 子元素顺序 {order}，应为 {expect_order}")
        else:
            pass
    if not any("pane 子元素顺序" in f for f in FAILS):
        ok("全部 pane 的元素顺序正确")

    print("\n[9] windows 与 worksheets 对应")
    ws_names = {w.get("name") for w in root.find("worksheets")}
    win_names = {w.get("name") for w in root.find("windows") if w.get("class") == "worksheet"}
    if ws_names != win_names:
        bad(f"不一致: sheets={sorted(ws_names)} / windows={sorted(win_names)}")
    else:
        ok(f"{len(ws_names)} 个工作表与窗口一一对应")

    # [9b] dashboard 专项检查
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
            # 1) 引用的工作表必须存在
            for z in zones:
                nm = z.get("name")
                if nm and z.get("type") is None and nm not in ws_names:
                    bad(f"{dname}: zone 引用了不存在的工作表 '{nm}'")
                    ok_ids = False
            # 2) 坐标范围 0–100000
            for z in zones:
                for attr in ("x", "y", "w", "h"):
                    v = z.get(attr)
                    if v is None:
                        bad(f"{dname}: zone id={z.get('id')} 缺 {attr}")
                        ok_ids = False
                    elif not (0 <= float(v) <= 100000):
                        bad(f"{dname}: zone id={z.get('id')} 的 {attr}={v} 越界")
                        ok_ids = False
            # 3) 同一父级下的子 zone 不得重叠
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
                        # 允许恰好相邻（边界相等不算重叠）
                        ox = min(x1 + w1, x2 + w2) - max(x1, x2)
                        oy = min(y1 + h1, y2 + h2) - max(y1, y2)
                        if ox > 0 and oy > 0:
                            bad(f"{dname}: zone {i1} 与 {i2} 重叠 ({ox:.0f}×{oy:.0f})")
                            ok_ids = False
                # 4) 子区域不超出父级
                px, py, pw, ph = (float(parent.get("x")), float(parent.get("y")),
                                 float(parent.get("w")), float(parent.get("h")))
                for i, x, y, w, h in rects:
                    if x < px or y < py or x + w > px + pw + 1 or y + h > py + ph + 1:
                        bad(f"{dname}: zone {i} 超出父容器范围")
                        ok_ids = False
            # 5) id 唯一
            ids = [z.get("id") for z in zones]
            if len(ids) != len(set(ids)):
                bad(f"{dname}: zone id 有重复 {ids}")
                ok_ids = False
            if ok_ids:
                ok(f"{dname}: {len(zones)} 个 zone，坐标合法、无重叠、引用完整")

    print("\n[10] 数据源目录存在")
    for ds_name, ds in ds_elems.items():
        conn = ds.find(".//connection[@class='textscan']")
        d = conn.get("directory")
        if os.path.isdir(d):
            ok(f"{ds.get('caption')}: 目录存在 {d}")
        else:
            bad(f"{ds.get('caption')}: 目录不存在 {d}")

    # [11] 颜色格式：10.5 XSD 的 facet 是 #[0-9a-f]{6} —— 大写字母直接判不合法
    print("\n[11] 颜色值必须小写十六进制")
    raw = open(TWB, encoding="utf-8").read()
    hexes = set(re.findall(r"#[0-9A-Fa-f]{6}", raw))
    bad_hex = sorted(h for h in hexes if not re.fullmatch(r"#[0-9a-f]{6}", h))
    if bad_hex:
        bad(f"大写/非法颜色值: {bad_hex}")
    else:
        ok(f"{len(hexes)} 个颜色值全部小写合法")

    # [12] datasource 子元素顺序：aliases 必须在 style 之前
    print("\n[12] datasource 子元素顺序")
    order_ok = True
    for ds_name, ds in ds_elems.items():
        tags = [c.tag for c in ds]
        if "aliases" in tags and "style" in tags:
            if tags.index("aliases") > tags.index("style"):
                bad(f"{ds.get('caption')}: aliases 出现在 style 之后（XSD 要求在前）")
                order_ok = False
        # column 必须在 style 之前
        if "style" in tags:
            si = tags.index("style")
            late_cols = [t for t in tags[si:] if t == "column"]
            if late_cols:
                bad(f"{ds.get('caption')}: 有 column 出现在 style 之后")
                order_ok = False
    if order_ok:
        ok("aliases / column 均在 style 之前")

    # 汇总
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
