#!/usr/bin/env python3
"""Pipeline-component ablation: what each audit stage adds to the conclusion.

Asks one question of every synthetic corpus: does the random-split (or
published-split) accuracy overstate accuracy on new traffic by more than the
0.01 materiality threshold? Three workflows answer it with the frozen checks:

  W1 diagnostic only      dedup_check: `flag` (any test row reuses a training
                          feature vector) is read as "material", otherwise
                          "not material".
  W2 + control            W1, then homogeneity_test on a W1 flag: a leakage
                          class means "material", every class cleared means
                          "not material", otherwise "inconclusive".
  W3 + intervention       W2, then two interventions whose verdicts replace
                          it: repeated_seed_falsification_check (grouped
                          resplit, 10 seeds) and a reuse intervention (accuracy
                          on the whole test set minus accuracy on its rows
                          whose vector is absent from training, 10 model
                          seeds, t interval widened by the test-set sampling
                          margin, needs 30 such rows). "material" if either
                          interval sits above 0.01, "not material" if every
                          applicable one sits below it, otherwise
                          "inconclusive".

Ground truth is set by each scenario's construction (TRUTH below) and checked
against the generator: the model trained on the published training split is
scored on a fresh 5,000-row sample of the deployment population (new groups,
no copies), and the gap is the published-test accuracy minus that, averaged
over 10 model seeds. A single run's gap carries test-sampling noise (sd about
0.011 at 0.8 accuracy on 2,000 test rows), so it verifies the design truth on
average and does not replace it: the first run scored truth per run from this
gap and called one clean corpus material on noise alone (gap +0.021, scenario
mean -0.002).

Scenarios (10 generator seeds each, 10,000 rows, 80/20 split):
  clean          independent rows, moderate class signal
  repetitive     each class is 40 scripted templates, copied exactly; the
                 deployment traffic repeats the same templates
  group_noisy    600 flow groups with their own feature signature and a
                 random label; rows vary slightly within a group
  group_exact    as group_noisy, rows repeated exactly within a group
  presplit_easy  a released test set with 20% of its rows copied from
                 training, on data whose classes are easy to separate
  presplit_hard  the same copying on data whose classes are hard to separate

The scenarios are chosen to put each stage where it is meant to help or fail;
the result shows how each workflow behaves in those situations and is not a
rate over real datasets.

Usage: venv/bin/python3 validation/workflow_ablation.py [--reps N] [--jobs N]
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
warnings.filterwarnings("ignore")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from joblib import Parallel, delayed  # noqa: E402
from scipy import stats  # noqa: E402
from sklearn.ensemble import RandomForestClassifier  # noqa: E402
from sklearn.metrics import accuracy_score  # noqa: E402

from ids2eval.audit import dedup as dedup_mod  # noqa: E402
from ids2eval.audit import homogeneity, repeated_seed_falsification  # noqa: E402
from ids2eval.audit._materiality import accuracy_gap_margin  # noqa: E402
from ids2eval.config import DEFAULTS  # noqa: E402
from ids2eval.data import dataset, features  # noqa: E402

N_ROWS = 10_000
N_DEPLOY = 5_000
N_FEATS = 6
CLASSES = np.array(["normal", "dos", "scan"])
PRIORS = [0.6, 0.25, 0.15]
GROUP = ["src_ip", "src_port", "dst_ip", "dst_port", "proto"]
THRESHOLD = 0.01
N_SEEDS = 10  # repeated_seed_count used in Section 6.3
MIN_NOVEL = 30
SCENARIOS = ["clean", "repetitive", "group_noisy", "group_exact", "presplit_easy", "presplit_hard"]
TRUTH = {"clean": "not material", "repetitive": "not material", "group_noisy": "material",
         "group_exact": "material", "presplit_easy": "not material", "presplit_hard": "material"}
OUT = Path(__file__).resolve().parent.parent / "results" / "analysis" / "workflow_ablation.json"
FEATS = [f"f{i}" for i in range(N_FEATS)]


def cfg_for() -> dict:
    cfg = copy.deepcopy(DEFAULTS)
    cfg["schema"]["label_column"] = "label"
    cfg["dataset"]["raw_files"] = ["<in-memory>"]
    cfg["dataset"]["group_columns"] = list(GROUP)
    cfg["schema"]["drop_columns"] = list(GROUP)
    cfg["audit"]["repeated_seed_count"] = N_SEEDS
    return cfg


def tuples(gid: np.ndarray) -> pd.DataFrame:
    """One 5-tuple per group id."""
    return pd.DataFrame({
        "src_ip": [f"10.{g // 62500}.{(g // 250) % 250}.{g % 250}" for g in gid],
        "src_port": 1024 + gid % 60000, "dst_ip": "192.168.1.1", "dst_port": 443, "proto": "tcp",
    })


def shifted(rng, y, scale):
    """Class-shifted Gaussian features: larger scale, easier classes."""
    mu = {c: rng.normal(scale=scale, size=N_FEATS) for c in CLASSES}
    def draw(labels):
        return np.array([mu[c] for c in labels]) + rng.normal(size=(len(labels), N_FEATS))
    return draw


class Scenario:
    """Builds the audited corpus and a sampler for the deployment population."""

    def __init__(self, name: str, seed: int):
        rng = np.random.default_rng(seed)
        self.name, self.rng = name, rng
        self.next_gid = 0
        self.published = None
        if name in ("clean", "presplit_easy", "presplit_hard"):
            scale = {"clean": 0.9, "presplit_easy": 3.0, "presplit_hard": 0.35}[name]
            self.draw = shifted(rng, None, scale)
            df = self._rows(N_ROWS)
            if name.startswith("presplit"):
                train, test = dataset._random_split(df, "label", {"split_ratio": 0.8}, seed=seed)
                k = len(test) // 5
                src = train.sample(n=k, random_state=seed).to_numpy()
                test.iloc[:k] = src  # copies keep their original's 5-tuple and label
                test = test.infer_objects()
                self.published = (train, test)
                df = pd.concat([train, test], ignore_index=True)
            self.combined = df
        elif name == "repetitive":
            self.templates = {c: rng.normal(scale=2.0, size=(40, N_FEATS)) + i * 1.5
                              for i, c in enumerate(CLASSES)}
            self.combined = self._templ(N_ROWS)
        else:  # group_noisy / group_exact
            self.n_groups, self.per = 600, N_ROWS // 600 + 1
            self.combined = self._groups(self.n_groups, self.per).iloc[:N_ROWS].reset_index(drop=True)
        if self.published is None:
            self.published = dataset._random_split(self.combined, "label", {"split_ratio": 0.8}, seed=seed)

    def _gids(self, n):
        g = np.arange(self.next_gid, self.next_gid + n)
        self.next_gid += n
        return g

    def _rows(self, n):
        y = self.rng.choice(CLASSES, size=n, p=PRIORS)
        df = tuples(self._gids(n))
        df[FEATS] = self.draw(y)
        df["label"] = y
        return df

    def _templ(self, n):
        y = self.rng.choice(CLASSES, size=n, p=PRIORS)
        pick = self.rng.integers(0, 40, size=n)
        df = tuples(self._gids(n))
        df[FEATS] = np.array([self.templates[c][j] for c, j in zip(y, pick)])
        df["label"] = y
        return df

    def _groups(self, n_groups, per):
        gid = self._gids(n_groups)
        cent = self.rng.normal(scale=3.0, size=(n_groups, N_FEATS))
        glab = self.rng.choice(CLASSES, size=n_groups, p=PRIORS)
        rows = np.repeat(np.arange(n_groups), per)
        df = tuples(gid[rows])
        jitter = 0.0 if self.name == "group_exact" else 0.3
        df[FEATS] = cent[rows] + jitter * self.rng.normal(size=(len(rows), N_FEATS))
        df["label"] = glab[rows]
        return df

    def deployment(self):
        if self.name == "repetitive":
            return self._templ(N_DEPLOY)
        if self.name.startswith("group"):
            return self._groups(N_DEPLOY // 10, 10)
        return self._rows(N_DEPLOY)


def fit(train, cols, seed):
    clf = RandomForestClassifier(n_estimators=100, random_state=seed, n_jobs=1)
    return clf.fit(train[cols].to_numpy(), train["label"])


def acc(clf, df, cols):
    return float(accuracy_score(df["label"], clf.predict(df[cols].to_numpy())))


def t_interval(values, extra=0.0):
    m = float(np.mean(values))
    half = stats.t.ppf(0.975, len(values) - 1) * float(np.std(values, ddof=1)) / len(values) ** 0.5
    return m, m - half - extra, m + half + extra


def verdict(lo, hi):
    return "material" if lo > THRESHOLD else ("not material" if hi < THRESHOLD else "inconclusive")


def run_one(name: str, seed: int) -> dict:
    sc = Scenario(name, seed)
    cfg = cfg_for()
    cfg["random_seed"] = seed
    train, test = sc.published
    deploy = sc.deployment()

    # ground truth: published-test accuracy against fresh deployment traffic
    gaps, pub_accs = [], []
    for s in range(N_SEEDS):
        clf = fit(train, FEATS, s)
        a_pub = acc(clf, test, FEATS)
        pub_accs.append(a_pub)
        gaps.append(a_pub - acc(clf, deploy, FEATS))
    true_gap = float(np.mean(gaps))
    truth = TRUTH[name]

    # W1: diagnostic only
    d = dedup_mod.check(train, test, cfg)
    w1 = "material" if d["status"] == "flag" else "not material"

    # W2: + train-internal control
    h = homogeneity.check(train, test, cfg)
    classes = [v["classification"] for v in h["details"]["per_class"].values()]
    if w1 == "not material":
        w2 = "not material"
    elif "leakage" in classes:
        w2 = "material"
    elif classes and all(c in ("equivalent", "below_control") for c in classes):
        w2 = "not material"
    else:
        w2 = "inconclusive"

    # W3: + interventions
    rs = repeated_seed_falsification.check(cfg, combined=sc.combined)
    lo_g, hi_g = rs["details"]["ci_95"]
    interventions = {"grouped_resplit": {"mean": rs["details"]["mean_drop"], "ci": [lo_g, hi_g],
                                         "verdict": verdict(lo_g, hi_g)}}
    key = pd.util.hash_pandas_object(train[FEATS], index=False)
    novel = test.loc[~pd.util.hash_pandas_object(test[FEATS], index=False).isin(set(key)).to_numpy()]
    if len(novel) >= MIN_NOVEL and len(novel) < len(test):
        drops, a_full, a_nov = [], [], []
        for s in range(N_SEEDS):
            clf = fit(train, FEATS, s)
            a_full.append(acc(clf, test, FEATS))
            a_nov.append(acc(clf, novel, FEATS))
            drops.append(a_full[-1] - a_nov[-1])
        margin = accuracy_gap_margin(np.mean(a_full), len(test), np.mean(a_nov), len(novel))
        m, lo_r, hi_r = t_interval(drops, extra=margin)
        interventions["reuse"] = {"mean": m, "ci": [lo_r, hi_r], "verdict": verdict(lo_r, hi_r),
                                  "novel_rows": int(len(novel))}
    vs = [v["verdict"] for v in interventions.values()]
    w3 = "material" if "material" in vs else ("not material" if all(v == "not material" for v in vs)
                                              else "inconclusive")

    return {"scenario": name, "seed": seed, "truth": truth, "true_gap": true_gap,
            "published_acc": float(np.mean(pub_accs)), "dedup_status": d["status"],
            "test_reuse_rows": int(d["details"]["test_leakage_dropped"]),
            "homogeneity_classes": classes, "interventions": interventions,
            "W1": w1, "W2": w2, "W3": w3}


def summarize(rows):
    table = {}
    for name in SCENARIOS:
        rs = [r for r in rows if r["scenario"] == name]
        if not rs:
            continue
        gaps = [r["true_gap"] for r in rs]
        entry = {"truth": TRUTH[name], "true_gap_mean": float(np.mean(gaps)),
                 "true_gap_sd": float(np.std(gaps, ddof=1)) if len(gaps) > 1 else 0.0,
                 "true_gap_range": [min(gaps), max(gaps)]}
        for w in ("W1", "W2", "W3"):
            entry[w] = {"correct": sum(r[w] == r["truth"] for r in rs),
                        "wrong": sum(r[w] not in (r["truth"], "inconclusive") for r in rs),
                        "inconclusive": sum(r[w] == "inconclusive" for r in rs)}
        table[name] = entry
    return table


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=10)
    ap.add_argument("--jobs", type=int, default=-1)
    ap.add_argument("--scenarios", nargs="*", default=SCENARIOS)
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()
    tasks = [(n, 3000 + 100 * i + r) for i, n in enumerate(SCENARIOS) if n in args.scenarios
             for r in range(args.reps)]
    rows = Parallel(n_jobs=args.jobs, verbose=5)(delayed(run_one)(n, s) for n, s in tasks)
    result = {"threshold": THRESHOLD, "n_rows": N_ROWS, "n_seeds": N_SEEDS, "runs": rows,
              "summary": summarize(rows)}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, indent=2, default=float))
    for name, e in result["summary"].items():
        print(name, e["truth"], "gap mean %.4f sd %.4f" % (e["true_gap_mean"], e["true_gap_sd"]),
              {w: e[w] for w in ("W1", "W2", "W3")}, flush=True)
    print("DONE")


if __name__ == "__main__":
    main()
