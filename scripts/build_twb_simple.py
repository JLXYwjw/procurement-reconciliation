# -*- coding: utf-8 -*-
"""
Tableau 10.5 分析工作簿生成器 —— 基础可读版（build_twb_simple.py）
=================================================================

  生成一个 Tableau 10.5 格式的 .twb 工作簿文件，包含：
    3 个数据源（明细宽表 / Top500供应商 / Top20供应商）
    6 个工作表（月度趋势 / 部门Top15 / 采购控制 / Top20 / 分层 / 散点图）
    1 个仪表板（2行3列布局）

为什么照 10.5 原生样例写：之前用 2023.3 模板降级属于猜，
照原生样例写才能保证 XSD 校验通过。

运行方式：
    python scripts/build_twb_simple.py

English:
Tableau 10.5 analytics workbook generator (plain, readable version).

Builds a .twb workbook in Tableau 10.5 format containing:
  3 data sources (wide fact / Top-500 suppliers / Top-20 suppliers)
  6 worksheets (monthly trend / dept Top15 / control / Top20 / segmentation / scatter)
  1 dashboard (2-row x 3-column layout)

Why it follows the native 10.5 sample: an earlier 2023.3-template
downgrade was a guess; writing against the native sample guarantees that
XSD validation passes.

Run:
    python scripts/build_twb_simple.py
"""

import os

# ------------------------------------------------------------------
# 0. 路径配置
# ------------------------------------------------------------------
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_DIR = (ROOT + "/data/pbip").replace(os.sep, "/")
OUT = os.path.join(ROOT, "ProcurementReconciliation_Tableau105.twb")

# ------------------------------------------------------------------
# 1. 数据源字段定义
# ------------------------------------------------------------------
# (字段名, datatype, role, type, remote-type, 中文标题)
FACT_FIELDS = [
    ("creation_date",             "date",    "dimension", "ordinal",      133, "创建日期"),
    ("year_month",                "string",  "dimension", "nominal",      129, "年月"),
    ("fiscal_year",               "string",  "dimension", "nominal",      129, "财年"),
    ("po_number",                  "string",  "dimension", "nominal",      129, "订单号"),
    ("acquisition_method",         "string",  "dimension", "nominal",      129, "采购方法"),
    ("method_class",              "string",  "dimension", "nominal",      129, "控制类别"),
    ("method_class_cn",           "string",  "dimension", "nominal",      129, "控制类别(中)"),
    ("acquisition_type",           "string",  "dimension", "nominal",      129, "采购类型"),
    ("department",                "string",  "dimension", "nominal",      129, "部门"),
    ("dept_group",                "string",  "dimension", "nominal",      129, "部门分组"),
    ("supplier_name",             "string",  "dimension", "nominal",      129, "供应商"),
    ("quantity",                  "real",    "measure",   "quantitative",   5, "数量"),
    ("unit_price",                "real",    "measure",   "quantitative",   5, "单价"),
    ("total_price",               "real",    "measure",   "quantitative",   5, "支出金额"),
    ("spend_b",                   "real",    "measure",   "quantitative",   5, "支出(十亿)"),
    ("segment",                   "integer", "dimension", "nominal",       20, "商品段"),
    ("supplier_tier",             "string",  "dimension", "nominal",      129, "供应商分层"),
    ("tier_cn",                   "string",  "dimension", "nominal",      129, "供应商分层(中)"),
    ("supplier_total_spend",      "real",    "measure",   "quantitative",   5, "供应商总支出"),
    ("supplier_order_count",      "integer", "measure",   "quantitative",  20, "供应商订单数"),
    ("supplier_category_breadth", "integer", "measure",   "quantitative",  20, "品类广度"),
    ("supplier_years_active",     "integer", "measure",   "quantitative",  20, "活跃年数"),
]

