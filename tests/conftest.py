# -*- coding: utf-8 -*-
"""Shared fixtures / paths for the procurement tests."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

OUTPUT_DIR = os.path.join(ROOT, "output")
ASSET_DIR = os.path.join(ROOT, "assets")

# Paths to analysis outputs (excluded from git but present locally)
PROC_CLEAN = os.path.join(OUTPUT_DIR, "procurement_clean.parquet")
SUPPLIER_SEG = os.path.join(OUTPUT_DIR, "supplier_segmentation.parquet")
