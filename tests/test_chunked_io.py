import numpy as np
import pandas as pd

from ids2eval.data.chunked_io import iter_chunks, load_file, load_files_combined, reservoir_sample


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


def _sample_df(n=10):
    return pd.DataFrame({"F1": np.arange(n, dtype="float64"), "Label": (["A", "B"] * n)[:n]})


def test_iter_chunks_reads_plain_csv(tmp_path):
    df = _sample_df()
    path = tmp_path / "data.csv"
    df.to_csv(path, index=False)
    result = pd.concat(list(iter_chunks([str(path)], chunk_size=None)), ignore_index=True)
    pd.testing.assert_frame_equal(result, df.astype({"F1": "float32"}))


def test_iter_chunks_reads_chunked_csv(tmp_path):
    df = _sample_df(20)
    path = tmp_path / "data.csv"
    df.to_csv(path, index=False)
    result = pd.concat(list(iter_chunks([str(path)], chunk_size=7)), ignore_index=True)
    assert len(result) == 20
    assert result["Label"].tolist() == df["Label"].tolist()


def test_iter_chunks_reads_a_whole_parquet_file(tmp_path):
    df = _sample_df()
    path = tmp_path / "data.parquet"
    df.to_parquet(path, index=False)
    result = pd.concat(list(iter_chunks([str(path)], chunk_size=None)), ignore_index=True)
    assert result["Label"].tolist() == df["Label"].tolist()
    assert len(result) == len(df)


def test_iter_chunks_reads_a_chunked_parquet_file(tmp_path):
    df = _sample_df(20)
    path = tmp_path / "data.parquet"
    df.to_parquet(path, index=False)
    result = pd.concat(list(iter_chunks([str(path)], chunk_size=7)), ignore_index=True)
    assert len(result) == 20
    assert result["Label"].tolist() == df["Label"].tolist()


def test_load_file_downcasts_parquet_floats_to_float32(tmp_path):
    df = _sample_df()
    path = tmp_path / "data.parquet"
    df.to_parquet(path, index=False)
    result = load_file(str(path), chunk_size=None, max_rows=None)
    assert result["F1"].dtype == np.float32


def test_load_files_combined_mixes_csv_and_parquet(tmp_path):
    df1, df2 = _sample_df(5), _sample_df(5)
    csv_path, parquet_path = tmp_path / "a.csv", tmp_path / "b.parquet"
    df1.to_csv(csv_path, index=False)
    df2.to_parquet(parquet_path, index=False)
    result = load_files_combined([str(csv_path), str(parquet_path)], chunk_size=None, max_rows=None)
    assert len(result) == 10