SUP_FIELDS = [
    ("supplier_name",    "string",  "dimension", "nominal",      129, "供应商"),
    ("supplier_rank",    "integer", "dimension", "ordinal",       20, "支出排名"),
    ("total_spend_b",    "real",    "measure",   "quantitative",   5, "总支出(十亿)"),
    ("total_spend",      "real",    "measure",   "quantitative",   5, "总支出"),
    ("order_count",      "integer", "measure",   "quantitative",  20, "订单数"),
    ("avg_order",        "real",    "measure",   "quantitative",   5, "平均订单金额"),
    ("cum_share_pct",    "real",    "measure",   "quantitative",   5, "累计占比(%)"),
    ("category_breadth", "integer", "measure",   "quantitative",  20, "品类广度"),
    ("years_active",     "integer", "measure",   "quantitative",  20, "活跃年数"),
    ("tier_cn",          "string",  "dimension", "nominal",      129, "供应商分层"),
    ("tier_order",       "integer", "dimension", "ordinal",       20, "分层排序"),
]

TOP20_FIELDS = [
    ("supplier_name", "string",  "dimension", "nominal",      129, "供应商"),
    ("supplier_rank", "integer", "dimension", "ordinal",       20, "支出排名"),
    ("total_spend_b", "real",    "measure",   "quantitative",   5, "总支出(十亿)"),
    ("order_count",   "integer", "measure",   "quantitative",  20, "订单数"),
    ("tier_cn",       "string",  "dimension", "nominal",      129, "供应商分层"),
]

# 数据源标识
FACT_DS = "federated.0factdetail"
FACT_TS = "textscan.0factdetail"
FACT_CAP = "采购明细"

SUP_DS = "federated.0supplier"
SUP_TS = "textscan.0supplier"
SUP_CAP = "Top500供应商"

TOP20_DS = "federated.0top20"
TOP20_TS = "textscan.0top20"
TOP20_CAP = "Top20供应商"

FACT_CSV = "tableau_fact_wide.csv"
SUP_CSV = "tableau_supplier_top500.csv"
TOP20_CSV = "tableau_top20.csv"

CAP_BY_DS = {FACT_DS: FACT_CAP, SUP_DS: SUP_CAP, TOP20_DS: TOP20_CAP}

AGG_BY_REMOTE = {129: "Count", 20: "Sum", 5: "Sum", 133: "Year"}

# ------------------------------------------------------------------
# 2. 配色（小写十六进制，10.5 XSD 要求）
# ------------------------------------------------------------------
C_NAVY = "#1f3a5f"
C_BLUE = "#3e6e9e"
C_LBLUE = "#9db4cc"
C_RED = "#a8322a"
C_GRAY = "#8a94a6"
C_TEXT = "#1f2937"

# 维度值 → 颜色
COLOR_MAP_METHOD = [("竞争性", C_NAVY), ("豁免", C_RED), ("灵活", C_LBLUE)]
COLOR_MAP_TIER = [("一次性大额", C_RED), ("核心战略", C_NAVY),
                  ("常规", C_BLUE), ("长尾", C_LBLUE), ("未分层", C_GRAY)]

FONT = "Microsoft YaHei"


# ------------------------------------------------------------------
# 3. XML 转义
# ------------------------------------------------------------------
def esc(s):
    """XML 特殊字符转义。"""
    text = str(s)
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    text = text.replace("'", "&apos;")
    text = text.replace('"', "&quot;")
    return text


# ------------------------------------------------------------------
# 4. 数据源 XML 生成
# ------------------------------------------------------------------
def build_columns_block(fields):
    """生成 <columns> 块。"""
    rows = ["          <columns character-set='UTF-8' header='yes' locale='en_US' separator=','>"]
    for i, (name, dt, *_r) in enumerate(fields):
        rows.append(f"            <column datatype='{dt}' name='{esc(name)}' ordinal='{i}' />")
    rows.append("          </columns>")
    return "\n".join(rows)


