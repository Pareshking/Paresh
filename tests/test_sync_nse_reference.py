"""Guards for scripts/sync_nse_reference.py: never overwrite good data with a broken fetch."""
import json
from datetime import datetime, timezone

import pytest

from scripts import sync_nse_reference as s


def test_guard_refuses_empty_and_shrunken_feeds():
    with pytest.raises(s.SyncError):
        s.guard("f", 0, 100)
    with pytest.raises(s.SyncError):
        s.guard("f", 80, 100)
    s.guard("f", 95, 100)
    s.guard("f", 5, None)


def test_parse_csv_strips_bom_and_padded_headers():
    rows = s.parse_csv("﻿SYMBOL, NAME OF COMPANY\nAAA, A Ltd\n".encode())
    assert rows == [{"SYMBOL": "AAA", "NAME OF COMPANY": "A Ltd"}]


def test_diff_new_reports_only_unseen_rows():
    old = [{"symbol": "A", "exDate": "1", "subject": "x"}]
    new = old + [{"symbol": "B", "exDate": "2", "subject": "y"}]
    assert s.diff_new(old, new, ("symbol", "exDate", "subject")) == [new[1]]


def test_corporate_action_window_and_shape():
    seen = {}

    def fetch(url, params):
        seen.update(params)
        return json.dumps([{"symbol": "A"}]).encode()

    rows = s.fetch_corporate_actions(datetime(2026, 10, 2, tzinfo=timezone.utc), days=45, fetch=fetch)
    assert rows == [{"symbol": "A"}] and seen["to_date"] == "02-10-2026" and seen["from_date"] == "18-08-2026"
    with pytest.raises(s.SyncError):
        s.fetch_corporate_actions(datetime(2026, 10, 2, tzinfo=timezone.utc), fetch=lambda u, p: b'{"x": 1}')


def test_membership_symbols_reads_baselines_and_recent_changes(tmp_path):
    p = tmp_path / "h.json"
    p.write_text(json.dumps({"indices": {"i": {"baseline": {"symbols": ["A"]},
                                               "changes": [{"added": ["B"], "removed": ["C"]}]}}}))
    assert s.membership_symbols(p) == {"A", "B", "C"}
    assert s.membership_symbols(tmp_path / "missing.json") == set()


def test_headerless_symbol_change_file_keeps_its_first_row():
    raw = b"Acme Ltd,OLD,NEW,01-JUL-2026\nBeta Ltd,B1,B2,02-JUL-2026\n"
    rows = s.parse_csv(raw, s.HEADERLESS["symbolchange.csv"])
    assert len(rows) == 2 and rows[0] == {"company": "Acme Ltd", "old_symbol": "OLD", "new_symbol": "NEW", "date": "01-JUL-2026"}
