"""Regression contracts for stateful backtest history boundaries."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKTESTER = ROOT / "src/engine/backtester.py"


def test_stateful_rebalance_blotter_is_built_after_inception_filter():
    source = BACKTESTER.read_text(encoding="utf-8")
    filter_pos = source.index("if stateful_history:")
    history_floor_pos = source.index("history_floor = (", filter_pos)
    blotter_pos = source.index("tradebook_df = pd.DataFrame(trade_records)", filter_pos)

    assert filter_pos < history_floor_pos < blotter_pos
    assert 'pd.Timestamp(history_start).normalize()' in source
    assert "Portfolio Rebalances" in source


def test_stateful_trade_records_fall_back_to_window_start_without_history_start():
    source = BACKTESTER.read_text(encoding="utf-8")
    anchor = source.index("history_floor = (")
    block = source[anchor:source.index("trade_records = [", anchor)]

    assert "if history_start is not None" in block
    assert "else window_start" in block
