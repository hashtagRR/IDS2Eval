"""Classifier benchmarking loop, driven by classifiers.* config.

Runs a "binary" stage against schema.label_column always, and a "type"
stage against schema.attack_category_column if one is configured, two
independent flat benchmarks, not a chained/routed cascade (that
architecture is explicitly out of scope for this tool). Each stage can
run under one or more scaling methods and one or more sampling
strategies (preprocessing.scaling and preprocessing.sampling.<stage>
each accept a string or a list), producing one row per
(stage, scaling, sampling, classifier) combination.

Scaling and sampling run INSIDE an imblearn Pipeline together with the
classifier, not once up front - this is a fixed leakage bug, not a
style choice: fitting a scaler/sampler once on the whole training set
and only THEN handing the result to GridSearchCV/CalibratedClassifierCV
lets those tools' internal cross-validation folds see data that was
already transformed using information from the other folds (SMOTE's
synthetic points are the sharpest version of this: a fold's synthetic
training rows can be interpolated from real neighbors that landed in a
different, supposedly-held-out fold). Wrapping [scaler, sampler,
classifier] in one Pipeline and always fitting it on raw, unscaled,
unsampled data means every internal CV fold repeats scaling/sampling
independently, exactly as it should. The plain (non-tuned, non-
calibrated) path was never affected by this, a single fit with no
internal CV has nowhere for this kind of leakage to occur, but it now
shares the same code path rather than a separate, easy-to-forget one.
"""

from __future__ import annotations

import logging
import time

import numpy as np
import pandas as pd
from imblearn.pipeline import Pipeline as ImbPipeline
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score, roc_auc_score
from sklearn.model_selection import GridSearchCV
from sklearn.preprocessing import LabelEncoder

from ..data import features
from . import classifiers as clf_registry
from .preprocessing import SAMPLERS, SCALERS

logger = logging.getLogger(__name__)

MAX_FIT_ROWS = 200_000
TUNING_CV_FOLDS = 3


