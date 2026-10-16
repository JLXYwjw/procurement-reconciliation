# -*- coding: utf-8 -*-
"""Pure logic used by supplier_cluster.py, factored out so it can be tested
independently of the (large, git-excluded) parquet outputs.

Kept dependency-free (pandas only) so a clean clone can unit-test the tiering
rule without reproducing the whole dataset.
"""
import pandas as pd


def label_tiers(prof):
    """Map cluster -> business tier from a cluster profile.

    The rule encodes the *business* definition of "strategic":
      - the highest-spend cluster whose suppliers RECUR (median years >= 2)
        is the recurring core;
      - the highest-spend single-year cluster is the one-off/large tier;
      - the rest are regular / tail by spend.

    prof: DataFrame indexed by cluster id with columns
          ['n','spend','med_spend','med_seg_share','med_dept_share',
           'med_years','med_freq'], as produced by supplier_cluster.py.
    Returns: pd.Series indexed by cluster id -> tier name.
    """
    recur = prof[prof["med_years"] >= 2].sort_values("spend", ascending=False)
    core_c = recur.index[0] if len(recur) else prof.sort_values("spend", ascending=False).index[0]

    once = prof[prof["med_years"] < 2].sort_values("spend", ascending=False)
    oneoff_c = once.index[0] if len(once) else None

    rest = [c for c in prof.index if c not in (core_c, oneoff_c)]
    rest = sorted(rest, key=lambda c: prof.loc[c, "spend"], reverse=True)

    names = {core_c: "core_strategic"}
    if oneoff_c is not None:
        names[oneoff_c] = "oneoff_large"
    for i, c in enumerate(rest):
        names[c] = ["regular", "tail"][i]
    return pd.Series(names).reindex(prof.index)
