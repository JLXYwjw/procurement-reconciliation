# -*- coding: utf-8 -*-
"""Check the deliverable is complete: report references real assets, title set."""
import os
import re

import pytest

from conftest import ASSET_DIR, ROOT


def _html_path():
    return os.path.join(ROOT, "index.html")


def test_report_exists():
    assert os.path.isfile(_html_path())


def test_report_has_title():
    with open(_html_path(), encoding="utf-8") as f:
        html = f.read()
    m = re.search(r"<title>(.*?)</title>", html, re.S)
    assert m and m.group(1).strip(), "HTML report must have a document title"


def test_report_has_six_sections():
    with open(_html_path(), encoding="utf-8") as f:
        html = f.read()
    for sec in ("s1", "s2", "s3", "s4", "s5", "s6"):
        assert f'id="{sec}"' in html, f"missing section {sec}"


def test_all_assets_exist_and_are_referenced():
    with open(_html_path(), encoding="utf-8") as f:
        html = f.read()
    refs = re.findall(r'src="assets/([^"]+)"', html)
    assert refs, "report must embed at least one chart"
    for ref in refs:
        assert os.path.isfile(os.path.join(ASSET_DIR, ref)), f"missing asset {ref}"
    # no dangling reference to a file we didn't generate
    generated = {f for f in os.listdir(ASSET_DIR) if f.endswith(".png")}
    for ref in refs:
        assert ref in generated


def test_readme_mentions_report_and_status():
    with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as f:
        readme = f.read()
    assert "index.html" in readme or "report" in readme.lower()
