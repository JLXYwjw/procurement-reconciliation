# -*- coding: utf-8 -*-
r"""
生成 Tableau 10.5「分析级」工作簿。

★ 权威参考：D:/software/Tableau/Performance/PerformanceRecording_new.twb
  （Tableau 10.5 原生自带，version='10.5'，2017-12 生成）
  之前用 2023.3 的模板降级推测，属于猜；现在改成照 10.5 原生样例写。

★ 为什么之前「太丑」：
  ① 没加 <style-theme name='smooth' />，走的是 classic 主题 = 灰底 + 灰框 + 显示字段标签
  ② 条形图没排序（<sort class='computed' direction='DESC' using=...>）
  ③ 部门 111 个全画出来 → 挤成一堆线；应 Top15 + 其余合并
  ④ 日期用原始 date 类型 → 1015 个点连成一片；应预聚合成 year_month（36 个点）
  ⑤ 没有数值标签、没有结论式标题、没有自定义配色

★ 为什么分两个数据源：
  帕累托 / Top20 供应商 / 分层占比 都是【供应商粒度】指标。
  在 34.6 万行明细上 SUM(supplier_total_spend) 会按订单行数重复计算 N 次。
  供应商汇总表一供应商一行，从根上避免重复计数。

输出：ProcurementReconciliation_Tableau105.twb
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_DIR = (ROOT + "/data/pbip").replace(os.sep, "/")
OUT = os.path.join(ROOT, "ProcurementReconciliation_Tableau105.twb")

# ============ 数据源定义 ============
# (字段名, datatype, role, type, remote-type, 中文标题)
FACT_FIELDS = [
    ("creation_date",             "date",    "dimension", "ordinal",      133, "创建日期"),
    ("year_month",                "string",  "dimension", "nominal",      129, "年月"),
    ("fiscal_year",               "string",  "dimension", "nominal",      129, "财年"),
    ("po_number",                 "string",  "dimension", "nominal",      129, "订单号"),
    ("acquisition_method",        "string",  "dimension", "nominal",      129, "采购方法"),
    ("method_class",              "string",  "dimension", "nominal",      129, "控制类别"),
    ("method_class_cn",           "string",  "dimension", "nominal",      129, "控制类别(中)"),
    ("acquisition_type",          "string",  "dimension", "nominal",      129, "采购类型"),
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

# Top20 单独成表：避免用 quantitative filter（10.5 的 filter-group 写法没十足把握，
# 一旦偏差图会静默空白）。20 行的表 = 零筛选风险。
TOP20_FIELDS = [
    ("supplier_name", "string",  "dimension", "nominal",      129, "供应商"),
    ("supplier_rank", "integer", "dimension", "ordinal",       20, "支出排名"),
    ("total_spend_b", "real",    "measure",   "quantitative",   5, "总支出(十亿)"),
    ("order_count",   "integer", "measure",   "quantitative",  20, "订单数"),
    ("tier_cn",       "string",  "dimension", "nominal",      129, "供应商分层"),
]

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

# ============ 配色（专业商务风）============
# ★ 颜色必须小写十六进制。10.5 XSD 的 facet 正则就是 `#[0-9a-f]{6}`
#   （实测报错：value '#1F4E79' does not match regular expression facet）
C_NAVY = "#1f4e79"   # 主色 深蓝
C_BLUE = "#4a90c2"   # 次蓝
C_LBLUE = "#a8c6e5"  # 浅蓝
C_GREEN = "#2e7d32"  # 竞争性
C_RED = "#c62828"    # 豁免 / 一次性大额（警示）
C_AMBER = "#f9a825"  # 灵活
C_GRAY = "#7f7f7f"
C_TEXT = "#333333"

# 维度值 -> 颜色
COLOR_MAP_METHOD = [("竞争性", C_GREEN), ("豁免", C_RED), ("灵活", C_AMBER)]
COLOR_MAP_TIER = [("核心战略", C_NAVY), ("常规", C_BLUE), ("长尾", C_LBLUE),
                  ("一次性大额", C_RED), ("未分层", C_GRAY)]

FONT = "Microsoft YaHei"


def esc(s) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace("'", "&apos;").replace('"', "&quot;"))


# ---------------------------------------------------------------- 数据源
def build_columns_block(fields) -> str:
    rows = ["          <columns character-set='UTF-8' header='yes' locale='en_US' separator=','>"]
    for i, (name, dt, *_r) in enumerate(fields):
        rows.append(f"            <column datatype='{dt}' name='{esc(name)}' ordinal='{i}' />")
    rows.append("          </columns>")
    return "\n".join(rows)


def build_metadata_records(fields, csv_name) -> str:
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
            # 10.5 对 string 的 metadata 要求更细，缺 scale/width 会校验失败
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


def build_palette(field_inst: str, pairs) -> str:
    """<encoding attr='color' field='[..]' type='palette'> + map/bucket"""
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


def build_datasource(ds, ts, cap, csv_name, fields, palette_block="") -> str:
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
    # ★ 元素顺序受 XSD 内容模型严格约束（实测报错 element 'aliases' is not allowed）：
    #   connection → utility-dimensions? → dimension* → overridable-settings?
    #   → aliases? → column, column-instance … → extract? → layout? → style
    #   即 aliases 必须在 <style> 之前，column 之后。
    out.append("      <aliases enabled='yes' />")
    for name, dt, role, typ, remote, cap2 in fields:
        out.append(f"      <column caption='{esc(cap2)}' datatype='{dt}' name='[{esc(name)}]' "
                   f"role='{role}' type='{typ}' />")
    # style（配色 palette）必须放在所有 column 之后
    if palette_block:
        out.append(palette_block)
    out.append("    </datasource>")
    return "\n".join(out)


# ---------------------------------------------------------------- 工作表
def title_block(title: str, sub: str = "", size: int = 15) -> str:
    """结论式标题：Tableau 的默认标题只有字段名，这里直接写业务结论"""
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
              axis_titles=None) -> str:
    """deps: [(datatype, column, role, type, inst_name, derivation, inst_type)]
    encodings: [(kind, expr)]
    sort: (column_expr, using_expr, direction)
    filters: 原始 XML 片段列表
    axis_titles: {'rows': '..', 'cols': '..'}
    """
    L = [f"    <worksheet name='{esc(name)}'>"]
    if title:
        L.append(title_block(title, sub))
    L += ["      <table>", "        <view>", "          <datasources>",
          f"            <datasource caption='{esc(CAP_BY_DS[ds])}' name='{ds}' />",
          "          </datasources>",
          f"          <datasource-dependencies datasource='{ds}'>"]
    for dt, cname, role, typ, inst, deriv, ityp in deps:
        L.append(f"            <column datatype='{dt}' name='[{esc(cname)}]' role='{role}' type='{typ}' />")
        # pivot='key' 是 10.5 XSD 的必需属性（缺了报 missing required attribute）
        L.append(f"            <column-instance column='[{esc(cname)}]' derivation='{deriv}' "
                 f"name='[{esc(inst)}]' pivot='key' type='{ityp}' />")
    L.append("          </datasource-dependencies>")

    if filters:
        for f in filters:
            L.append(f)

    # ★ sort 必须在 filters/slices 之后、aggregation 之前（照 10.5 样例顺序）
    if sort:
        col_expr, using_expr, direction = sort
        L.append(f"          <sort class='computed' column='{col_expr}' direction='{direction}' using='{using_expr}' />")

    if filters:
        L.append("          <slices>")
        for f in filters:
            # 从 filter 的 column 属性里取出列表达式
            import re as _re
            m = _re.search(r"column='([^']+)'", f)
            if m:
                L.append(f"            <column>{m.group(1)}</column>")
        L.append("          </slices>")

    L.append("          <aggregation value='true' />")
    L.append("        </view>")

    # ---- table 级 style：去边框、隐藏字段标签、数字格式 ----
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

    # ---- panes ----
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
              "                <format attr='font-size' value='9' />",
              "                <format attr='color' value='#000000' />",
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


def main() -> None:
    # ============ 工作簿头 ============
    head = f"""<?xml version='1.0' encoding='utf-8' ?>

