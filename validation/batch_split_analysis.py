#!/usr/bin/env python3
"""Staged, resumable split analysis for a dataset too large for the local VM.

Runs three analyses on one dataset in a single process, loading the data once:

  load         read raw_files and cache the combined frame as parquet
  homogeneity  homogeneity_test (current Newcombe-Wilson version) on the audited
               random split, before and after dedup, plus the per-class
               baseline and threshold grid of homogeneity_sensitivity.py
  seeds        paired random-vs-grouped seeds, scoring RandomForest (as
               class_sensitive_seeds.py) and LogisticRegression + XGBoost (as
               model_sensitivity.py) on the same two splits per seed
  summarize    writes class_sensitive_seeds.json and model_sensitivity.json in
               the same layout as the local results, keyed by dataset name

Every stage records its start, end and outcome in OUT/state.json and is skipped
on a rerun once done. The seeds stage checkpoints each (seed, split, model
group) unit to OUT/seeds/seed_<n>.json, so a rerun after a crash or a Spot
preemption only repeats the unit that was in progress. FORCE_STAGES (comma
separated) reruns stages that are already marked done.

Usage: python3 validation/batch_split_analysis.py CONFIG OUT_DIR N_SEEDS
"""
from __future__ import annotations

import gc
import json
import logging
import os
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd
from class_sensitive_seeds import score as rf_score
from class_sensitive_seeds import summarize as rf_summarize
from homogeneity_sensitivity import CUTOFFS, MARGINS, classify, distances
from model_sensitivity import score_all as other_score
from model_sensitivity import summarize as other_summarize

from ids2eval.audit import homogeneity as h
from ids2eval.config import load_config
from ids2eval.data import dataset
from ids2eval.data.label_grouping import apply_attack_type_mapping

STAGES = ["load", "homogeneity", "seeds", "summarize"]
log = logging.getLogger("batch_split_analysis")


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_json(path: Path, obj) -> None:
    # Write then rename, so a sync or a kill never sees a half-written file.
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, default=str))
    tmp.replace(path)


class State:
    def __init__(self, path: Path):
        self.path = path
        self.data = json.loads(path.read_text()) if path.exists() else {}

    def done(self, stage: str) -> bool:
        return self.data.get(stage, {}).get("status") == "done"

    def mark(self, stage: str, status: str, **extra) -> None:
        entry = self.data.setdefault(stage, {"attempts": 0})
        if status == "running":
            entry["attempts"] += 1
            entry["started"] = now()
            entry.pop("error", None)
        else:
            entry["finished"] = now()
        entry["status"] = status
        entry.update(extra)
        write_json(self.path, self.data)


def stage_load(cfg, out: Path) -> pd.DataFrame:
    path = out / "cache" / "combined.parquet"
    if path.exists():
        log.info("reading cached combined frame %s", path)
        return pd.read_parquet(path)
    combined = dataset.load_raw_combined(cfg["dataset"], seed=cfg["random_seed"])
    path.parent.mkdir(exist_ok=True)
    tmp = path.with_suffix(".parquet.tmp")
    combined.to_parquet(tmp, index=False)
    tmp.replace(path)
    log.info("cached combined frame: %s rows -> %s (%.1f MB)", f"{len(combined):,}", path, path.stat().st_size / 1e6)
    return combined


def homogeneity_pass(train_df, test_df, cfg) -> dict:
    result = h.check(train_df, test_df, cfg)
    dists = distances(train_df, test_df, cfg)
    baseline, grid = {}, {}
    for cls, (test_d, ctrl_d) in dists.items():
        p_t, p_c = float((test_d < 1e-6).mean()), float((ctrl_d < 1e-6).mean())
        lo, hi = h._rate_diff_ci(p_t, len(test_d), p_c, len(ctrl_d))
        baseline[cls] = {"test_rate": p_t, "control_rate": p_c, "n_test": len(test_d),
                         "n_control": len(ctrl_d), "ci": [lo, hi], "class": classify(lo, hi, 0.05)}
    for cutoff in CUTOFFS:
        for margin in MARGINS:
            counts = {"leakage": 0, "cleared": 0, "inconclusive": 0}
            for test_d, ctrl_d in dists.values():
                p_t, p_c = float((test_d < cutoff).mean()), float((ctrl_d < cutoff).mean())
                lo, hi = h._rate_diff_ci(p_t, len(test_d), p_c, len(ctrl_d))
                counts[classify(lo, hi, margin)] += 1
            grid[f"cutoff={cutoff:g},margin={margin:g}"] = counts
    return {"check": result, "baseline": baseline, "grid": grid}


def stage_homogeneity(combined, cfg, out: Path) -> None:
    label = cfg["schema"]["label_column"]
    train_df, test_df = dataset._random_split(combined, label, cfg["dataset"], seed=cfg["random_seed"])
    train_df, test_df = apply_attack_type_mapping(train_df, test_df, cfg)
    log.info("audited split: train=%s test=%s", f"{len(train_df):,}", f"{len(test_df):,}")
    result = {"split": {"train_rows": len(train_df), "test_rows": len(test_df)}}
    t0 = time.time()
    result["before"] = homogeneity_pass(train_df, test_df, cfg)
    log.info("before dedup: %s (%.0fs)", result["before"]["check"]["status"], time.time() - t0)
    train_df, test_df, stats = dataset.dedup(train_df, test_df, cfg)
    result["dedup"] = stats
    log.info("dedup: %s", stats)
    t0 = time.time()
    result["after"] = homogeneity_pass(train_df, test_df, cfg)
    log.info("after dedup: %s (%.0fs)", result["after"]["check"]["status"], time.time() - t0)
    write_json(out / "homogeneity.json", result)


