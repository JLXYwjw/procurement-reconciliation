# -*- coding: utf-8 -*-
"""Clean the CA procurement purchase-order extract and persist a tidy table.

The raw file has ~909k physical lines but ~346k logical records (some text
fields span multiple lines). We normalize money, dates and identifiers, then
save a clean parquet for downstream analysis.
"""
import os

import numpy as np
import pandas as pd

SRC = r"D:\B编程\powerBI\github\datasets\procurement\PURCHASE ORDER DATA EXTRACT 2012-2015_0.csv"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "output")
os.makedirs(OUT_DIR, exist_ok=True)


def parse_amount(x):
    """Parse a '$1,234.56'-style cell into a float; NaN stays NaN."""
    if pd.isna(x):
        return np.nan
    s = str(x).replace("$", "").replace(",", "").replace(" ", "").strip()
    try:
        return float(s)
    except Exception:
        return np.nan


def main():
    df = pd.read_csv(SRC, encoding="utf-8")
    df["unit_price"] = df["Unit Price"].apply(parse_amount)
    df["total_price"] = df["Total Price"].apply(parse_amount)
    df["quantity"] = pd.to_numeric(df["Quantity"], errors="coerce")
    df["creation_date"] = pd.to_datetime(
        df["Creation Date"], format="%m/%d/%Y", errors="coerce"
    )
    df["purchase_date"] = pd.to_datetime(
        df["Purchase Date"], format="%m/%d/%Y", errors="coerce"
    )

    clean = df[
        [
            "creation_date", "purchase_date", "Fiscal Year",
            "Purchase Order Number", "Requisition Number",
            "Acquisition Type", "Acquisition Method",
            "Department Name", "Supplier Name", "Supplier Code",
            "Item Name", "Item Description", "quantity",
            "unit_price", "total_price", "Normalized UNSPSC", "Location",
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
        }
    )

    out = os.path.join(OUT_DIR, "procurement_clean.parquet")
    clean.to_parquet(out, index=False)
    print("ROWS", len(clean))
    print("OUT", out)
    print("TOTAL_PRICE_SUM", round(float(clean["total_price"].sum()), 2))
    print("ROWS_WITH_PRICE", int(clean["total_price"].notna().sum()))


if __name__ == "__main__":
    main()
