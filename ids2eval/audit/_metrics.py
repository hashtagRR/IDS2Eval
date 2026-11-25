"""Per-metric scoring and verdicts for the intervention checks.

An intervention check compares a model's score under two conditions (random
vs. grouped split, all features vs. some removed). Accuracy alone can hide a
change that falls on a minority class: removing identifier columns can cost
half a point of accuracy and six points of balanced accuracy at once. So each
comparison is scored on three metrics, all proportions on [0, 1]:

    accuracy            share of test rows classified correctly
    balanced_accuracy   mean per-class recall over the classes present in the test labels
    macro_f1            unweighted mean of per-class F1 over every class seen in either
                        the test labels or the predictions (an undefined F1 counts as 0)

and gets one verdict per metric. They are computed from the confusion matrix,
so a check keeps one small matrix per fit instead of the predictions, and a
sampling margin can be drawn by resampling the matrix's cells.

Thresholds: audit.materiality_thresholds.<check> is either the old single value
(applied to every metric) or a mapping from metric name to value. The status a
check reports is the most severe verdict among audit.materiality_metrics; the
per-metric verdicts are always reported, so which metric moved stays visible.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

METRICS = ("accuracy", "balanced_accuracy", "macro_f1")

# Status severity for combining per-metric verdicts into one check status.
_SEVERITY = {"ok": 0, "warning": 1, "flag": 2}

# Resamples for the bootstrap margin of balanced accuracy and macro-F1. The
# margin is a 95% half-width, so a few hundred resamples pin it to within a few
# percent of itself; the seed is fixed so a run's verdicts are reproducible.
_BOOTSTRAP_RESAMPLES = 400
_BOOTSTRAP_SEED = 0


@dataclass(frozen=True)
class Scores:
    """A fit's test-set confusion matrix (rows: true class, columns: predicted)."""

    labels: tuple
    confusion: np.ndarray

    @property
    def n(self) -> int:
        return int(self.confusion.sum())

    @property
    def metrics(self) -> dict[str, float]:
        return metrics_from_confusion(self.confusion)


def scores_from_predictions(y_true, y_pred) -> Scores:
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    labels = np.unique(np.concatenate([y_true, y_pred]))
    index = {label: i for i, label in enumerate(labels)}
    true_idx = np.fromiter((index[v] for v in y_true), dtype=np.int64, count=len(y_true))
    pred_idx = np.fromiter((index[v] for v in y_pred), dtype=np.int64, count=len(y_pred))
    k = len(labels)
    confusion = np.bincount(true_idx * k + pred_idx, minlength=k * k).reshape(k, k)
    return Scores(tuple(labels.tolist()), confusion)


def metrics_from_confusion(confusion: np.ndarray) -> dict[str, float]:
    """The three metrics, matching scikit-learn's accuracy_score,
    balanced_accuracy_score and f1_score(average="macro", zero_division=0)."""
    confusion = np.asarray(confusion, dtype=float)
    total = confusion.sum()
    diag = np.diag(confusion)
    support = confusion.sum(axis=1)
    predicted = confusion.sum(axis=0)
    present = support > 0
    recall = np.divide(diag, support, out=np.zeros_like(diag), where=present)
    precision = np.divide(diag, predicted, out=np.zeros_like(diag), where=predicted > 0)
    denom = precision + recall
    f1 = np.divide(2 * precision * recall, denom, out=np.zeros_like(diag), where=denom > 0)
    seen = present | (predicted > 0)
    return {
        "accuracy": float(diag.sum() / total) if total else 0.0,
        "balanced_accuracy": float(recall[present].mean()) if present.any() else 0.0,
        "macro_f1": float(f1[seen].mean()) if seen.any() else 0.0,
    }