def run_benchmark(train_df: pd.DataFrame, test_df: pd.DataFrame, cfg: dict) -> tuple[pd.DataFrame, dict]:
    """Returns (summary_df, extras).

    summary_df has one row per (stage, scaling, sampling, classifier)
    with the scalar metrics, including f1_macro alongside f1_weighted:
    weighted averages every class by its support, so a strong majority
    class can carry a weak result on rare classes, while macro treats
    every class equally. extras holds the heavier per-row detail
    (confusion matrix, per-class report, feature importance, best
    hyperparameters) keyed by "{stage}|{scaling}|{sampling}|{classifier}",
    a "class_distributions" entry recording each stage's original and
    post-sampling class counts (scaling doesn't change class counts, so
    it isn't part of that key), an "unseen_test_labels" entry mapping each
    stage that had test labels absent from training to {label: test row
    count} (see _encode_test_labels), and a flat "per_class_metrics" list, the
    same per-class precision/recall/f1/support already nested inside
    each combination's per_class_report, pulled out so a summary table
    can scan it without opening the per-combination JSON.
    """
    schema = cfg["schema"]
    stages = [("binary", schema["label_column"])]
    if schema["attack_category_column"]:
        stages.append(("type", schema["attack_category_column"]))

    cols = features.feature_columns(train_df, cfg)
    x_train_all, x_test = features.encode_aligned(train_df, test_df, cols)
    x_train_all, x_test = x_train_all.to_numpy(), x_test.to_numpy()

    rows = []
    per_class_rows = []
    extras: dict = {"class_distributions": {}, "unseen_test_labels": {}}
    # Progress counter for the log; one fit per (stage, sampling, scaling, classifier).
    step = 0
    total = sum(len(_sampling_strategies(cfg, st)) for st, _ in stages) * len(_scaling_strategies(cfg)) \
        * len(_resolve_classifier_list(cfg))
    for stage, label_col in stages:
        label_encoder = LabelEncoder()
        y_train_all = label_encoder.fit_transform(train_df[label_col])
        y_test, class_names, unseen = _encode_test_labels(label_encoder, test_df[label_col])
        if unseen:
            extras["unseen_test_labels"][stage] = unseen
            logger.warning(
                "Stage '%s': %d test row(s) carry %d label(s) never seen in training (%s). They stay in the "
                "evaluation as their own classes, which no classifier can predict; AUC uses the other rows only.",
                stage, sum(unseen.values()), len(unseen), ", ".join(f"{k}={v}" for k, v in unseen.items()),
            )

        if len(x_train_all) > MAX_FIT_ROWS:
            idx = np.random.RandomState(cfg["random_seed"]).choice(len(x_train_all), size=MAX_FIT_ROWS, replace=False)
            x_train, y_train = x_train_all[idx], y_train_all[idx]
        else:
            x_train, y_train = x_train_all, y_train_all

        stage_distributions = {"original": _distribution(y_train, label_encoder)}

        for sampling_algo in _sampling_strategies(cfg, stage):
            stage_distributions[sampling_algo] = _resampled_distribution(
                x_train, y_train, sampling_algo, label_encoder, cfg["random_seed"]
            )

            for scaling_algo in _scaling_strategies(cfg):
                for name in _resolve_classifier_list(cfg):
                    step += 1
                    logger.info("Benchmark %d/%d: %s (stage=%s, scaling=%s, sampling=%s) ...",
                                step, total, name, stage, scaling_algo, sampling_algo)
                    try:
                        model, fit_time, best_params = _fit_classifier(
                            name, x_train, y_train, cfg, sampling_algo, scaling_algo
                        )
                    except Exception as e:
                        logger.warning(
                            "Classifier '%s' failed on stage '%s' (scaling=%s, sampling=%s): %s",
                            name, stage, scaling_algo, sampling_algo, e,
                        )
                        continue

                    metrics, infer_time, detail = _evaluate(
                        model, x_test, y_test, class_names, len(label_encoder.classes_), cols
                    )
                    logger.info("Benchmark %d/%d done: %s macro-F1=%.4f (fit %.1fs, predict %.1fs)",
                                step, total, name, metrics.get("f1_macro", float("nan")), fit_time, infer_time)
                    rows.append({
                        "stage": stage, "scaling": scaling_algo, "sampling": sampling_algo, "classifier": name,
                        "train_time_s": round(fit_time, 4), "infer_time_s": round(infer_time, 4),
                        **metrics,
                    })
                    extras[f"{stage}|{scaling_algo}|{sampling_algo}|{name}"] = {"best_params": best_params, **detail}
                    per_class_rows.extend(
                        _per_class_rows(stage, scaling_algo, sampling_algo, name, detail["per_class_report"])
                    )

        extras["class_distributions"][stage] = stage_distributions

    extras["per_class_metrics"] = per_class_rows
    return pd.DataFrame(rows), extras


def _per_class_rows(
    stage: str, scaling_algo: str, sampling_algo: str, classifier: str, per_class_report: dict
) -> list[dict]:
    """Flattens one (stage, scaling, sampling, classifier) combination's
    per_class_report (already computed by _evaluate, just nested inside
    benchmark_details.json) into rows a summary CSV can scan directly,
    without opening the JSON. Skips classification_report's aggregate
    keys ("accuracy", "macro avg", "weighted avg"): those are already
    the f1_macro/f1_weighted columns in benchmark_results.csv.
    """
    return [
        {
            "stage": stage, "scaling": scaling_algo, "sampling": sampling_algo, "classifier": classifier,
            "class": class_name, "precision": stats["precision"], "recall": stats["recall"],
            "f1": stats["f1-score"], "support": stats["support"],
        }
        for class_name, stats in per_class_report.items()
        if class_name not in ("accuracy", "macro avg", "weighted avg")
    ]


def _sampling_strategies(cfg: dict, stage: str) -> list[str]:
    algo = cfg["preprocessing"]["sampling"][stage]
    return algo if isinstance(algo, list) else [algo]


def _scaling_strategies(cfg: dict) -> list[str]:
    scaling = cfg["preprocessing"]["scaling"]
    return scaling if isinstance(scaling, list) else [scaling]


