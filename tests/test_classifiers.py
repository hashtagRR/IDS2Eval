import pytest

from ids2eval.classifiers import REGISTRY, build_estimator


def test_registry_has_all_14_classifiers():
    expected = {
        "RandomForest", "XGBoost", "DecisionTree", "NaiveBayes", "LogisticRegression",
        "KNN", "SVM", "LDA", "Stacking", "Voting", "ExtraTrees",
        "HistGradientBoosting", "AdaBoost", "MLP",
    }
    assert set(REGISTRY) == expected


def test_no_tune_classifiers_flagged_correctly():
    for name in ("NaiveBayes", "Stacking", "Voting"):
        assert REGISTRY[name].no_tune is True
    assert REGISTRY["RandomForest"].no_tune is False


@pytest.mark.parametrize("name", list(REGISTRY))
def test_build_estimator_fits_and_predicts(name):
    from sklearn.datasets import make_classification
    x, y = make_classification(n_samples=60, n_features=5, n_informative=3, random_state=0)
    model = build_estimator(name)
    model.fit(x, y)
    preds = model.predict(x)
    assert len(preds) == len(y)


def test_build_estimator_applies_overrides():
    model = build_estimator("RandomForest", {"n_estimators": 7})
    assert model.n_estimators == 7