def build_metadata_records(fields, csv_name):
    """生成 <metadata-records> 块。"""
    rows = ["        <metadata-records>"]
    rows += [
        "          <metadata-record class='capability'>",
        "            <remote-name />",
        "            <remote-type>0</remote-type>",
        f"            <parent-name>[{esc(csv_name)}]</parent-name>",
        "            <remote-alias />",
        "            <aggregation>Count</aggregation>",
        "            <contains-null>true</contains-null>",
        "            <attributes>",
        "              <attribute datatype='string' name='character-set'>&quot;UTF-8&quot;</attribute>",
        "              <attribute datatype='string' name='collation'>&quot;en_US&quot;</attribute>",
        "              <attribute datatype='string' name='field-delimiter'>&quot;,&quot;</attribute>",
        "              <attribute datatype='string' name='header-row'>&quot;true&quot;</attribute>",
        "              <attribute datatype='string' name='locale'>&quot;en_US&quot;</attribute>",
        "              <attribute datatype='string' name='single-char'>&quot;&quot;</attribute>",
        "            </attributes>",
        "          </metadata-record>",
    ]
    for i, (name, dt, role, typ, remote, cap) in enumerate(fields):
        extra = []
        if dt == "string":
            extra = ["            <scale>1</scale>",
                     "            <width>1073741823</width>"]
        rows += [
            "          <metadata-record class='column'>",
            f"            <remote-name>{esc(name)}</remote-name>",
            f"            <remote-type>{remote}</remote-type>",
            f"            <local-name>[{esc(name)}]</local-name>",
            f"            <parent-name>[{esc(csv_name)}]</parent-name>",
            f"            <remote-alias>{esc(name)}</remote-alias>",
            f"            <ordinal>{i}</ordinal>",
            f"            <local-type>{dt}</local-type>",
            f"            <aggregation>{AGG_BY_REMOTE[remote]}</aggregation>",
        ] + extra + ["            <contains-null>true</contains-null>"]
        if dt == "string":
            rows.append("            <collation flag='0' name='LEN_RGB' />")
        rows.append("          </metadata-record>")
    rows.append("        </metadata-records>")
    return "\n".join(rows)


def build_palette(field_inst, pairs):
    """生成颜色映射 palette 的 style 块。"""
    lines = ["        <style>",
             "          <style-rule element='mark'>",
             f"            <encoding attr='color' field='{field_inst}' type='palette'>"]
    for val, color in pairs:
        lines.append(f"              <map to='{color}'>")
        lines.append(f"                <bucket>&quot;{esc(val)}&quot;</bucket>")
        lines.append("              </map>")
    lines += ["            </encoding>",
              "          </style-rule>",
              "        </style>"]
    return "\n".join(lines)


def build_datasource(ds, ts, cap, csv_name, fields, palette_block=""):
    """生成一个完整的 <datasource> 块。"""
    out = [f"    <datasource caption='{esc(cap)}' inline='true' name='{ds}' version='10.5'>"]
    out += [
        "      <connection class='federated'>",
        "        <named-connections>",
        f"          <named-connection caption='{esc(csv_name)}' name='{ts}'>",
        f"            <connection class='textscan' directory='{esc(CSV_DIR)}' filename='{esc(csv_name)}' password='' server='' />",
        "          </named-connection>",
        "        </named-connections>",
        f"        <relation connection='{ts}' name='{esc(csv_name)}' table='[{esc(csv_name.replace('.csv', ''))}#csv]' type='table'>",
        build_columns_block(fields),
        "        </relation>",
        build_metadata_records(fields, csv_name),
        "      </connection>",
    ]
    # 元素顺序受 XSD 约束：aliases 必须在 style 之前，column 之后
    out.append("      <aliases enabled='yes' />")
    for name, dt, role, typ, remote, cap2 in fields:
        out.append(f"      <column caption='{esc(cap2)}' datatype='{dt}' name='[{esc(name)}]' "
                   f"role='{role}' type='{typ}' />")
    if palette_block:
        out.append(palette_block)
    out.append("    </datasource>")
    return "\n".join(out)


