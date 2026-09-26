# Contributing a known issue or extractor fingerprint

Two curated tables in this project grow entirely from published,
verifiable findings, not from running the audit and guessing: the
per-dataset known-issue lookup and the per-extractor schema fingerprint.
Both take the same kind of contribution and the same bar for inclusion.

## Adding a known issue

`ids2eval/audit/known_issues.py`'s `KNOWN_ISSUES` dict holds a list of
entries per dataset, matched by a case-insensitive substring against
`dataset.name`. Each entry is:

```python
{
    "issue": "A specific, checkable claim about this dataset: what's "
             "wrong, where, and how big the effect is (a percentage, a "
             "row count, a named file or class), not a vague caveat.",
    "citation": "Author et al. year, venue",
}
```

Requirements for a new entry:

- **A real citation.** A paper, a technical report, or (for a fact this
  project measured itself rather than found in the literature) the
  phrase `"Independently verified in this project's own audit
  methodology"`, matching the existing UNSW-NB15 and CICDDoS2019
  entries that use it. Never a claim with no source at all.
- **A specific claim, not a general caution.** "This dataset has some
  labeling problems" is not an entry. "The 2018-02-23 day-file's
  Brute-Force-Web/Brute-Force-XSS rows are approximately 41%
  mislabeled" is, because a reader can check it against the source.
- **Add a regression test** in `tests/test_audit.py`, next to the
  existing `test_known_issue_lookup_*` tests, asserting the dataset
  name resolves to a `warning` status and that the citation text
  appears in the summary.

Judgment calls belong in the pull request description, not silently
resolved: whether an older, largely superseded dataset (KDD99 being the
obvious case, still widely cited but generally considered deprecated)
is worth an entry at all, or whether two papers reporting different
numbers for the same problem should both be listed.

## Adding an extractor fingerprint

`ids2eval/audit/schema_fingerprint.py`'s `KNOWN_EXTRACTORS` dict holds
one entry per flow-export tool (currently only CICFlowMeter), matched
by how many of a fixed set of distinctive column names are present:

```python
"ToolName": {
    "signature_columns": {"Column A", "Column B", ...},
    "match_threshold": 0.6,
    "warning": "What's documented wrong with this tool's output, and "
               "the citation for it.",
},
```

Requirements are the same as a known issue: a real citation describing
a specific, documented calculation bug or version-dependent quirk in
the tool itself, not "this extractor might have issues." Pick
`signature_columns` distinctive enough that a genuinely different tool
producing superficially similar column names (duration, byte counts,
packet counts are common across every flow exporter) won't cross the
match threshold; a handful of a tool's more unusual, specifically-named
columns works better than trying to require most of its full schema.
