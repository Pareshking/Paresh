from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_r2_removed_from_runtime_v1_files():
    runtime_files = [
        ROOT / "src/engine/momentum.py",
        ROOT / "src/engine/calendar_momentum.py",
        ROOT / "src/engine/backtester.py",
        ROOT / "src/ui/views/ranking_view.py",
        ROOT / "src/ui/views/backtest_view.py",
    ]
    # Do not reject implementation identifiers such as cs_r2; this test is
    # specifically about stale R² methodology claims in runtime text.
    forbidden = ("R²", "R^2", "R2", "Sharpe ×")
    for path in runtime_files:
        text = path.read_text()
        assert not any(token in text for token in forbidden), f"R2 methodology residue in {path}"
