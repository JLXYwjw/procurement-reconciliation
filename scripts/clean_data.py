# -*- coding: utf-8 -*-
"""Clean the CA procurement purchase-order extract and persist a tidy table.

The raw file has ~909k physical lines but ~346k logical records (some text
fields span multiple lines). We normalize money, dates and identifiers, derive
feature columns (zip, UNSPSC segment, acquisition-method control class), then
save a clean parquet for downstream analysis.
"""
import argparse
import os

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "output")
DATA_NAME = "PURCHASE ORDER DATA EXTRACT 2012-2015_0.csv"
# default search path relative to the repo, so no machine-specific absolute path
DEFAULT_DATA = os.path.join(ROOT, "..", "datasets", "procurement", DATA_NAME)
os.makedirs(OUT_DIR, exist_ok=True)

# Acquisition-method control classification (initial business rule).
#   competitive: went through competition / governed frameworks
#   exempt:      legally exempt from competitive bidding (services) -> legitimate
#   flexible:    "off-standard" methods that deserve review (not necessarily bad)
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
METHOD_CLASS_LOOKUP = {
    m: cls for cls, methods in METHOD_CLASS.items() for m in methods
}


def parse_amount(x):
    """Parse a '$1,234.56'-style cell into a float; NaN stays NaN."""
    if pd.isna(x):
        return np.nan
    s = str(x).replace("$", "").replace(",", "").replace(" ", "").strip()
    try:
        return float(s)
    except Exception:
        return np.nan


def _plausible_year(d, lo=2000, hi=2026):
    """A date is plausible only if it falls in a sane year range; NaN is kept
    as NaN (it is a legitimately-missing value, not a dirty one)."""
    if pd.isna(d):
        return True
    return lo <= d.year <= hi


def main():
    parser = argparse.ArgumentParser(description="Clean the CA procurement extract.")
    parser.add_argument("--src", default=None,
                        help=f"Path to the raw CSV (default: {DEFAULT_DATA})")
    args = parser.parse_args()
    src = args.src or DEFAULT_DATA
    if not os.path.isfile(src):
        raise SystemExit(
            f"Raw CSV not found at {src}. Pass the correct path with --src "
            "(e.g. --src datasets/procurement/{DATA_NAME})."
        )

    df = pd.read_csv(src, encoding="utf-8")
    df["unit_price"] = df["Unit Price"].apply(parse_amount)
    df["total_price"] = df["Total Price"].apply(parse_amount)
    df["quantity"] = pd.to_numeric(df["Quantity"], errors="coerce")
    df["creation_date"] = pd.to_datetime(
        df["Creation Date"], format="%m/%d/%Y", errors="coerce"
    )
    df["purchase_date"] = pd.to_datetime(
        df["Purchase Date"], format="%m/%d/%Y", errors="coerce"
    )
    # Date sanity: the raw Purchase Date field is dirty (years from 1911 to
    # 2912). Only keep plausible years; the rest become NaN so no downstream
    # analysis can silently use an absurd date.
    df["creation_date"] = df["creation_date"].where(
        df["creation_date"].map(lambda d: _plausible_year(d, 2000, 2026))
    )
    df["purchase_date"] = df["purchase_date"].where(
        df["purchase_date"].map(lambda d: _plausible_year(d, 2000, 2026))
    )

    # --- derived features ---
    # location is a dirty field "ZIP\n(lat,lon)" -> keep only the ZIP code
    df["zip_code"] = df["Location"].astype(str).str.split("\n").str[0].str.strip()
    df["zip_code"] = df["zip_code"].where(df["zip_code"].str.match(r"^\d{5}$"))
    # UNSPSC segment (first 2 digits of the 8-digit classification code)
    df["segment"] = df["Normalized UNSPSC"].astype("Int64").astype(str).str[:2]
    df["segment"] = df["segment"].where(df["segment"] != "<NA>")
    # acquisition-method control class (initial rule)
    df["method_class"] = df["Acquisition Method"].map(METHOD_CLASS_LOOKUP)

    clean = df[
        [
            "creation_date", "purchase_date", "Fiscal Year",
            "Purchase Order Number", "Requisition Number",
            "Acquisition Type", "Acquisition Method", "method_class",
            "Department Name", "Supplier Name", "Supplier Code",
            "Item Name", "Item Description", "quantity",
            "unit_price", "total_price", "Normalized UNSPSC", "segment",
            "zip_code", "Location",
        ]
    ].rename(
        columns={
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
    )

    out = os.path.join(OUT_DIR, "procurement_clean.parquet")
    clean.to_parquet(out, index=False)
    print("ROWS", len(clean))
    print("OUT", out)
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
