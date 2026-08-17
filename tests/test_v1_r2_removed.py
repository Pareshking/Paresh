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
    forbidden = ("R²", "R2", "r2", "Sharpe ×")
    for path in runtime_files:
        text = path.read_text()
        assert not any(token in text for token in forbidden), f"R2 residue in {path}"

