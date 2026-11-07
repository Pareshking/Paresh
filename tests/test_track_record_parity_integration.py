from pathlib import Path


def test_track_record_updater_reports_strategy_and_benchmark_parity():
    source = Path("scripts/update_track_record.py").read_text(encoding="utf-8")

    assert "from src.engine.parity_audit import compare_monthly_ledger" in source
    assert 'ledger, result["equity_curve"], result["benchmark"]' in source
    assert "frozen-ledger parity:" in source
    assert "stored value stands" in source
    assert "missing recomputed data" in source


def test_a_red_parity_refuses_the_freeze_before_anything_is_written():
    # S92 (owner, 7 Nov 2026): parity was diagnostic only until October 2026 was
    # struck on a store carrying BSE closes. Now a red comparison refuses a new
    # month, before save_ledger, except in a deliberate --force rebuild.
    source = Path("scripts/update_track_record.py").read_text(encoding="utf-8")
    audit_section = source.split("# Read-only comparison of both frozen return series.", 1)[1]
    assert "ledger, added, skipped = finalize_months(" in audit_section
    guard = audit_section.index("refusal = freeze_refusal(parity)")
    assert guard < audit_section.index("save_ledger(ledger, ledger_file)")
    assert guard < audit_section.index('if args.dry_run:')
    assert "if refusal and added and not args.force:" in audit_section
