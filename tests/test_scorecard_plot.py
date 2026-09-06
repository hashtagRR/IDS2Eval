from ids2eval import scorecard, scorecard_plot


def _finding(check, status, summary="a summary", details=None):
    return {"check": check, "status": status, "summary": summary, "details": details or {}}


def _fingerprint():
    return {
        "train_rows": 100, "test_rows": 20,
        "train_content_hash": "abc123", "test_content_hash": "def456",
    }


def test_render_writes_valid_pdf_and_png_with_minimal_findings(base_cfg, tmp_path):
    findings = [_finding("dedup_check", "ok"), _finding("data_integrity_check", "ok")]
    sc = scorecard.build_scorecard(findings, "after", base_cfg, _fingerprint())
    pdf_path, png_path = tmp_path / "scorecard.pdf", tmp_path / "scorecard.png"

    scorecard_plot.render(sc, findings, pdf_path, png_path)

    assert pdf_path.read_bytes().startswith(b"%PDF")
    assert png_path.read_bytes().startswith(b"\x89PNG")
    assert pdf_path.stat().st_size > 1000
    assert png_path.stat().st_size > 1000


def test_render_adds_conditional_panels_when_those_checks_ran(base_cfg, tmp_path):
    findings = [
        _finding("dedup_check", "ok"),
        _finding(
            "class_distribution_report", "warning",
            details={
                "train": {"counts": {"Benign": 700, "Attack": 300}},
                "test": {"counts": {"Benign": 175, "Attack": 75}},
            },
        ),
        _finding(
            "leakage_screen", "flag", "leak found",
            details={"top_features": {"Leaky": 0.9, "F1": 0.05, "F2": 0.03}},
        ),
    ]
    sc = scorecard.build_scorecard(findings, "after", base_cfg, _fingerprint())
    pdf_path, png_path = tmp_path / "scorecard.pdf", tmp_path / "scorecard.png"

    scorecard_plot.render(sc, findings, pdf_path, png_path)

    assert pdf_path.exists() and png_path.exists()
    # A figure with two extra panels renders a taller PDF than the minimal case.
    minimal_pdf = tmp_path / "minimal.pdf"
    scorecard_plot.render(sc, [_finding("dedup_check", "ok")], minimal_pdf, tmp_path / "minimal.png")
    assert pdf_path.stat().st_size != minimal_pdf.stat().st_size


def test_render_handles_test_only_class_present(base_cfg, tmp_path):
    # A class that only appears in test, not train - must not crash or drop it.
    findings = [
        _finding(
            "class_distribution_report", "ok",
            details={
                "train": {"counts": {"Benign": 100}},
                "test": {"counts": {"Benign": 25, "RareAttack": 1}},
            },
        ),
    ]
    sc = scorecard.build_scorecard(findings, "after", base_cfg, _fingerprint())
    scorecard_plot.render(sc, findings, tmp_path / "scorecard.pdf", tmp_path / "scorecard.png")
    assert (tmp_path / "scorecard.pdf").exists()
