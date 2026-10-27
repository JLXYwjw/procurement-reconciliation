# -*- coding: utf-8 -*-
"""
PBIP 静态校验器 —— 基础可读版（validate_pbip_simple.py）
=======================================================

  对生成的 PBIP 工程做静态检查，覆盖 12 个检查项：
    [1] .pbip 指针文件格式正确
    [2] 必需文件清单齐全
    [3] version.json 符合 semver 格式
    [4] report.json 不是旧版 Layout（Legacy 检测）
    [5] pageOrder 与 pages/ 目录一致
    [6] TMDL 缩进合法性
    [7] TMDL 字符串里无 Windows 反斜杠
    [8] 关系只声明在 relationships.tmdl
    [9] visual.json 的 position 在根层 + 每个 projection 有 queryRef
   [10] 悬空引用检测（Entity/Property 必须存在）
   [11] partition CSV 真实存在 + 列数一致
   [12] 页面排版几何（越界/重叠）

运行方式：
    python scripts/validate_pbip_simple.py

English:
PBIP static validator (plain, readable version).

Runs 12 static checks on the generated PBIP project:
  [1]  .pbip pointer file is well-formed
  [2]  required file list is complete
  [3]  version.json follows semver
  [4]  report.json is NOT the legacy Layout (Legacy detection)
  [5]  pageOrder matches the pages/ directory
  [6]  TMDL indentation is valid
  [7]  no Windows backslashes inside TMDL strings
  [8]  relationships are declared only in relationships.tmdl
  [9]  visual.json positions at root level, every projection has a queryRef
  [10] no dangling references (every Entity/Property exists)
  [11] partition CSVs exist and column counts match
  [12] page layout geometry (out-of-bounds / overlap)

Run:
    python scripts/validate_pbip_simple.py
"""

import glob
import json
import os
import re
from pathlib import Path

# ------------------------------------------------------------------
# 0. 路径配置
# ------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
REPORT_DIR = str(ROOT / "ProcurementReconciliation.Report")
PROJ = "ProcurementReconciliation"
CSV_DIR = ROOT / "data" / "pbip"
SM_DIR = ROOT / f"{PROJ}.SemanticModel"
RP_DIR = ROOT / f"{PROJ}.Report"
PBIP_FILE = ROOT / f"{PROJ}.pbip"

# 全局问题列表
issues = []


# ------------------------------------------------------------------
# 工具函数
# ------------------------------------------------------------------
def ok(msg):
    print(f"  [OK]   {msg}")


def bad(msg):
    print(f"  [FAIL] {msg}")
    issues.append(msg)


# ------------------------------------------------------------------
# 主流程
# ------------------------------------------------------------------
print("=" * 72)
print(f"PBIP 静态校验  ({PROJ})")
print("=" * 72)

# ---- [1] .pbip 指针 + artifacts 只允许 report ----
print("\n[1] .pbip 指针 + artifacts 只允许 report")
if not PBIP_FILE.exists():
    bad(f"缺少 {PBIP_FILE.name}")
else:
    cfg = json.loads(PBIP_FILE.read_text(encoding="utf-8-sig"))
    if not cfg.get("$schema"):
        bad(".pbip 缺 $schema")
    else:
        ok("$schema 存在")
    if cfg.get("version") != "1.0":
        bad(f".pbip version 异常: {cfg.get('version')}")
    else:
        ok("version=1.0")
    art = cfg.get("artifacts", [])
    for i, a in enumerate(art):
        for k in a.keys():
            if k != "report":
                bad(f"artifacts[{i}] 含非法键 '{k}'（只允许 report）")
            else:
                ok(f"artifacts[{i}].report.path = {a[k].get('path')}")
                tgt = ROOT / a[k].get("path")
                if tgt.exists():
                    ok("  -> 路径存在")
                else:
                    bad(f"  -> 路径缺失: {tgt}")

# ---- [2] 必需文件清单 ----
print("\n[2] 必需文件清单")
required = [
    SM_DIR / ".platform",
    SM_DIR / "definition.pbism",
    SM_DIR / "definition" / "model.tmdl",
    SM_DIR / "definition" / "database.tmdl",
    SM_DIR / "definition" / "expressions.tmdl",
    SM_DIR / "definition" / "relationships.tmdl",
    SM_DIR / "definition" / "cultures" / "zh-CN.tmdl",
    RP_DIR / ".platform",
    RP_DIR / "definition.pbir",
    RP_DIR / "definition" / "version.json",
    RP_DIR / "definition" / "report.json",
    RP_DIR / "definition" / "pages" / "pages.json",
]
for p in required:
    if p.exists():
        ok(p.relative_to(ROOT))
    else:
        bad(f"缺失: {p.relative_to(ROOT)}")