<!-- 由 build_twb.py 生成 / Tableau 10.5 格式（参照 Tableau 自带 10.5 样例） -->
<workbook original-version='10.5' source-build='10.5.0 (10500.17.1226.1925)' source-platform='win' version='10.5' xmlns:user='http://www.tableausoftware.com/xml/user'>
  <preferences>
    <preference name='ui.encoding.shelf.height' value='24' />
    <preference name='ui.shelf.height' value='26' />
  </preferences>
  <!-- ★ 关键：smooth 主题。不加就走 classic = 灰底灰框，这是「丑」的头号原因 -->
  <style-theme name='smooth' />
  <datasources>"""

    ds_a = build_datasource(FACT_DS, FACT_TS, FACT_CAP, FACT_CSV, FACT_FIELDS,
                            palette_block=build_palette(f"[none:method_class_cn:nk]", COLOR_MAP_METHOD))
    ds_b = build_datasource(SUP_DS, SUP_TS, SUP_CAP, SUP_CSV, SUP_FIELDS,
                            palette_block=build_palette(f"[none:tier_cn:nk]", COLOR_MAP_TIER))
    ds_c = build_datasource(TOP20_DS, TOP20_TS, TOP20_CAP, TOP20_CSV, TOP20_FIELDS)

    F = FACT_DS
    S = SUP_DS

    # ---------------- 图 1：月度支出趋势 ----------------
    w1 = worksheet(
        "1 月度支出趋势", F,
        deps=[("string", "year_month", "dimension", "nominal",
               "none:year_month:nk", "None", "nominal"),
              ("real", "spend_b", "measure", "quantitative",
               "sum:spend_b:qk", "Sum", "quantitative")],
        rows_expr=f"[{F}].[sum:spend_b:qk]",
        cols_expr=f"[{F}].[none:year_month:nk]",
        mark="Line",
        axis_titles={"rows": "支出（十亿美元）"},
        num_format=(f"[{F}].[sum:spend_b:qk]", "*0.0"),
        title="3–6 月支出是淡季的 6.3 倍，预算释放节奏明显",
        sub="36 个月 · 峰值 2013-03 达 $23.3B · 单位：十亿美元",
    )

    # ---------------- 图 2：部门支出 Top15 ----------------
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
        title="Top15 部门吃掉 92.5% 的支出，医疗一个部门占 66.0%",
        sub="Health Care Services $99.8B · 其余 96 个部门合计仅 7.5%",
    )

    # ---------------- 图 3：采购控制结构 ----------------
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
        title="竞争性采购占 55.7%，但豁免采购仍有 $60.6B（40.1%）",
        sub="豁免=可不经竞争程序直接采购，占比过高是审计高风险信号",
    )

    # ---------------- 图 4：Top20 供应商 ----------------
    # 数据源是 20 行的独立表，不需要任何筛选器
    T = TOP20_DS
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
        title="Top20 供应商拿走 58.0% 的支出，单家最高 $13.6B",
        sub="24,465 家供应商中，前 0.08% 占掉近六成金额",
    )

    # ---------------- 图 5：供应商分层支出 ----------------
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
        title="「一次性大额」合同贡献 68.4% 支出，却只有 4,545 家供应商",
        sub="核心战略 30.6% · 常规 0.9% · 长尾 0.1% —— 支出高度依赖非长期关系",
    )

    # ---------------- 图 6：供应商散点（异常识别）----------------
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
        axis_titles={"cols": "订单数", "rows": "总支出（十亿美元）"},
        num_format=(f"[{S}].[sum:total_spend_b:qk]", "*0.00"),
        title="500 家供应商覆盖 92.7% 支出，其中 5 家只下过 1 单",
        sub="这 5 家单笔合计 $13.0B · 每点一家供应商 · X=订单数 Y=总支出",
    )

    sheets = [(w1, "1 月度支出趋势"), (w2, "2 部门支出Top15"),
              (w3, "3 采购控制结构"), (w4, "4 Top20供应商"),
              (w5, "5 供应商分层"), (w6, "6 供应商散点")]

    # ---------------- 仪表板（2 行 × 3 列 + 标题条）----------------
    # 坐标体系：0–100000 相对值（照 Tableau 10.5 自带样例）
    DASH = "采购支出分析总览"
    CW = 33333  # 每列宽
    zones = [
        f"        <zone h='8000' id='2' type='title' w='100000' x='0' y='0' />",
        # 第一行
        f"        <zone h='46000' id='3' name='1 月度支出趋势' show-title='true' w='{CW}' x='0' y='8000' />",
        f"        <zone h='46000' id='4' name='2 部门支出Top15' show-title='true' w='{CW}' x='{CW}' y='8000' />",
        f"        <zone h='46000' id='5' name='4 Top20供应商' show-title='true' w='{100000 - 2 * CW}' x='{2 * CW}' y='8000' />",
        # 第二行
        f"        <zone h='46000' id='6' name='3 采购控制结构' show-title='true' w='{CW}' x='0' y='54000' />",
        f"        <zone h='46000' id='7' name='5 供应商分层' show-title='true' w='{CW}' x='{CW}' y='54000' />",
        f"        <zone h='46000' id='8' name='6 供应商散点' show-title='true' w='{100000 - 2 * CW}' x='{2 * CW}' y='54000' />",
    ]
    dashboard = f"""  <dashboards>
    <dashboard name='{DASH}'>
      <layout-options>
        <title>
          <formatted-text>
            <run bold='true' fontcolor='{C_NAVY}' fontname='{FONT}' fontsize='18'>加州州级采购支出分析 · 2012–2015</run>
            <run fontcolor='{C_GRAY}' fontname='{FONT}' fontsize='10'>&#9;346,018 笔订单 / $151.2B / 24,465 家供应商</run>
          </formatted-text>
        </title>
      </layout-options>
      <style />
      <size maxheight='900' maxwidth='1200' minheight='900' minwidth='1200' />
      <zones>
        <zone h='100000' id='1' type='layout-basic' w='100000' x='0' y='0'>
{chr(10).join(zones)}
        </zone>
      </zones>
    </dashboard>
  </dashboards>
"""
    dash_window = f"""    <window class='dashboard' maximized='true' name='{DASH}'>
      <viewpoints>
{chr(10).join(f"        <viewpoint name='{esc(n)}' />" for _, n in sheets)}
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

    xml = (head + "\n" + ds_a + "\n" + ds_b + "\n" + ds_c + "\n  </datasources>\n"
           "  <worksheets>\n" + "\n".join(w for w, _ in sheets) + "\n  </worksheets>\n"
           + dashboard +
           "  <windows source-height='30'>\n" + "\n".join(wins) + "\n  </windows>\n"
           "</workbook>\n")

    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(xml)
    print(f"生成: {OUT}  ({os.path.getsize(OUT):,} bytes)")

    import xml.etree.ElementTree as ET
    ET.parse(OUT)
    print("XML 语法检查: OK")


if __name__ == "__main__":
    main()
