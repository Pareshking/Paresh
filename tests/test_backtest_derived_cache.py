"""S220: the page's figures, trade table and trade log are kept once per run, keyed on every input."""
import pandas as pd

from src.ui.views import backtest_view as bv


def _h(**kw):
    h = {"close_fingerprint": "abc", "traded_value": None, "name": "Nifty 500", "months": 120,
         "start": pd.Period("2010-01", "M"), "floor": 0.0, "close": pd.DataFrame(index=pd.date_range("2020-01-01", periods=5))}
    h.update(kw)
    return h


def test_key_changes_with_every_input():
    bench = pd.Series([1.0, 2.0], index=pd.date_range("2020-01-01", periods=2))
    s = {"top_n": 20, "rebal_freq": "M", "weights": (0.1, 0.3, 0.3, 0.2, 0.1)}
    base = bv._derived_key(s, _h(), bench, 0.1, 0.3, True)
    assert base == bv._derived_key(dict(reversed(list(s.items()))), _h(), bench, 0.1, 0.3, True)
    others = [bv._derived_key({**s, "top_n": 30}, _h(), bench, 0.1, 0.3, True),
              bv._derived_key(s, _h(close_fingerprint="xyz"), bench, 0.1, 0.3, True),
              bv._derived_key(s, _h(floor=5.0), bench, 0.1, 0.3, True),
              bv._derived_key(s, _h(), bench.iloc[:1], 0.1, 0.3, True),
              bv._derived_key(s, _h(), bench, 0.2, 0.3, True),
              bv._derived_key(s, _h(), bench, 0.1, 0.3, False)]
    assert base not in others and len(set(others)) == len(others)


def test_render_reads_the_figures_through_the_cache():
    import inspect
    src = inspect.getsource(bv.render_backtest_view)
    assert "_derived(" in src and "gather(" not in src and "history_spec(" not in src
