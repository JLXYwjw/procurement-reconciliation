# -*- coding: utf-8 -*-
"""Guard against hand-typed numbers drifting from the data: recompute headline
figures from the parquet outputs and require the HTML report to contain them.

Skips on a clean clone (outputs are git-excluded), like the other output tests.
"""
import os

import pandas as pd
import pytest

from conftest import PROC_CLEAN, ROOT, SUPPLIER_SEG

pytestmark = pytest.mark.skipif(
    not (os.path.isfile(PROC_CLEAN) and os.path.isfile(SUPPLIER_SEG)),
    reason="analysis outputs not present in this checkout",
)


def _html():
    with open(os.path.join(ROOT, "index.html"), encoding="utf-8") as f:
        return f.read()


def test_headline_concentration_matches_data():
    df = pd.read_parquet(PROC_CLEAN)
    g = df.groupby("supplier_name")["total_price"].sum().sort_values(ascending=False)
    grand = float(df["total_price"].sum())
    cr4 = g.head(4).sum() / grand
    cr8 = g.head(8).sum() / grand
    top10 = g.head(10).sum() / grand
    html = _html()
    assert f"{cr4*100:.1f}%" in html  # 26.5%
    assert f"{cr8*100:.1f}%" in html  # 37.4%
    assert f"{top10*100:.1f}%" in html  # 41.4%


def test_tier_shares_match_data():
    sup = pd.read_parquet(SUPPLIER_SEG)
    ts = sup.groupby("tier")["total_spend"].sum()
    once_share = ts.get("oneoff_large", 0) / ts.sum()
    core_share = ts.get("core_strategic", 0) / ts.sum()
    html = _html()
    assert f"{once_share*100:.1f}%" in html  # 68.8%
    assert f"{core_share*100:.1f}%" in html  # 30.1%
    core_n = int(sup[sup["tier"] == "core_strategic"].shape[0])
    assert f"{core_n:,}" in html  # "1,921"


def test_exempt_share_matches_data():
    df = pd.read_parquet(PROC_CLEAN)
    ex = df[df["method_class"] == "exempt"]["total_price"].sum() / df["total_price"].sum()
    html = _html()
    assert f"{ex*100:.1f}%" in html  # 40.1%
