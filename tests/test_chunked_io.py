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


def _multi_member_zip(tmp_path, members: dict):
    import zipfile
    path = tmp_path / "archive.zip"
    with zipfile.ZipFile(path, "w") as zf:
        for name, df in members.items():
            if name.endswith(".parquet"):
                buf_path = tmp_path / f"_staging_{name}"
                df.to_parquet(buf_path, index=False)
                zf.write(buf_path, arcname=name)
            else:
                zf.writestr(name, df.to_csv(index=False))
    return path


def test_iter_chunks_reads_one_named_csv_member_from_a_multi_member_zip(tmp_path):
    train, test = _sample_df(6), _sample_df(4)
    # Mirrors a real official dataset zip: a train/test pair plus files that
    # aren't training data at all (a feature-name reference, an event log).
    archive = _multi_member_zip(tmp_path, {
        "features.csv": pd.DataFrame({"name": ["F1", "Label"]}),
        "training-set.csv": train,
        "testing-set.csv": test,
        "list_events.csv": pd.DataFrame({"event": ["x"]}),
    })
    result = pd.concat(list(iter_chunks([f"{archive}::training-set.csv"], chunk_size=None)), ignore_index=True)
    assert len(result) == 6
    assert result["Label"].tolist() == train["Label"].tolist()


def test_iter_chunks_reads_a_chunked_csv_member_from_a_zip(tmp_path):
    df = _sample_df(20)
    archive = _multi_member_zip(tmp_path, {"data.csv": df})
    result = pd.concat(list(iter_chunks([f"{archive}::data.csv"], chunk_size=7)), ignore_index=True)
    assert len(result) == 20


def test_iter_chunks_reads_a_parquet_member_from_a_zip(tmp_path):
    df = _sample_df(6)
    archive = _multi_member_zip(tmp_path, {"data.parquet": df})
    result = pd.concat(list(iter_chunks([f"{archive}::data.parquet"], chunk_size=None)), ignore_index=True)
    assert len(result) == 6
    assert result["Label"].tolist() == df["Label"].tolist()


def test_load_files_combined_reads_two_members_of_the_same_zip(tmp_path):
    train, test = _sample_df(5), _sample_df(5)
    archive = _multi_member_zip(tmp_path, {"train.csv": train, "test.csv": test})
    result = load_files_combined(
        [f"{archive}::train.csv", f"{archive}::test.csv"], chunk_size=None, max_rows=None
    )
    assert len(result) == 10


def test_iter_chunks_reads_a_headerless_csv_with_column_names(tmp_path):
    df = _sample_df(6)
    path = tmp_path / "headerless.csv"
    df.to_csv(path, index=False, header=False)  # row 0 is data, not a header
    result = pd.concat(
        list(iter_chunks([str(path)], chunk_size=None, column_names=["F1", "Label"])), ignore_index=True
    )
    assert list(result.columns) == ["F1", "Label"]
    assert len(result) == 6
    assert result["Label"].tolist() == df["Label"].tolist()


def test_iter_chunks_reads_a_chunked_headerless_csv_with_column_names(tmp_path):
    df = _sample_df(20)
    path = tmp_path / "headerless.csv"
    df.to_csv(path, index=False, header=False)
    result = pd.concat(
        list(iter_chunks([str(path)], chunk_size=7, column_names=["F1", "Label"])), ignore_index=True
    )
    assert len(result) == 20
    assert result["Label"].tolist() == df["Label"].tolist()


def test_load_file_treats_row_zero_as_data_when_column_names_is_set(tmp_path):
    df = _sample_df(5)
    path = tmp_path / "headerless.csv"
    df.to_csv(path, index=False, header=False)
    result = load_file(str(path), chunk_size=None, max_rows=None, column_names=["F1", "Label"])
    assert len(result) == 5  # not 4: row 0 is a real data row, not consumed as a header


def test_iter_chunks_ignores_column_names_for_parquet(tmp_path, caplog):
    df = _sample_df(4)
    path = tmp_path / "data.parquet"
    df.to_parquet(path, index=False)
    result = pd.concat(
        list(iter_chunks([str(path)], chunk_size=None, column_names=["X", "Y"])), ignore_index=True
    )
    assert list(result.columns) == ["F1", "Label"]  # Parquet's own names win, not column_names
    assert "ignoring dataset.column_names" in caplog.text


def test_headerless_csv_member_from_a_zip_with_column_names(tmp_path):
    df = _sample_df(6)
    archive = _multi_member_zip(tmp_path, {"headerless.csv": df.reset_index(drop=True)})
    # _multi_member_zip writes df.to_csv(index=False) with a header; overwrite that
    # member with a headerless version to match this test's real scenario.
    import zipfile
    with zipfile.ZipFile(archive, "a") as zf:
        zf.writestr("no_header.csv", df.to_csv(index=False, header=False))
    result = pd.concat(list(iter_chunks(
        [f"{archive}::no_header.csv"], chunk_size=None, column_names=["F1", "Label"]
    )), ignore_index=True)
    assert list(result.columns) == ["F1", "Label"]
    assert len(result) == 6
