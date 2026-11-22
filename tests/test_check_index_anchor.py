"""Guards for scripts/check_index_anchor.py."""
import json

from scripts import check_index_anchor as a

H = {"indices": {"x": {"baseline": {"date": "2020-01-01", "symbols": ["A", "B", "DUMMYZ"]},
                       "changes": [{"date": "2020-02-01", "added": ["C"], "removed": ["B"]}]}}}


def test_current_members_replays_changes_and_drops_dummies():
    assert a.current_members(H, "x") == {"A", "C"}


def test_parse_symbols_handles_bom_blank_and_dummy_rows():
    raw = "﻿Company Name,Industry,Symbol\nAcme,x,A\nDum,x,DUMMYQ\nNone,x,\nCo,x, C \n".encode()
    assert a.parse_symbols(raw) == {"A", "C"}


def test_compare_flags_differences_on_either_host():
    ok = a.compare(H, "x", {"niftyindices": {"A", "C"}, "nsearchives": {"A", "C"}})
    assert ok["agrees"] and ok["history"] == 2
    bad = a.compare(H, "x", {"niftyindices": {"A", "C"}, "nsearchives": {"A", "D"}})
    assert not bad["agrees"] and bad["only_nsearchives"] == ["D"] and bad["only_history_vs_nsearchives"] == ["C"]


def test_fetch_fails_loudly_on_empty_or_bad_response():
    class R:
        status_code = 200
        content = b""

    class S:
        def get(self, *args, **kwargs):
            return R()

    import pytest
    from unittest import mock
    with mock.patch.object(a.time, "sleep"), pytest.raises(a.AnchorError):
        a.fetch("https://example.invalid/x.csv", tries=2, session=S())


def test_record_is_json_serialisable():
    rec = a.compare(H, "x", {"niftyindices": {"A", "C"}, "nsearchives": {"A", "C"}})
    assert json.loads(json.dumps(rec, sort_keys=True))["index"] == "x"


def test_the_nifty_1000_is_anchored_on_the_host_that_publishes_it(monkeypatch, tmp_path, capsys):
    # S196: tracked like the other indices; nsearchives does not publish it (404 on 22 Nov 2026).
    import json

    assert a.FILES["nifty_1000"] == "ind_nifty1000_list.csv" and a.NOT_ON["nifty_1000"] == ("nsearchives",)
    hist = {"indices": {"nifty_1000": {"baseline": {"date": "2026-10-30", "symbols": ["A", "B"]}, "changes": []}}}
    p = tmp_path / "h.json"
    p.write_text(json.dumps(hist))
    monkeypatch.setattr(a, "HISTORY", p)
    monkeypatch.setattr(a, "FILES", {"nifty_1000": "ind_nifty1000_list.csv", "nifty_50": "x.csv"})
    asked = []
    monkeypatch.setattr(a, "fetch", lambda url: asked.append(url) or b"Symbol\nA\nB\n")
    assert a.main(["--dry-run"]) == 0
    assert asked == ["https://www.niftyindices.com/IndexConstituent/ind_nifty1000_list.csv"]   # nifty_50 not recorded: skipped
    assert "not published on nsearchives" in capsys.readouterr().out