def gap_margins(a: Scores, b: Scores) -> dict[str, float]:
    """Half-width of a 95% interval on each metric's difference between two fits
    scored on test sets treated as independent (conservative when they share
    rows). Accuracy uses the normal approximation the checks have always used, so
    accuracy verdicts are unchanged; the other two metrics have no simple closed
    form, so their margin comes from resampling each confusion matrix's cells
    (equivalent to resampling test rows with replacement)."""
    acc_a, acc_b = a.metrics["accuracy"], b.metrics["accuracy"]
    var = acc_a * (1 - acc_a) / max(a.n, 1) + acc_b * (1 - acc_b) / max(b.n, 1)
    margins = {"accuracy": 1.959964 * var ** 0.5}
    rng = np.random.default_rng(_BOOTSTRAP_SEED)
    draws_a = _resampled_metrics(a, rng)
    draws_b = _resampled_metrics(b, rng)
    for metric in ("balanced_accuracy", "macro_f1"):
        diff = draws_a[metric] - draws_b[metric]
        low, high = np.percentile(diff, [2.5, 97.5])
        margins[metric] = float((high - low) / 2)
    return margins


def _resampled_metrics(scores: Scores, rng: np.random.Generator) -> dict[str, np.ndarray]:
    flat = scores.confusion.ravel().astype(float)
    if scores.n == 0:
        return {m: np.zeros(_BOOTSTRAP_RESAMPLES) for m in METRICS}
    draws = rng.multinomial(scores.n, flat / flat.sum(), size=_BOOTSTRAP_RESAMPLES)
    k = scores.confusion.shape[0]
    values = [metrics_from_confusion(d.reshape(k, k)) for d in draws]
    return {m: np.array([v[m] for v in values]) for m in METRICS}


def thresholds(cfg: dict, check: str, default):
    """Per-metric thresholds for a check: {metric: value}. The configured value
    may be the check's single value (or {"warning", "flag"} tiers), applied to
    every metric, or a mapping from metric name to that value; metrics the
    mapping leaves out keep the check's default."""
    configured = cfg["audit"]["materiality_thresholds"].get(check)
    if configured is None:
        return dict.fromkeys(METRICS, default)
    if isinstance(configured, dict) and set(configured) <= set(METRICS):
        return {m: configured.get(m, default) for m in METRICS}
    return dict.fromkeys(METRICS, configured)


def single_comparison_verdict(drop: float, margin: float, threshold: float) -> str:
    """The rule for one comparison on finite test sets: material (flag) only once
    the drop clears the threshold by more than its sampling margin; above the
    threshold but within the margin is inconclusive (warning)."""
    if drop - margin > threshold:
        return "flag"
    if drop > threshold:
        return "warning"
    return "ok"


def tiered_verdict(drop: float, tiers: dict) -> str:
    """The rule of the tiered checks that judge a point estimate: flag above the
    flag tier, warning above the warning tier, ok otherwise."""
    if drop > tiers["flag"]:
        return "flag"
    if drop > tiers["warning"]:
        return "warning"
    return "ok"


def interval_verdict(ci_low: float, ci_high: float, threshold: float) -> str:
    """The three-way rule on a confidence interval for a mean drop: material if
    the whole interval lies above the threshold, not material if it lies below,
    inconclusive if it straddles it."""
    if ci_low > threshold:
        return "flag"
    if ci_high < threshold:
        return "ok"
    return "warning"


def combined_status(verdicts: dict[str, str], cfg: dict) -> str:
    """The most severe verdict among the metrics audit.materiality_metrics names."""
    chosen = [verdicts[m] for m in cfg["audit"]["materiality_metrics"] if m in verdicts]
    return max(chosen, key=_SEVERITY.__getitem__) if chosen else "ok"


def error_ratio(baseline_accuracy: float, condition_accuracy: float) -> float | None:
    """Condition error rate over baseline error rate. Near a ceiling an absolute
    drop is small even when the error rate multiplies; None if the baseline makes
    no errors."""
    base_error = 1 - baseline_accuracy
    if base_error <= 0:
        return None
    return (1 - condition_accuracy) / base_error


def describe(verdicts: dict[str, str]) -> str:
    words = {"flag": "material", "warning": "inconclusive", "ok": "not material"}
    return ", ".join(f"{m.replace('_', ' ')} {words[v]}" for m, v in verdicts.items())
