# -*- coding: utf-8 -*-
"""Contract checks on the analysis outputs (run only when outputs exist locally,
since the parquet files are intentionally excluded from git)."""
import os

import numpy as np
import pandas as pd
import pytest

from conftest import PROC_CLEAN, SUPPLIER_SEG

pytestmark = pytest.mark.skipif(
    not (os.path.isfile(PROC_CLEAN) and os.path.isfile(SUPPLIER_SEG)),
    reason="analysis outputs not present in this checkout",
)


def test_clean_has_expected_columns():
    df = pd.read_parquet(PROC_CLEAN)
    for col in ("total_price", "quantity", "zip_code", "segment",
                "method_class", "department", "fiscal_year"):
        assert col in df.columns


def test_clean_total_spend_matches():
    df = pd.read_parquet(PROC_CLEAN)
    total = float(df["total_price"].sum())
    assert total == pytest.approx(151_243_580_498.2, rel=1e-6)


def test_top10_share_around_41_percent():
    df = pd.read_parquet(PROC_CLEAN)
    g = df.groupby("supplier_name")["total_price"].sum().sort_values(ascending=False)
    share = g.head(10).sum() / g.sum()
    assert 0.38 < share < 0.44


def test_health_care_department_dominates():
    df = pd.read_parquet(PROC_CLEAN)
    dep = df.groupby("department")["total_price"].sum()
    hc = dep.get("Health Care Services, Department of", 0) / dep.sum()
    assert 0.62 < hc < 0.70


def test_supplier_segmentation_strategic_split():
    sup = pd.read_parquet(SUPPLIER_SEG)
    assert set(sup["tier"]) == {"core_strategic", "oneoff_large", "regular", "tail"}
    core = sup[sup["tier"] == "core_strategic"]
    once = sup[sup["tier"] == "oneoff_large"]
    # one-off/large dominates spend (~68.8%) - the key strategic insight
    assert once["total_spend"].sum() / sup["total_spend"].sum() == pytest.approx(0.688, rel=0.05)
    # the two high-spend tiers are genuinely different: recurring vs single-year
    assert core["years_active"].median() >= 2
    assert once["years_active"].median() < 2
    assert len(core) >= 1000


def test_method_class_no_null():
    df = pd.read_parquet(PROC_CLEAN)
    assert df["method_class"].notna().mean() > 0.99