def stage_seeds(combined, cfg, out: Path, n_seeds: int) -> None:
    label = cfg["schema"]["label_column"]
    seed_dir = out / "seeds"
    seed_dir.mkdir(exist_ok=True)
    splitters = {"random": dataset._random_split, "grouped": dataset._grouped_split}
    scorers = {"random_forest": rf_score, "other_models": other_score}
    for seed in range(n_seeds):
        path = seed_dir / f"seed_{seed}.json"
        rec = json.loads(path.read_text()) if path.exists() else {"seed": seed, "random": {}, "grouped": {}}
        for split_name, splitter in splitters.items():
            missing = [m for m in scorers if m not in rec[split_name]]
            if not missing:
                continue
            t0 = time.time()
            train_df, test_df = splitter(combined, label, cfg["dataset"], seed=seed)
            log.info("seed %d %s split: train=%s test=%s (%.0fs)", seed, split_name,
                     f"{len(train_df):,}", f"{len(test_df):,}", time.time() - t0)
            for model in missing:
                t0 = time.time()
                rec[split_name][model] = scorers[model](train_df, test_df, label, cfg, seed)
                rec[split_name][model + "_seconds"] = round(time.time() - t0, 1)
                write_json(path, rec)
                log.info("seed %d %s %s done (%.0fs)", seed, split_name, model, time.time() - t0)
            del train_df, test_df
            gc.collect()
        r, g = rec["random"], rec["grouped"]
        log.info("seed %d: RF acc %.5f->%.5f mF1 %.4f->%.4f; LR acc %.4f->%.4f; XGB acc %.5f->%.5f mF1 %.4f->%.4f",
                 seed, r["random_forest"]["accuracy"], g["random_forest"]["accuracy"],
                 r["random_forest"]["macro_f1"], g["random_forest"]["macro_f1"],
                 r["other_models"]["logistic_regression"]["accuracy"],
                 g["other_models"]["logistic_regression"]["accuracy"],
                 r["other_models"]["xgboost"]["accuracy"], g["other_models"]["xgboost"]["accuracy"],
                 r["other_models"]["xgboost"]["macro_f1"], g["other_models"]["xgboost"]["macro_f1"])


def stage_summarize(cfg, out: Path, n_seeds: int) -> None:
    recs = [json.loads((out / "seeds" / f"seed_{s}.json").read_text()) for s in range(n_seeds)]
    name = cfg["dataset"]["name"]
    rf = [{"seed": r["seed"], "random": r["random"]["random_forest"], "grouped": r["grouped"]["random_forest"]}
          for r in recs]
    other = [{"seed": r["seed"], "random": r["random"]["other_models"], "grouped": r["grouped"]["other_models"]}
             for r in recs]
    write_json(out / "class_sensitive_seeds.json", {name: {"seeds": rf, "summary": rf_summarize(rf)}})
    write_json(out / "model_sensitivity.json", {name: {"seeds": other, "summary": other_summarize(other)}})
    log.info("RF summary: %s", json.dumps({k: v for k, v in rf_summarize(rf).items() if k != "per_class_recall_drop"}))
    log.info("LR/XGB summary: %s", json.dumps(other_summarize(other)))


def main() -> int:
    config_path, out, n_seeds = sys.argv[1], Path(sys.argv[2]), int(sys.argv[3])
    out.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s", datefmt="%Y-%m-%dT%H:%M:%S")
    cfg = load_config(config_path)
    state = State(out / "state.json")
    force = {s for s in os.environ.get("FORCE_STAGES", "").split(",") if s}
    log.info("dataset %s, %d seeds, stages already done: %s, forced: %s", cfg["dataset"]["name"], n_seeds,
             [s for s in STAGES if state.done(s)], sorted(force))

    combined = None
    for stage in STAGES:
        if state.done(stage) and stage not in force:
            log.info("stage %s: already done, skipping", stage)
            continue
        needs_data = stage in ("homogeneity", "seeds")
        if stage == "load" or (needs_data and combined is None):
            # The cached parquet makes this cheap after the first attempt.
            if stage == "load":
                log.info("stage load: start")
                state.mark("load", "running")
            else:
                log.info("loading data for stage %s", stage)
            t0 = time.time()
            try:
                combined = stage_load(cfg, out)
            except Exception as e:
                state.mark("load", "failed", error=f"{type(e).__name__}: {e}")
                log.error("stage load failed:\n%s", traceback.format_exc())
                return 1
            if stage == "load":
                state.mark("load", "done", rows=len(combined), columns=combined.shape[1],
                           seconds=round(time.time() - t0, 1))
                log.info("stage load: done in %.0fs", time.time() - t0)
                continue
        log.info("stage %s: start", stage)
        state.mark(stage, "running")
        t0 = time.time()
        try:
            if stage == "homogeneity":
                stage_homogeneity(combined, cfg, out)
            elif stage == "seeds":
                stage_seeds(combined, cfg, out, n_seeds)
            else:
                stage_summarize(cfg, out, n_seeds)
        except Exception as e:
            state.mark(stage, "failed", error=f"{type(e).__name__}: {e}", seconds=round(time.time() - t0, 1))
            log.error("stage %s failed:\n%s", stage, traceback.format_exc())
            return 1
        state.mark(stage, "done", seconds=round(time.time() - t0, 1))
        log.info("stage %s: done in %.0fs", stage, time.time() - t0)
    log.info("ALL STAGES DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
