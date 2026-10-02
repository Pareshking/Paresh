"""The long 2010+ backtest's data: index timelines (Nifty 100) and the long NSE price file."""
import pandas as pd
import pytest

from scripts import build_nse_long_prices as long
from src.engine import index_universe as iu
from src.engine.membership import members_on

FULL = {
    "schema_version": 2,
    "baseline": {"date": "2021-10-29", "symbols": ["AAA", "BBB", "CCC", "DDD"]},
    "changes": [],
    "aliases": {"OLDB": {"new_symbol": "BBB", "effective": "2015-06-01"}},
    "indices": {
        "nifty_50": {"baseline": {"date": "2010-01-01", "symbols": ["AAA", "OLDB"]},
                     "changes": [{"date": "2014-03-28", "added": ["CCC"], "removed": ["AAA"]}]},
        "nifty_next_50": {"baseline": {"date": "2010-01-01", "symbols": ["CCC", "DDD"]},
                          "changes": [{"date": "2014-03-28", "added": ["AAA"], "removed": ["CCC"]}]},
        "nifty_midcap_150": {"baseline": {"date": "2016-04-01", "symbols": ["EEE"]}, "changes": []},
        "nifty_total_market": {"baseline": {"date": "2021-10-29", "symbols": ["AAA"]}, "changes": []},
    },
}


def test_nifty_100_is_nifty_50_plus_next_50_on_every_date():
    h = iu.index_history("nifty_100", FULL)
    # Built on current tickers (OLDB is filed as BBB), as the backtester asks.
    assert members_on(h, "2012-01-02", canonical=True) == {"AAA", "BBB", "CCC", "DDD"}
    # A stock moving from one half to the other on the same day stays in the 100.
    assert members_on(h, "2014-03-28", canonical=True) == {"AAA", "BBB", "CCC", "DDD"}
    assert members_on(h, "2009-12-31") is None


def test_an_index_starts_at_its_own_first_whole_month():
    assert iu.first_month(iu.index_history("nifty_50", FULL)) == pd.Period("2010-01", "M")
    assert iu.first_month(iu.index_history("nifty_midcap_150", FULL)) == pd.Period("2016-04", "M")
    # Total Market's list begins 29 Oct 2021: its first whole month is November.
    assert iu.first_month(iu.index_history("nifty_total_market", FULL)) == pd.Period("2021-11", "M")
    assert iu.index_history("nifty_microcap_250", FULL) is None


def test_ever_members_covers_every_index_and_current_tickers():
    assert iu.all_ever_members(FULL) == {"AAA", "BBB", "CCC", "DDD", "EEE", "OLDB"}


DAYS = list(pd.bdate_range("2010-01-04", "2010-02-26"))


def _prices():
    """AAA splits 1:5 on 18 Jan; OLDX trades until 29 Jan, then as NEWX."""
    rows = []
    for s in ("AAA", "OLDX", "NEWX", "ZZZ"):
        last = 100.0
        for d in DAYS:
            if s == "OLDX" and d > pd.Timestamp("2010-01-29"):
                continue
            if s == "NEWX" and d <= pd.Timestamp("2010-01-29"):
                continue
            close = last * 1.01
            if s == "AAA" and d == pd.Timestamp("2010-01-18"):
                close = last * 0.2
            if s == "NEWX" and d == pd.Timestamp("2010-02-01"):
                close = 100.0 * 1.01 ** 19        # continues OLDX's level
            rows.append({"date": d, "mkt": "N", "series": "EQ", "symbol": s, "close": close,
                         "prev_close": last, "high": close, "low": close,
                         "volume": 1000.0, "value": close * 1000.0})
            last = close
    return pd.DataFrame(rows)


SPLIT = pd.DataFrame([{"symbol": "AAA", "ex_date": pd.Timestamp("2010-01-18"), "kind": "split",
                       "price_factor": 0.2, "purpose": "FACE VALUE SPLIT FROM RS 10 TO RS 2"}])
RENAMES = {"OLDX": {"new_symbol": "NEWX"}}


def test_the_long_file_adjusts_splits_joins_renames_and_keeps_traded_value():
    close, value, report = long.build(_prices(), SPLIT, {"renames": RENAMES}, RENAMES, ["AAA", "NEWX"])
    assert list(close.columns) == ["AAA", "NEWX"]
    # The split is folded back: the 80% fall on 18 Jan is gone, the 1% days stay.
    aaa = close["AAA"]
    assert abs(aaa.loc["2010-01-18"] / aaa.loc["2010-01-15"] - 1.0) < 1e-4
    assert abs(aaa.loc["2010-01-15"] / aaa.loc["2010-01-14"] - 1.01) < 1e-4
    # One series under today's ticker, from the first session.
    assert close["NEWX"].first_valid_index() == DAYS[0]
    assert close["NEWX"].notna().all()
    # Traded value is rupees traded / 1e7, not adjusted for the split, joined like the closes.
    assert abs(value.loc["2010-01-04", "AAA"] - 101.0 * 1000 / 1e7) < 1e-9
    assert value["NEWX"].notna().all()
    assert report["value_over_close_x_volume_by_year"] == {2010: 1.0}