# ---- [3] version.json semver ----
print("\n[3] version.json semver")
v = json.loads((RP_DIR / "definition" / "version.json").read_text(encoding="utf-8"))
ver = v.get("version", "")
SEMVER_PATTERN = re.compile(r"^[0-9]+\.[0-9]+\.0$")
if SEMVER_PATTERN.match(ver):
    ok(f"version={ver} (符合 semver)")
else:
    bad(f"version={ver} 不符合 ^[0-9]+\\.[0-9]+\\.0$")

# ---- [4] report.json Legacy 检测 ----
print("\n[4] report.json Legacy 检测")
r = json.loads((RP_DIR / "definition" / "report.json").read_text(encoding="utf-8"))
if "sections" in r or "activeSectionIndex" in r:
    bad("report.json 是旧版 Layout（含 sections/activeSectionIndex），必须重写为 PBIR")
else:
    ok("PBIR 格式（无 sections）")
if "themeCollection" not in r:
    bad("report.json 缺 themeCollection")
else:
    ok("themeCollection 存在")

# ---- [5] pageOrder 与目录一致 ----
print("\n[5] pageOrder 与 pages/ 目录一致")
pj = json.loads((RP_DIR / "definition" / "pages" / "pages.json").read_text(encoding="utf-8"))
order = pj.get("pageOrder", [])
actual_dirs = []
for p in (RP_DIR / "definition" / "pages").iterdir():
    if p.is_dir() and p.name.startswith("ReportSection"):
        actual_dirs.append(p.name)
actual = sorted(actual_dirs)
if order == actual:
    ok(f"pageOrder ({len(order)} 页) 与目录一致: {order}")
else:
    bad(f"pageOrder={order} != 实际目录={actual}")
if pj.get("activePageName") not in order:
    bad(f"activePageName={pj.get('activePageName')} 不在 pageOrder 里")
else:
    ok(f"activePageName={pj.get('activePageName')}")

# ---- [6] TMDL 缩进合法性 ----
print("\n[6] TMDL 缩进合法性")
SCALAR_PATTERN = re.compile(r"^\t*([A-Za-z][A-Za-z0-9_.]*)\s*:")
EQ_PATTERN = re.compile(r"^\t*([A-Za-z][A-Za-z0-9_.]*)\s*=")
indent_bad = 0
scan_root = SM_DIR / "definition"

for f in sorted(scan_root.rglob("*.tmdl")):
    lines = f.read_text(encoding="utf-8").split("\n")
    prev_indent = -1
    prev_kind = None
    for n, line in enumerate(lines, 1):
        if not line.strip() or line.lstrip().startswith("///"):
            continue
        ind = len(line) - len(line.lstrip("\t"))
        if line[:ind].replace("\t", "") != "":
            bad(f"{f.name}:{n} 缩进混用了空格")
            indent_bad += 1
            continue
        ms = SCALAR_PATTERN.match(line)
        me = EQ_PATTERN.match(line)
        if ms:
            prev_kind = "scalar"
            prev_indent = ind
        elif me:
            prev_kind = "eq"
            prev_indent = ind
        else:
            if prev_kind == "scalar" and ind > prev_indent:
                bad(f"{f.name}:{n} 标量属性后跟更深子行（标量没有子对象）")
                indent_bad += 1
            prev_kind = "other"
            prev_indent = ind

if indent_bad == 0:
    ok("TMDL 缩进通过")
else:
    bad(f"TMDL 缩进有 {indent_bad} 处问题")

# ---- [7] TMDL 字符串里无 Windows 反斜杠 ----
print("\n[7] TMDL 字符串里无 Windows 反斜杠")
bs_bad = 0
STRING_PATTERN = re.compile(r'"([^"]*)"')
for f in sorted(scan_root.rglob("*.tmdl")):
    txt = f.read_text(encoding="utf-8")
    for m in STRING_PATTERN.finditer(txt):
        s = m.group(1)
        if "\\" in s:
            bad(f"{f.name}: 字符串里含反斜杠: {s}")
            bs_bad += 1
if bs_bad == 0:
    ok("无反斜杠字符串")

# ---- [8] 关系只声明在 relationships.tmdl ----
print("\n[8] 关系只声明在 relationships.tmdl（不在 model.tmdl）")
model_txt = (SM_DIR / "definition" / "model.tmdl").read_text(encoding="utf-8")
REL_PATTERN = re.compile(r"^\trelationship\s", flags=re.M)
if REL_PATTERN.search(model_txt):
    bad("model.tmdl 里含 relationship（必须只放 relationships.tmdl）")
