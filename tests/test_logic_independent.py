# -*- coding: utf-8 -*-
"""Independent logic tests that run WITHOUT the large parquet outputs, so a
clean clone can still verify the cleaning parsers and the tiering rule.

(The big-data output contract checks live in test_output_contract.py and skip
when the git-excluded parquet files are absent.)
"""
import numpy as np
import pandas as pd

from clean_data_simple import method_class_lookup, parse_amount
from segment_utils_simple import label_tiers


def test_parse_amount_handles_currency_strings():
    assert parse_amount("$1,234.56") == 1234.56
    assert parse_amount("$0") == 0.0
    assert parse_amount("1234.56") == 1234.56
    assert np.isnan(parse_amount(None))
    assert np.isnan(parse_amount("n/a"))


def test_method_class_mapping_covers_known_methods():
    assert method_class_lookup["Formal Competitive"] == "competitive"
    assert method_class_lookup["Statewide Contract"] == "competitive"
    assert method_class_lookup["Services are specifically exempt by statute"] == "exempt"
    assert method_class_lookup["Emergency Purchase"] == "flexible"
    assert method_class_lookup["Statement of Qualifications"] == "flexible"


def test_label_tiers_marks_recurring_highspend_as_core():
    # cluster 1 = recurring (3 yrs) high spend  -> core
    # cluster 0 = single-year high spend        -> one-off/large
    # cluster 2 = recurring but low spend       -> regular
    # cluster 3 = single-year low spend         -> tail
    prof = pd.DataFrame(
        {"spend": [1e11, 5e10, 1e9, 1e8], "med_years": [1, 3, 2, 1]},
        index=[0, 1, 2, 3],
    )
    tiers = label_tiers(prof).to_dict()
    assert tiers[1] == "core_strategic"
    assert tiers[0] == "oneoff_large"
    assert tiers[2] == "regular"
    assert tiers[3] == "tail"


def test_label_tiers_core_beats_higher_single_year_spend():
    # even if the single-year cluster spends more in total, the recurring
    # cluster is still the strategic core (business rule, not size rule)
    prof = pd.DataFrame(
        {"spend": [9e10, 6e10, 1e9, 1e8], "med_years": [1, 3, 2, 1]},
        index=[0, 1, 2, 3],
    )
    tiers = label_tiers(prof).to_dict()
    assert tiers[1] == "core_strategic"
    assert tiers[0] == "oneoff_large"