def _distribution(y_encoded: np.ndarray, label_encoder: LabelEncoder) -> dict:
    labels = label_encoder.inverse_transform(y_encoded)
    counts = pd.Series(labels).value_counts()
    return {str(k): int(v) for k, v in counts.items()}


def _resampled_distribution(x_train, y_train, sampling_algo: str, label_encoder: LabelEncoder, seed: int) -> dict:
    """A standalone probe resample purely for reporting, decoupled from
    what each classifier's own pipeline does internally, but deterministic
    (same seed) so it matches what they'll actually see.
    """
    if sampling_algo == "none":
        return _distribution(y_train, label_encoder)
    try:
        _, y_res = SAMPLERS[sampling_algo](seed).fit_resample(x_train, y_train)
    except ValueError as e:
        logger.warning("Could not compute resampled distribution for '%s': %s", sampling_algo, e)
        return {}
    return _distribution(y_res, label_encoder)


def _resolve_classifier_list(cfg: dict) -> list[str]:
    clf_list = cfg["classifiers"]["list"]
    return list(clf_registry.REGISTRY) if clf_list == "all" else clf_list


def _build_pipeline(name: str, cfg: dict, overrides: dict, sampling_algo: str, scaling_algo: str) -> ImbPipeline:
    seed = cfg["random_seed"]
    scaler = SCALERS[scaling_algo]() if scaling_algo != "none" else "passthrough"
    sampler = SAMPLERS[sampling_algo](seed) if sampling_algo != "none" else "passthrough"
    clf = clf_registry.build_estimator(name, overrides, seed=seed)
    return ImbPipeline([("scaler", scaler), ("sampler", sampler), ("clf", clf)])


def _prefix_grid(grid: dict) -> dict:
    return {f"clf__{k}": v for k, v in grid.items()}


def _fit_classifier(name: str, x_train, y_train, cfg: dict, sampling_algo: str, scaling_algo: str):
    classifiers_cfg = cfg["classifiers"]
    spec = clf_registry.REGISTRY[name]
    overrides = classifiers_cfg["hyperparameters"].get(name, {})
    pipe = _build_pipeline(name, cfg, overrides, sampling_algo, scaling_algo)

    best_params = None
    start = time.perf_counter()
    if classifiers_cfg["tuning"] and not spec.no_tune:
        grid = _prefix_grid(classifiers_cfg["search_space"].get(name, spec.default_grid))
        if grid:
            search = GridSearchCV(pipe, grid, cv=TUNING_CV_FOLDS, n_jobs=-1)
            search.fit(x_train, y_train)
            model = search.best_estimator_
            best_params = {k.removeprefix("clf__"): v for k, v in search.best_params_.items()}
        else:
            model = pipe
            model.fit(x_train, y_train)
    else:
        model = pipe
        model.fit(x_train, y_train)

    calibration = classifiers_cfg["calibration"]
    if calibration != "none" and name != "SVM":  # SVM is already CalibratedClassifierCV-wrapped
        method = "sigmoid" if calibration == "platt" else "isotonic"
        model = CalibratedClassifierCV(model, method=method, cv=5)
        model.fit(x_train, y_train)
    fit_time = time.perf_counter() - start

    return model, fit_time, best_params


def _encode_test_labels(label_encoder: LabelEncoder, test_labels: pd.Series) -> tuple[np.ndarray, list[str], dict]:
    """Encodes test labels against the classes seen in training. A test label
    the training split never had (NSL-KDD's KDDTest+ has several attack types
    KDDTrain+ lacks) gets a code after the training classes instead of
    raising, so those rows are scored as the misses they are rather than
    crashing the stage or being dropped, which would overstate every metric.

    Returns (codes, class names in code order, {unseen label: test row count}).
    """
    known = {c: i for i, c in enumerate(label_encoder.classes_)}
    unseen_labels = sorted(set(test_labels.unique()) - set(known), key=str)
    codes = {**known, **{c: len(known) + j for j, c in enumerate(unseen_labels)}}
    y_test = test_labels.map(codes).to_numpy(dtype=int)
    counts = test_labels.value_counts()
    unseen = {str(c): int(counts[c]) for c in unseen_labels}
    class_names = [str(c) for c in label_encoder.classes_] + [str(c) for c in unseen_labels]
    return y_test, class_names, unseen


