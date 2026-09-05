import copy

import numpy as np
import pandas as pd
import pytest

from ids2eval.config import DEFAULTS


@pytest.fixture
def base_cfg():
    cfg = copy.deepcopy(DEFAULTS)
    cfg["dataset"]["name"] = "test-dataset"
    cfg["schema"]["label_column"] = "Label"
    return cfg


@pytest.fixture
def synth_data():
    """A small, fully-controlled synthetic dataset with known properties:
    - LeakyFeature perfectly separates the label (for leakage_screen)
    - SrcIP has low cardinality and is predictive (for identity checks)
    - 10 exact duplicate rows (for dedup_check)
    - a rare class at <1% share (for class_distribution_report)
    """
    rng = np.random.RandomState(0)
    n = 1000
    label = rng.choice(["Benign", "Attack", "Rare"], size=n, p=[0.6, 0.39, 0.01])
    leaky = np.where(label == "Benign", 0.0, 100.0)
    src_ip = np.where(label == "Benign", "10.0.0.1", "10.0.0.2")
    f1 = rng.normal(0, 1, n)

    df = pd.DataFrame({
        "SrcIP": src_ip,
        "LeakyFeature": leaky,
        "Feature1": f1,
        "Label": label,
    })
    dupes = df.iloc[:10].copy()
    df = pd.concat([df, dupes], ignore_index=True)
    return df


@pytest.fixture
def synth_train_test(synth_data):
    from sklearn.model_selection import train_test_split
    train, test = train_test_split(synth_data, test_size=0.3, random_state=0, stratify=synth_data["Label"])
    return train.reset_index(drop=True), test.reset_index(drop=True)