# ------------------------------------------------------------------
# 5. 工作表 XML 生成
# ------------------------------------------------------------------
def title_block(title, sub="", size=12):
    """生成结论式标题块。"""
    runs = [f"            <run bold='true' fontcolor='{C_NAVY}' fontname='{FONT}' fontsize='{size}'>{esc(title)}</run>"]
    if sub:
        runs.append(f"            <run fontcolor='{C_GRAY}' fontname='{FONT}' fontsize='9'>&#10;{esc(sub)}</run>")
    return ("      <layout-options>\n"
            "        <title>\n"
            "          <formatted-text>\n" + "\n".join(runs) + "\n"
            "          </formatted-text>\n"
            "        </title>\n"
            "      </layout-options>")


def worksheet(name, ds, deps, rows_expr, cols_expr, mark="Automatic",
              encodings=None, sort=None, filters=None, labels=False,
              num_format=None, title="", sub="", hide_grid=True,
              axis_titles=None):
    """生成一个完整的 <worksheet> 块。"""
    L = [f"    <worksheet name='{esc(name)}'>"]
    if title:
        L.append(title_block(title, sub))
    L += ["      <table>", "        <view>", "          <datasources>",
          f"            <datasource caption='{esc(CAP_BY_DS[ds])}' name='{ds}' />",
          "          </datasources>",
          f"          <datasource-dependencies datasource='{ds}'>"]
    for dt, cname, role, typ, inst, deriv, ityp in deps:
        L.append(f"            <column datatype='{dt}' name='[{esc(cname)}]' role='{role}' type='{typ}' />")
        L.append(f"            <column-instance column='[{esc(cname)}]' derivation='{deriv}' "
                 f"name='[{esc(inst)}]' pivot='key' type='{ityp}' />")
    L.append("          </datasource-dependencies>")

    if filters:
        for f in filters:
            L.append(f)

    if sort:
        col_expr, using_expr, direction = sort
        L.append(f"          <sort class='computed' column='{col_expr}' direction='{direction}' using='{using_expr}' />")

    if filters:
        L.append("          <slices>")
        for f in filters:
            import re as _re
            m = _re.search(r"column='([^']+)'", f)
            if m:
                L.append(f"            <column>{m.group(1)}</column>")
        L.append("          </slices>")

    L.append("          <aggregation value='true' />")
    L.append("        </view>")

    # table 级样式
    st = []
    if hide_grid:
        st += ["          <style-rule element='pane'>",
               "            <format attr='border-style' scope='rows' value='none' />",
               "            <format attr='border-style' scope='cols' value='none' />",
               "          </style-rule>",
               "          <style-rule element='header'>",
               "            <format attr='border-style' scope='rows' value='none' />",
               "            <format attr='border-style' scope='cols' value='none' />",
               "          </style-rule>",
               "          <style-rule element='table-div'>",
               "            <format attr='line-pattern' scope='rows' value='none' />",
               "            <format attr='line-pattern' scope='cols' value='none' />",
               "          </style-rule>",
               "          <style-rule element='header-div'>",
               "            <format attr='line-pattern' scope='rows' value='none' />",
               "            <format attr='line-pattern' scope='cols' value='none' />",
               "          </style-rule>"]
    if num_format:
        field_expr, fmt = num_format
        st += ["          <style-rule element='cell'>",
               f"            <format attr='text-format' field='{field_expr}' value='{fmt}' />",
               "          </style-rule>"]
    st += ["          <style-rule element='worksheet'>",
           "            <format attr='display-field-labels' scope='rows' value='false' />",
           "            <format attr='display-field-labels' scope='cols' value='false' />",
           f"            <format attr='color' value='{C_TEXT}' />",
           "          </style-rule>",
           "          <style-rule element='field-labels'>",
           f"            <format attr='font-family' value='{FONT}' />",
           "          </style-rule>"]
    if axis_titles:
        ax = ["          <style-rule element='axis'>"]
        for scope, t in axis_titles.items():
            ax.append(f"            <format attr='title' class='0' scope='{scope}' value='{esc(t)}' />")
        ax.append("          </style-rule>")
        st += ax
    L.append("        <style>")
    L += st
    L.append("        </style>")

    # panes
    L += ["        <panes>",
          "          <pane selection-relaxation-option='selection-relaxation-allow'>",
          "            <view>", "              <breakdown value='auto' />", "            </view>",
          f"            <mark class='{mark}' />"]
    if encodings:
        L.append("            <encodings>")
        for kind, expr in encodings:
            L.append(f"              <{kind} column='{expr}' />")
        L.append("            </encodings>")
    if labels:
        L += ["            <style>",
              "              <style-rule element='datalabel'>",
              "                <format attr='font-size' value='10' />",
              f"                <format attr='color' value='{C_TEXT}' />",
              "              </style-rule>",
              "              <style-rule element='mark'>",
              "                <format attr='mark-labels-show' value='true' />",
              "                <format attr='mark-labels-cull' value='true' />",
              "              </style-rule>",
              "            </style>"]
    L += ["          </pane>", "        </panes>"]

    if rows_expr:
        L.append(f"        <rows>{rows_expr}</rows>")
    if cols_expr:
        L.append(f"        <cols>{cols_expr}</cols>")
    L += ["      </table>", "    </worksheet>"]
    return "\n".join(L)


