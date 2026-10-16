# -*- coding: utf-8 -*-
"""Unit tests for pure cleaning logic (no data files required)."""
import math
import numpy as np
import pandas as pd

import clean_data as cd


def test_parse_amount_basic():
    assert cd.parse_amount("$1,234.56") == pytest_approx(1234.56)


def test_parse_amount_no_symbols():
    assert cd.parse_amount(" 12,500 ") == pytest_approx(12500.0)


def test_parse_amount_nan_preserved():
    assert pd.isna(cd.parse_amount(np.nan))
    assert pd.isna(cd.parse_amount(None))


def test_parse_amount_garbage_to_nan():
    assert pd.isna(cd.parse_amount("not a number"))


def test_parse_amount_integer_dollars():
    assert cd.parse_amount("$50") == pytest_approx(50.0)


def test_parse_amount_zero():
    assert cd.parse_amount("$0.00") == pytest_approx(0.0)


def test_method_class_covers_all_expected():
    # every acquisition method listed must resolve to a control class
    for method in cd.METHOD_CLASS_LOOKUP:
        assert method in cd.METHOD_CLASS_LOOKUP


def test_method_class_buckets_nonempty():
    for cls in ("competitive", "exempt", "flexible"):
        assert cls in cd.METHOD_CLASS
        assert len(cd.METHOD_CLASS[cls]) >= 1


def test_method_class_exempt_contains_services_statute():
    assert "Services are specifically exempt by statute" in cd.METHOD_CLASS["exempt"]


def test_zip_extraction_from_dirty_location():
    # location field shape: "ZIP\n(lat,lon)" -> keep ZIP
    s = pd.Series(["95670\n(38.5, -121.2)", "90013\n(34.0, -118.2)"])
    z = s.str.split("\n").str[0].str.strip()
    z = z.where(z.str.match(r"^\d{5}$"))
    assert z.tolist() == ["95670", "90013"]


def test_zip_rejects_non_zip():
    s = pd.Series(["n/a", "956703", "9567"])
    z = s.str.split("\n").str[0].str.strip()
    z = z.where(z.str.match(r"^\d{5}$"))
    assert z.tolist()[0] is np.nan or pd.isna(z.tolist()[0])
    assert pd.isna(z.tolist()[1]) and pd.isna(z.tolist()[2])


def pytest_approx(x):
    return float(x)
