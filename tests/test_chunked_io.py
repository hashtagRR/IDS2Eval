import numpy as np
import pandas as pd

from ids2eval.chunked_io import reservoir_sample


def _chunks(n, chunk_size):
    for start in range(0, n, chunk_size):
        end = min(start + chunk_size, n)
        yield pd.DataFrame({"id": np.arange(start, end), "val": np.arange(start, end, dtype="float64")})


def test_reservoir_sample_exact_row_count():
    sample, n_seen = reservoir_sample(_chunks(10_000, 333), max_rows=500, seed=0)
    assert n_seen == 10_000
    assert len(sample) == 500


def test_reservoir_sample_no_duplicates():
    sample, _ = reservoir_sample(_chunks(10_000, 333), max_rows=500, seed=0)
    assert sample["id"].nunique() == 500


def test_reservoir_sample_smaller_than_max_rows_keeps_everything():
    sample, n_seen = reservoir_sample(_chunks(300, 50), max_rows=1000, seed=0)
    assert n_seen == 300
    assert len(sample) == 300
    assert set(sample["id"]) == set(range(300))


def test_reservoir_sample_invariant_to_chunk_size():
    results = [reservoir_sample(_chunks(20_000, cs), max_rows=200, seed=0)[0]["id"].tolist()
               for cs in (17, 500, 5000)]
    assert results[0] == results[1] == results[2]


def test_reservoir_sample_roughly_uniform():
    n = 100_000
    sample, _ = reservoir_sample(_chunks(n, 1000), max_rows=2000, seed=1)
    ids = sample["id"].to_numpy()
    # loose sanity bound, not a strict statistical test: with a true uniform
    # sample the mean should land well within a few standard errors of n/2
    expected_mean = (n - 1) / 2
    stderr = (n / np.sqrt(12)) / np.sqrt(len(ids))
    assert abs(ids.mean() - expected_mean) < 5 * stderr
