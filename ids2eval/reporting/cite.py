"""Prints a citation block for a completed run's scorecard.

Everything needed already lives in scorecard.json (dataset name, tool
version and commit, schema version, verdict, generated timestamp, and
the dataset_fingerprint content hashes): this reads that one file and
reformats it, it computes nothing new.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from . import scorecard as _scorecard


def _bibtex_key(dataset_name: str, train_content_hash: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", dataset_name.lower()).strip("_")
    return f"ids2eval_{slug}_{train_content_hash[:8]}"


def load_scorecard(run_dir: str | Path) -> dict:
    path = Path(run_dir)
    if path.is_dir():
        path = path / "scorecard.json"
    if not path.exists():
        raise FileNotFoundError(f"No scorecard.json found at or under {run_dir}")
    return _scorecard.upgrade(json.loads(path.read_text()))


def citation_bibtex(scorecard: dict) -> str:
    fp = scorecard["dataset_fingerprint"]
    year = scorecard["generated_at"][:4]
    key = _bibtex_key(scorecard["dataset_name"], fp["train_content_hash"])
    commit = scorecard["ids2eval_git_commit"]
    verdict = scorecard["overall_status"].replace("_", " ")

    # commit is only known for a git checkout (version_info.py shells out to
    # git); a pip install from a downloaded zip - no .git directory at all -
    # has no commit to report, and "commit unknown" reads worse in a
    # citation than just not mentioning a commit at all.
    howpublished = f"IDS2Eval v{scorecard['ids2eval_version']} (scorecard schema {scorecard['scorecard_schema_version']})"
    if commit:
        howpublished += f", commit {commit}"

    fields = {
        "title": f"IDS2Eval scorecard for {scorecard['dataset_name']}",
        "howpublished": howpublished,
        "note": (
            f"{verdict}; train content hash {fp['train_content_hash']}; "
            f"test content hash {fp['test_content_hash']}; generated {scorecard['generated_at']}"
        ),
        "year": year,
    }
    body = ",\n".join(f"  {name} = {{{value}}}" for name, value in fields.items())
    return f"@misc{{{key},\n{body}\n}}"