def _evaluate(
    model, x_test, y_test, class_names: list[str], n_train_classes: int, feature_names: list[str]
) -> tuple[dict, float, dict]:
    """Codes 0..n_train_classes-1 are the training classes; any code past that
    is a test-only class (see _encode_test_labels). Every per-class output is
    built over the full code range, so the confusion matrix and report keep
    one row per class even when a class is absent from y_test and y_pred.
    """
    start = time.perf_counter()
    y_pred = model.predict(x_test)
    infer_time = time.perf_counter() - start

    metrics = {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "f1_weighted": float(f1_score(y_test, y_pred, average="weighted", zero_division=0)),
        # Weighted averages every class by its support, so a majority class can carry
        # a poor result on rare classes. Macro treats every class equally, surfacing
        # exactly that collapse on the imbalanced label distributions typical here.
        "f1_macro": float(f1_score(y_test, y_pred, average="macro", zero_division=0)),
    }
    try:
        # AUC needs a probability column per true class, and the model has none
        # for a class it never trained on, so it covers the known-class rows.
        known = y_test < n_train_classes
        proba = _full_proba(model, x_test[known], n_train_classes)
        y_known = y_test[known]
        if n_train_classes == 2:
            metrics["auc"] = float(roc_auc_score(y_known, proba[:, 1]))
        else:
            metrics["auc"] = _ovr_weighted_auc(y_known, proba)
    except (AttributeError, ValueError) as e:
        logger.warning("Could not compute AUC: %s", e)
        metrics["auc"] = None

    labels = np.arange(len(class_names))
    detail = {
        "confusion_matrix": confusion_matrix(y_test, y_pred, labels=labels).tolist(),
        "confusion_matrix_labels": class_names,
        "per_class_report": classification_report(
            y_test, y_pred, labels=labels, target_names=class_names, output_dict=True, zero_division=0
        ),
        "feature_importance": _feature_importance(model, feature_names),
    }
    return metrics, infer_time, detail


def _ovr_weighted_auc(y: np.ndarray, proba: np.ndarray) -> float:
    """One-vs-rest AUC per class present in y, on that class's own probability
    column, averaged by support: what roc_auc_score(multi_class="ovr",
    average="weighted") returns when every class is present, but still
    defined when a training class has no test rows (sklearn raises then).
    """
    present, support = np.unique(y, return_counts=True)
    if len(present) < 2:
        raise ValueError("only one class present in the test labels")
    aucs = [roc_auc_score(y == c, proba[:, c]) for c in present]
    return float(np.average(aucs, weights=support))


def _full_proba(model, x, n_classes: int) -> np.ndarray:
    """predict_proba widened to one column per training class: a class the
    fit sample happened to miss (MAX_FIT_ROWS subsampling, a resampler)
    has no column in model.classes_, which would misalign the others.
    """
    proba = model.predict_proba(x)
    full = np.zeros((proba.shape[0], n_classes))
    full[:, np.asarray(model.classes_, dtype=int)] = proba
    return full


def _feature_importance(model, feature_names: list[str]) -> dict | None:
    """Best-effort: pokes into whatever wrapping (Pipeline, CalibratedClassifierCV)
    sits around the actual classifier. Returns None rather than raising if the
    wrapping doesn't match what's expected, this is a nice-to-have, not
    something that should ever crash a benchmark run.
    """
    try:
        clf = model
        if isinstance(clf, CalibratedClassifierCV):
            clf = clf.calibrated_classifiers_[0].estimator
        if hasattr(clf, "named_steps"):
            clf = clf.named_steps.get("clf", clf)
        if hasattr(clf, "feature_importances_"):
            values = clf.feature_importances_
        elif hasattr(clf, "coef_"):
            coef = clf.coef_
            values = coef[0] if coef.ndim > 1 else coef
        else:
            return None
        return {name: float(v) for name, v in zip(feature_names, values, strict=True)}
    except Exception:
        return None
