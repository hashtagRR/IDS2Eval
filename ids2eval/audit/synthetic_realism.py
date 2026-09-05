"""Synthetic-vs-real distributional realism check (v2, opt-in).

Per Layeghy et al. 2021 and Catillo et al. 2021: lab-generated/synthetic
IDS traffic can diverge from real network traffic in ways that make a
dataset's near-perfect classifier accuracy an artifact of unrepresentative
data rather than a real capability. Needs a reference real-traffic sample
(audit.reference_dataset) to compare against — there's no way to detect
"unrealistic compared to what" without something to compare to.

Method: a domain classifier trained to distinguish this dataset's rows
from the reference sample's rows. High separability (AUC) means the two
are easily distinguishable — a specific, checkable signature of
distributional divergence, not merely "different datasets differ."
"""

from __future__ import annotations

import pandas as pd
from scipy.stats import ks_2samp
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split

from .. import chunked_io, features

DOMAIN_AUC_FLAG_THRESHOLD = 0.9
MAX_ROWS_PER_SIDE = 50_000


def check(train_df: pd.DataFrame, cfg: dict) -> dict:
    dataset_cfg = cfg["dataset"]
    ref_df = chunked_io.load_file(
        cfg["audit"]["reference_dataset"], dataset_cfg["chunk_size"], dataset_cfg["max_rows"]
    )

    cols = [c for c in features.feature_columns(train_df, cfg) if c in ref_df.columns]
    if not cols:
        return {
            "check": "synthetic_realism_check", "status": "warning",
            "summary": "no feature columns in common with reference_dataset", "details": {},
        }

    ours = train_df.sample(n=min(len(train_df), MAX_ROWS_PER_SIDE), random_state=0)
    ref = ref_df.sample(n=min(len(ref_df), MAX_ROWS_PER_SIDE), random_state=0)

    ours_enc, (ref_enc,) = features.encode_multi(ours, [ref], cols)
    x = pd.concat([ours_enc, ref_enc], ignore_index=True)
    y = pd.Series([0] * len(ours_enc) + [1] * len(ref_enc))

    x_train, x_test, y_train, y_test = train_test_split(x, y, test_size=0.3, random_state=0, stratify=y)
    clf = RandomForestClassifier(n_estimators=100, random_state=0, n_jobs=-1)
    clf.fit(x_train, y_train)
    domain_auc = float(roc_auc_score(y_test, clf.predict_proba(x_test)[:, 1]))

    ks_scores = {}
    for col in cols:
        if pd.api.types.is_numeric_dtype(ours[col]):
            stat, _ = ks_2samp(ours[col].dropna(), ref[col].dropna())
            ks_scores[col] = float(stat)
    top_divergent = dict(sorted(ks_scores.items(), key=lambda kv: -kv[1])[:5])

    flagged = domain_auc > DOMAIN_AUC_FLAG_THRESHOLD
    status = "flag" if flagged else "ok"
    summary = (
        f"domain classifier AUC={domain_auc:.3f} distinguishing this dataset from "
        f"reference_dataset (>{DOMAIN_AUC_FLAG_THRESHOLD} flagged as easily separable); "
        f"most divergent features (KS statistic): {top_divergent}"
    )
    return {
        "check": "synthetic_realism_check", "status": status, "summary": summary,
        "details": {"domain_auc": domain_auc, "ks_by_feature": ks_scores},
    }