def test_a_refused_rename_is_not_joined_for_traded_value_either():
    renames = {"OLDX": {"new_symbol": "NEWX"}}
    refused = ["OLDX->NEWX: 30 days between the series"]
    assert long.joined_renames(renames, refused) == {}
    assert long.joined_renames(renames, []) == {"OLDX": {"new_symbol": "NEWX"}}


def test_the_raw_read_includes_the_old_tickers_of_kept_names(monkeypatch):
    monkeypatch.setattr(long, "all_ever_members", lambda: {"NEWX"})
    monkeypatch.setattr(long, "SAME_COMPANY", {})
    keep, raw = long.wanted_symbols({}, {"OLDX": {"new_symbol": "NEWX"}, "QQQ": {"new_symbol": "RRR"}})
    assert keep == ["NEWX"] and raw == {"NEWX", "OLDX"}


def test_the_loader_reads_the_three_files_from_the_cache(tmp_path):
    from src.loaders import nse_long

    close, value, report = long.build(_prices(), SPLIT, {"renames": RENAMES}, RENAMES, ["AAA", "NEWX"])
    close.to_parquet(tmp_path / nse_long.CLOSE_FILE)
    value.to_parquet(tmp_path / nse_long.VALUE_FILE)
    (tmp_path / nse_long.REPORT_FILE).write_text('{"sessions": %d}' % len(close))
    out = nse_long.load(base="http://127.0.0.1:9/unreachable", cache=tmp_path)
    assert out is not None
    c, v, r = out
    assert c.shape == close.shape and r["sessions"] == len(close)
    avg = nse_long.average_value(v)
    assert avg["AAA"].iloc[:14].isna().all() and avg["AAA"].iloc[20:].notna().all()


def test_the_loader_returns_none_when_nothing_is_reachable(tmp_path):
    from src.loaders import nse_long

    assert nse_long.load(base="http://127.0.0.1:9/unreachable", cache=tmp_path) is None



def test_the_long_file_drops_a_holiday_copied_from_the_day_before():
    p = _prices()
    copy = p[p["date"] == pd.Timestamp("2010-01-20")].assign(date=pd.Timestamp("2010-01-21"))
    p = pd.concat([p[p["date"] != pd.Timestamp("2010-01-21")], copy], ignore_index=True)
    close, _value, report = long.build(p, SPLIT, {"renames": RENAMES}, RENAMES, ["AAA", "NEWX"])
    assert report["copied_sessions_dropped"] == ["2010-01-21"]
    assert pd.Timestamp("2010-01-21") not in close.index


def test_a_day_whose_value_is_1e5_too_large_is_scaled_back():
    p = _prices()
    bad = p["date"].dt.year.eq(2010) & p["date"].dt.month.eq(2)
    p.loc[bad, "value"] *= 1e5                      # R2's mirror rows for 2010-2018
    _close, value, report = long.build(p, SPLIT, {"renames": RENAMES}, RENAMES, ["AAA", "NEWX"])
    assert report["value_days_rescaled_from_x1e5"] == int(p.loc[bad, "date"].nunique())
    assert value.loc["2010-02-01":].max().max() < 1.0          # Rs Cr, not Rs 1e5 Cr
    assert report["value_over_close_x_volume_by_year"] == {2010: 1.0}


def test_tejhq_fills_only_gaps_in_nses_list(tmp_path):
    from scripts.build_nse_long_prices import with_tejhq

    path = tmp_path / "t.csv"
    pd.DataFrame([
        {"symbol": "ABC", "isin": "X", "ex_date": "2016-07-14", "kind": "bonus",
         "price_factor": 2 / 3, "purpose": "Bonus 1:2"},             # NSE has it: skipped
        {"symbol": "SUPRAJIT", "isin": "Y", "ex_date": "2010-03-18", "kind": "split",
         "price_factor": 0.1, "purpose": "Bon 1:1/Fv Spl Rs.5tore.1"},  # a gap: added
    ]).to_csv(path, index=False)
    nse = pd.DataFrame([{"symbol": "ABC", "ex_date": pd.Timestamp("2016-07-15"), "kind": "bonus",
                         "price_factor": 2 / 3, "purpose": "BONUS 1:2"}])
    out, n = with_tejhq(nse, path)
    assert n == 1 and out["symbol"].tolist() == ["ABC", "SUPRAJIT"]
    assert out.iloc[1]["price_factor"] == pytest.approx(0.1)
    assert with_tejhq(nse, tmp_path / "missing.csv") == (nse, 0)