else:
    ok("model.tmdl 无 relationship")

rel_txt = (SM_DIR / "definition" / "relationships.tmdl").read_text(encoding="utf-8")
REL_COUNT_PATTERN = re.compile(r"^relationship\s", flags=re.M)
n_rel = len(REL_COUNT_PATTERN.findall(rel_txt))
ok(f"relationships.tmdl 含 {n_rel} 条关系")

# ---- [9] visual.json: position 在根层 + projection 有 queryRef ----
print("\n[9] visual.json position + queryRef")
n_pos_bad = 0
n_qref_bad = 0
n_visual = 0
for vf in sorted((RP_DIR / "definition" / "pages").rglob("visual.json")):
    n_visual += 1
    v = json.loads(vf.read_text(encoding="utf-8"))
    if "layouts" in v:
        bad(f"{vf.relative_to(ROOT)}: 含 layouts（必须根层 position）")
        n_pos_bad += 1
    if "position" not in v:
        bad(f"{vf.relative_to(ROOT)}: 缺 position")
        n_pos_bad += 1
    qs = v.get("visual", {}).get("query", {}).get("queryState", {})
    for role, st in qs.items():
        for i, proj in enumerate(st.get("projections", [])):
            if "queryRef" not in proj:
                bad(f"{vf.relative_to(ROOT)}: {role}[{i}] 缺 queryRef")
                n_qref_bad += 1
            if "field" not in proj:
                bad(f"{vf.relative_to(ROOT)}: {role}[{i}] 缺 field")

if n_pos_bad == 0 and n_qref_bad == 0:
    ok(f"全部 {n_visual} 个 visual: position 在根层 + 每个 projection 有 queryRef")

# ---- [10] 悬空引用检测 ----
print("\n[10] 悬空引用检测（Entity / Property 必须在表里存在）")
table_cols = {}
TABLE_NAME_PATTERN = re.compile(r"^table\s+'?([^\s']+)'?\s*$", flags=re.M)
COL_PATTERN = re.compile(r"^\tcolumn\s+'?\[?([^'\]]+)'?\]?", flags=re.M)
MEAS_PATTERN = re.compile(r"^\tmeasure\s+'([^']+)'", flags=re.M)

for tf in sorted((SM_DIR / "definition" / "tables").glob("*.tmdl")):
    txt = tf.read_text(encoding="utf-8")
    mt = TABLE_NAME_PATTERN.match(txt)
    tname = mt.group(1) if mt else tf.stem
    cols = set(COL_PATTERN.findall(txt))
    meas = set(MEAS_PATTERN.findall(txt))
    table_cols[tname] = cols | meas
    print(f"   表 {tname}: {len(cols)} 列 + {len(meas)} 度量值")

n_dangling = 0
for vf in sorted((RP_DIR / "definition" / "pages").rglob("visual.json")):
    v = json.loads(vf.read_text(encoding="utf-8"))
    qs = v.get("visual", {}).get("query", {}).get("queryState", {})
    for role, st in qs.items():
        for i, proj in enumerate(st.get("projections", [])):
            fld = proj.get("field", {})
            for kind in ("Column", "Measure"):
                if kind in fld:
                    e = fld[kind].get("Expression", {}).get("SourceRef", {}).get("Entity")
                    p = fld[kind].get("Property")
                    if e and e not in table_cols:
                        bad(f"{vf.name} {role}[{i}] 引用未知 Entity '{e}'")
                        n_dangling += 1
                    elif e and p and p not in table_cols[e]:
                        bad(f"{vf.name} {role}[{i}] 引用 {e}.{p} 不存在")
                        n_dangling += 1
            if "Aggregation" in fld:
                a = fld["Aggregation"]
                c = a.get("Expression", {}).get("Column", {})
                e = c.get("Expression", {}).get("SourceRef", {}).get("Entity")
                p = c.get("Property")
                if e and e not in table_cols:
                    bad(f"{vf.name} {role}[{i}] 聚合引用未知 Entity '{e}'")
                    n_dangling += 1
                elif e and p and p not in table_cols[e]:
                    bad(f"{vf.name} {role}[{i}] 聚合引用 {e}.{p} 不存在")
                    n_dangling += 1

if n_dangling == 0:
    ok("无悬空引用")