# ------------------------------------------------------------------
# 6. 主流程
# ------------------------------------------------------------------
def main():
    # ---- 6.1 工作簿头 ----
    head = """<?xml version='1.0' encoding='utf-8' ?>

<!-- 由 build_twb_simple.py 生成 / Tableau 10.5 格式 -->
<workbook original-version='10.5' source-build='10.5.0 (10500.17.1226.1925)' source-platform='win' version='10.5' xmlns:user='http://www.tableausoftware.com/xml/user'>
  <preferences>
    <preference name='ui.encoding.shelf.height' value='24' />
    <preference name='ui.shelf.height' value='26' />
  </preferences>
  <style-theme name='smooth' />
  <datasources>"""

    # ---- 6.2 三个数据源 ----
    ds_a = build_datasource(FACT_DS, FACT_TS, FACT_CAP, FACT_CSV, FACT_FIELDS,
                            palette_block=build_palette("[none:method_class_cn:nk]", COLOR_MAP_METHOD))
    ds_b = build_datasource(SUP_DS, SUP_TS, SUP_CAP, SUP_CSV, SUP_FIELDS,
                            palette_block=build_palette("[none:tier_cn:nk]", COLOR_MAP_TIER))
    ds_c = build_datasource(TOP20_DS, TOP20_TS, TOP20_CAP, TOP20_CSV, TOP20_FIELDS)

    F = FACT_DS
    S = SUP_DS
    T = TOP20_DS

    # ---- 6.3 六个工作表 ----
    # 图1：月度支出趋势
    w1 = worksheet(
        "1 月度支出趋势", F,
        deps=[("string", "year_month", "dimension", "nominal",
               "none:year_month:nk", "None", "nominal"),
              ("real", "spend_b", "measure", "quantitative",
               "sum:spend_b:qk", "Sum", "quantitative")],
        rows_expr=f"[{F}].[sum:spend_b:qk]",
        cols_expr=f"[{F}].[none:year_month:nk]",
        mark="Line",
        axis_titles={"rows": "十亿美元"},
        num_format=(f"[{F}].[sum:spend_b:qk]", "*0.0"),
        title="3–6 月是淡季的 6.3 倍",
    )

    # 图2：部门支出 Top15
    w2 = worksheet(
        "2 部门支出Top15", F,
        deps=[("string", "dept_group", "dimension", "nominal",
               "none:dept_group:nk", "None", "nominal"),
              ("real", "spend_b", "measure", "quantitative",
               "sum:spend_b:qk", "Sum", "quantitative")],
        rows_expr=f"[{F}].[none:dept_group:nk]",
        cols_expr=f"[{F}].[sum:spend_b:qk]",
        mark="Bar",
        encodings=[("text", f"[{F}].[sum:spend_b:qk]")],
        sort=(f"[{F}].[none:dept_group:nk]", f"[{F}].[sum:spend_b:qk]", "DESC"),
        labels=True,
        num_format=(f"[{F}].[sum:spend_b:qk]", "*0.0"),
        title="医疗一个部门占 66.0%",
    )

    # 图3：采购控制结构
    w3 = worksheet(
        "3 采购控制结构", F,
        deps=[("string", "method_class_cn", "dimension", "nominal",
               "none:method_class_cn:nk", "None", "nominal"),
              ("real", "spend_b", "measure", "quantitative",
               "sum:spend_b:qk", "Sum", "quantitative")],
        rows_expr=f"[{F}].[sum:spend_b:qk]",
        cols_expr=f"[{F}].[none:method_class_cn:nk]",
        mark="Bar",
        encodings=[("color", f"[{F}].[none:method_class_cn:nk]"),
                   ("text", f"[{F}].[sum:spend_b:qk]")],
        sort=(f"[{F}].[none:method_class_cn:nk]", f"[{F}].[sum:spend_b:qk]", "DESC"),
        labels=True,
        num_format=(f"[{F}].[sum:spend_b:qk]", "*0.0"),
        title="豁免采购仍占 40.1%",
    )

    # 图4：Top20 供应商
    w4 = worksheet(
        "4 Top20供应商", T,
        deps=[("string", "supplier_name", "dimension", "nominal",
               "none:supplier_name:nk", "None", "nominal"),
              ("real", "total_spend_b", "measure", "quantitative",
               "sum:total_spend_b:qk", "Sum", "quantitative")],
        rows_expr=f"[{T}].[none:supplier_name:nk]",
        cols_expr=f"[{T}].[sum:total_spend_b:qk]",
        mark="Bar",
        encodings=[("text", f"[{T}].[sum:total_spend_b:qk]")],
        sort=(f"[{T}].[none:supplier_name:nk]", f"[{T}].[sum:total_spend_b:qk]", "DESC"),
        labels=True,
        num_format=(f"[{T}].[sum:total_spend_b:qk]", "*0.00"),
        title="Top20 拿走 58.0%",
    )

    # 图5：供应商分层
    w5 = worksheet(
        "5 供应商分层", F,
        deps=[("string", "tier_cn", "dimension", "nominal",
               "none:tier_cn:nk", "None", "nominal"),
              ("real", "spend_b", "measure", "quantitative",
               "sum:spend_b:qk", "Sum", "quantitative")],
        rows_expr=f"[{F}].[sum:spend_b:qk]",
        cols_expr=f"[{F}].[none:tier_cn:nk]",
        mark="Bar",
        encodings=[("color", f"[{F}].[none:tier_cn:nk]"),
                   ("text", f"[{F}].[sum:spend_b:qk]")],
        sort=(f"[{F}].[none:tier_cn:nk]", f"[{F}].[sum:spend_b:qk]", "DESC"),
        labels=True,
        num_format=(f"[{F}].[sum:spend_b:qk]", "*0.0"),
        title="一次性大额占 68.4%",
    )

    # 图6：供应商散点
    w6 = worksheet(
        "6 供应商散点", S,
        deps=[("integer", "order_count", "measure", "quantitative",
               "sum:order_count:qk", "Sum", "quantitative"),
              ("real", "total_spend_b", "measure", "quantitative",
               "sum:total_spend_b:qk", "Sum", "quantitative"),
              ("string", "supplier_name", "dimension", "nominal",
               "none:supplier_name:nk", "None", "nominal"),
              ("string", "tier_cn", "dimension", "nominal",
               "none:tier_cn:nk", "None", "nominal")],
        rows_expr=f"[{S}].[sum:total_spend_b:qk]",
        cols_expr=f"[{S}].[sum:order_count:qk]",
        mark="Circle",
        encodings=[("color", f"[{S}].[none:tier_cn:nk]"),
                   ("lod", f"[{S}].[none:supplier_name:nk]")],
        axis_titles={"cols": "订单数", "rows": "十亿美元"},
        num_format=(f"[{S}].[sum:total_spend_b:qk]", "*0.00"),
        title="500 家覆盖 92.7%",
    )

    sheets = [(w1, "1 月度支出趋势"), (w2, "2 部门支出Top15"),
              (w3, "3 采购控制结构"), (w4, "4 Top20供应商"),
              (w5, "5 供应商分层"), (w6, "6 供应商散点")]

    # ---- 6.4 仪表板 ----
    DASH = "采购支出分析总览"
    CW = 33333
    zones = [
        f"        <zone h='8000' id='2' type='title' w='100000' x='0' y='0' />",
        f"        <zone h='46000' id='3' name='1 月度支出趋势' show-title='true' w='{CW}' x='0' y='8000' />",
        f"        <zone h='46000' id='4' name='2 部门支出Top15' show-title='true' w='{CW}' x='{CW}' y='8000' />",
        f"        <zone h='46000' id='5' name='4 Top20供应商' show-title='true' w='{100000 - 2 * CW}' x='{2 * CW}' y='8000' />",
        f"        <zone h='46000' id='6' name='3 采购控制结构' show-title='true' w='{CW}' x='0' y='54000' />",
        f"        <zone h='46000' id='7' name='5 供应商分层' show-title='true' w='{CW}' x='{CW}' y='54000' />",
        f"        <zone h='46000' id='8' name='6 供应商散点' show-title='true' w='{100000 - 2 * CW}' x='{2 * CW}' y='54000' />",
    ]
    zone_text = "\n".join(zones)
    dashboard = f"""  <dashboards>
    <dashboard name='{DASH}'>
      <layout-options>
        <title>
          <formatted-text>
            <run bold='true' fontcolor='{C_NAVY}' fontname='{FONT}' fontsize='16'>采购支出分析 2012–2015</run>
          </formatted-text>
        </title>
      </layout-options>
      <style />
      <size maxheight='900' maxwidth='1200' minheight='900' minwidth='1200' />
      <zones>
        <zone h='100000' id='1' type='layout-basic' w='100000' x='0' y='0'>
{zone_text}
        </zone>
      </zones>
    </dashboard>
  </dashboards>
"""

    # ---- 6.5 窗口定义 ----
    dash_window = f"""    <window class='dashboard' maximized='true' name='{DASH}'>
      <viewpoints>"""
    for _, n in sheets:
        dash_window += f"\n        <viewpoint name='{esc(n)}' />"
    dash_window += """
      </viewpoints>
      <active id='-1' />
    </window>"""

    wins = [dash_window]
    for _, wn in sheets:
        wins.append(f"""    <window class='worksheet' name='{esc(wn)}'>
      <cards>
        <edge name='left'>
          <strip size='160'>
            <card type='pages' />
            <card type='filters' />
            <card type='marks' />
          </strip>
        </edge>
        <edge name='top'>
          <strip size='2147483647'>
            <card type='columns' />
          </strip>
          <strip size='2147483647'>
            <card type='rows' />
          </strip>
        </edge>
      </cards>
    </window>""")

    # ---- 6.6 组装完整 XML ----
    sheets_text = "\n".join(w for w, _ in sheets)
    wins_text = "\n".join(wins)
    xml = (head + "\n" + ds_a + "\n" + ds_b + "\n" + ds_c + "\n  </datasources>\n"
           "  <worksheets>\n" + sheets_text + "\n  </worksheets>\n"
           + dashboard +
           "  <windows source-height='30'>\n" + wins_text + "\n  </windows>\n"
           "</workbook>\n")

    # ---- 6.7 写文件 ----
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(xml)
    print(f"生成: {OUT}  ({os.path.getsize(OUT):,} bytes)")

    # XML 语法检查
    import xml.etree.ElementTree as ET
    ET.parse(OUT)
    print("XML 语法检查: OK")


if __name__ == "__main__":
    main()
