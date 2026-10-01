from pathlib import Path


def test_track_record_updater_reports_strategy_and_benchmark_parity():
    source = Path("scripts/update_track_record.py").read_text(encoding="utf-8")

    assert "from src.engine.parity_audit import compare_monthly_ledger" in source
    assert 'ledger, result["equity_curve"], result["benchmark"]' in source
    assert "frozen-ledger parity:" in source
    assert "stored value stands" in source
    assert "missing recomputed data" in source


def test_parity_diagnostics_do_not_block_append_only_ledger_updates():
    source = Path("scripts/update_track_record.py").read_text(encoding="utf-8")
    audit_section = source.split("# Read-only comparison of both frozen return series.", 1)[1]
    assert "if not parity" not in audit_section
    assert 'parity["passed"]' not in audit_section
    assert "ledger, added, skipped = finalize_months(" in audit_section