# ---- [11] partition CSV 真实存在 + 列数一致 ----
print("\n[11] partition M 表达式引用的 CSV 真实存在 + 列数一致")
n_csv_bad = 0
CSV_REF_PATTERN = re.compile(r'pCsvFolder\s*&\s*"([^"]+\.csv)"')
COLS_PARAM_PATTERN = re.compile(r"Columns=(\d+)")

for tf in sorted((SM_DIR / "definition" / "tables").glob("*.tmdl")):
    txt = tf.read_text(encoding="utf-8")
    mt = TABLE_NAME_PATTERN.match(txt)
    tname = mt.group(1) if mt else tf.stem
    cm = CSV_REF_PATTERN.search(txt)
    if not cm:
        continue
    rel = cm.group(1)
    csv_path = CSV_DIR / rel
    if not csv_path.exists():
        bad(f"{tname}: CSV 缺失 {csv_path}")
        n_csv_bad += 1
        continue
    import csv as _csv
    with open(csv_path, encoding="utf-8") as fp:
        reader = _csv.reader(fp)
        header = next(reader)
    cm2 = COLS_PARAM_PATTERN.search(txt)
    if cm2:
        n_decl = int(cm2.group(1))
        if n_decl != len(header):
            bad(f"{tname}: M 表达式 Columns={n_decl} 与 CSV 实际列数 {len(header)} 不一致")
            n_csv_bad += 1
        else:
            ok(f"{tname}: CSV={rel}  {len(header)} 列  匹配")
    tmdl_cols = set(COL_PATTERN.findall(txt))
    csv_cols = set(header)
    if tmdl_cols != csv_cols:
        only_tmdl = tmdl_cols - csv_cols
        only_csv = csv_cols - tmdl_cols
        if only_tmdl:
            bad(f"{tname}: TMDL 有但 CSV 没有的列: {only_tmdl}")
            n_csv_bad += 1
        if only_csv:
            bad(f"{tname}: CSV 有但 TMDL 没有的列: {only_csv}")
            n_csv_bad += 1

if n_csv_bad == 0:
    ok("CSV 一致性通过")

# ---- [12] 页面排版几何：越界 / 重叠 ----
print("\n[12] 页面排版几何（越界 / 重叠）")
n_geo = 0
page_files = glob.glob(os.path.join(REPORT_DIR, "definition", "pages", "*", "page.json"))
for pj_path in sorted(page_files):
    page = json.load(open(pj_path, encoding="utf-8"))
    pw = page.get("width")
    ph = page.get("height")
    pname = page.get("displayName", page.get("name"))
    if not pw or not ph:
        bad(f"{pname}: 缺少 width/height")
        n_geo += 1
        continue
    vroot = os.path.join(os.path.dirname(pj_path), "visuals")
    rects = []
    visual_files = glob.glob(os.path.join(vroot, "*", "visual.json"))
    for vj in sorted(visual_files):
        v = json.load(open(vj, encoding="utf-8"))
        pos = v.get("position") or {}
        try:
            rects.append((v.get("name"), float(pos["x"]), float(pos["y"]),
                          float(pos["width"]), float(pos["height"])))
        except (KeyError, TypeError, ValueError):
            bad(f"{pname}: {v.get('name')} position 不完整")
            n_geo += 1
    before = n_geo
    for n, x, y, w, h in rects:
        if x < 0 or y < 0 or x + w > pw + 0.5 or y + h > ph + 0.5:
            bad(f"{pname}: {n} 超出画布 ({x},{y},{w},{h}) vs {pw}x{ph}")
            n_geo += 1
    for i in range(len(rects)):
        for j in range(i + 1, len(rects)):
            n1, x1, y1, w1, h1 = rects[i]
            n2, x2, y2, w2, h2 = rects[j]
            ox = min(x1 + w1, x2 + w2) - max(x1, x2)
            oy = min(y1 + h1, y2 + h2) - max(y1, y2)
            if ox > 0.5 and oy > 0.5:
                bad(f"{pname}: {n1} 与 {n2} 重叠 {ox:.0f}x{oy:.0f}px")
                n_geo += 1
    if n_geo == before:
        area = 0
        for _, _, _, w, h in rects:
            area += w * h
        ok(f"{pname}: {len(rects)} 个视觉全在 {pw:.0f}x{ph:.0f} 内、无重叠"
           f"（占屏 {area / (pw * ph) * 100:.0f}%）")

# ---- 汇总 ----
print("\n" + "=" * 72)
if issues:
    print(f"FAIL  共 {len(issues)} 处问题")
    for m in issues[:10]:
        print(f"  - {m}")
    raise SystemExit(1)
else:
    print("PASS  静态校验全部通过")
print("=" * 72)
