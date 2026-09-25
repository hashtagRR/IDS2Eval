# Example: CICDDoS2019 scorecard

A real IDS<sup>2</sup>Eval audit of [CICDDoS2019](https://www.unb.ca/cic/datasets/ddos-2019.html),
using [dhoogla's cleaned per-attack-type mirror](https://www.kaggle.com/datasets/dhoogla/cicddos2019)
(a curated CSV/parquet subset of the official release, not a sample of the full
multi-GB pcap-derived data). The training day's 8 attack-type files (125,170 rows)
and testing day's 12 attack-type files (306,201 rows) are concatenated back into
one train set and one test set, matching how the dataset was actually collected -
two separate days, run 2 months apart. Produced with `config.yaml` in this folder;
open [SCORECARD.html](SCORECARD.html) in a browser for the full result, or read
[SCORECARD.md](SCORECARD.md).

**Result: passed with warnings** - 8 ok, 4 warnings, 0 flags after dedup, across 12
checks.

What it found:

- **`label_conflict_check` flags 5,623 feature vectors (13,758 rows, 3.19%) mapping
  to more than one label before dedup**, 4,853 of them spanning train and test;
  after dedup, zero conflicts remain, so this one was duplication masquerading as
  label conflict, not independent ground-truth contradiction.
- **`dedup_check` finds 4,083 train duplicates (3.26%) and 6,763 test rows (2.21%)
  that exactly match a train row's features** - scores on those rows measure
  memorization of the training day's flows, not detection of the testing day's.
- **`known_issue_lookup` surfaces the dataset's own two-day design**: the testing
  day includes DDoS types (DNS, NTP, SNMP, TFTP, WebDDoS reflection attacks) that
  never appear in the training day, and the same attack type is named differently
  across the two days ('UDPLag' in training vs. 'UDP-lag' in testing, 'MSSQL' vs.
  'DrDoS_MSSQL'). Neither is a bug in this mirror; both are documented properties
  of how CICDDoS2019 was originally collected, and both mean a classifier's
  raw train-to-test accuracy on this dataset reflects those two effects as much as
  detection quality.
- **`one_rule_check` finds `Avg Packet Size <= 7.625` alone reaches only 11.5% test
  accuracy** despite 68.1% train accuracy - a large train/test gap consistent with
  the label-naming mismatch above, not necessarily a sign the rule doesn't
  generalize on the underlying traffic.
- **`data_integrity_check` finds 12 constant features** (`Bwd PSH Flags`,
  `Fwd URG Flags`, `Bwd URG Flags`, `FIN Flag Count`, `PSH Flag Count`,
  `ECE Flag Count`, and all six `*Bulk*` features) - present in this mirror across
  both days, so not an artifact of concatenating them.
- **`schema_fingerprint_check` matches CICFlowMeter's signature**: the same
  extractor-version caveat that applies to the CIC-IDS2017/2018 examples applies
  here too.
- **Imbalance of 1,312:1** after dedup, with `NetBIOS`, `Portmap`, and `UDPLag`
  each under 1% of train.

How the data was obtained: `dhoogla/cicddos2019` from Kaggle, downloaded
2026-09-25 via the Kaggle API's public dataset-download endpoint (no
authentication required for this dataset). This mirror already deduplicates and
downsamples the official multi-GB release per attack type; the row counts here
are the mirror's, not the original collection's.

Run on a 4-vCPU / 7.8GB VM: 86 seconds, audit only (`--skip-benchmark`). Produced
with IDS2Eval at commit d9d444d.

Files: `config.yaml` (input), `audit_report_before.json` /
`audit_report_after.json` (full findings), `dataset_fingerprint.json` /
`environment.json` (provenance), `SCORECARD.html` / `scorecard.json` /
`SCORECARD.md` (the citable rollup, see
[guide/checks.md](../../guide/checks.md#the-scorecard) for the format).
No `scorecard.pdf`/`.png`: matching the other four examples, this one ships the
HTML scorecard only, the same thing the dashboard shows.
