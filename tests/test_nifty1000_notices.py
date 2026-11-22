"""scripts/nifty1000_notices.py: the Nifty 1000's notices read like the other indices' (S196)."""
import json

from scripts import nifty1000_notices as nn

ENNATURE = """PRESS RELEASE
Mumbai, November 13, 2026
              Exclusion of Ennature Bio Pharma Ltd. from Nifty Indices
     NSE Indices Limited vide its press release dated August 26, 2026 had announced inclusion of IGL
     Spirits Ltd. (IGLSPIRITS) and Ennature Bio Pharma Ltd. (ENNATURE) with dummy symbols
     Ennature Bio Pharma Ltd. (ENNATURE) from various indices as listed hereunder effective from
     November 17, 2026 (close of November 16, 2026).
       Sr. No.                      Index Name
          1      Nifty Total Market
          2      Nifty Microcap 250
"""


def test_a_notice_whose_index_table_omits_the_nifty_1000_says_nothing_about_it():
    r = nn.read(ENNATURE)
    assert r["mentions"] is False and r["effective"] == "2026-11-17"


def test_a_single_company_notice_naming_the_nifty_1000_takes_that_companys_symbol():
    r = nn.read(ENNATURE + "          3      Nifty 1000\n")
    assert r["mentions"] and r["excluded"] == ["ENNATURE"] and r["included"] == []   # not IGLSPIRITS, named first


def test_the_equal_weight_index_is_not_the_nifty_1000():
    assert nn.read(ENNATURE + "          3      Nifty1000 Equal Weight\n")["mentions"] is False


def test_the_listing_keeps_notices_from_the_launch_on():
    html = ("<div class=\"pressItem\" data-date=\"Nov 20, 2026\" hidden=\"true\"> <p>Nov 20, 2026</p> "
            "<a href='/Press_Release/ind_prs20112026.pdf' target=\"_blank\">Replacement in indices</a></div>"
            "<div class=\"pressItem\" data-date=\"Oct 28, 2026\" hidden=\"true\"> <p>Oct 28, 2026</p> "
            "<a href='/Press_Release/ind_prs28102026.pdf' target=\"_blank\">Exclusion of X</a></div>")
    assert [n["notice"] for n in nn.listing(html)] == ["ind_prs20112026.pdf"]


def test_the_check_flags_a_recorded_change_with_no_notice_and_a_due_notice_not_recorded():
    hist = {"indices": {"nifty_1000": {"baseline": {"date": "2026-10-30", "symbols": ["A", "B"]},
                                       "changes": [{"date": "2026-12-01", "added": ["C"], "removed": ["B"]}]}}}
    ledger = {"notices": [{"notice": "n.pdf", "mentions": True, "effective": "2026-12-01",
                           "included": ["C"], "excluded": ["A"]}]}
    w = nn.check(ledger, hist, today="2026-12-02")
    assert any("B removed" in x for x in w) and any("excludes A" in x for x in w) and not any("C" in x for x in w)


def test_the_committed_ledger_reads_every_notice_since_the_launch_and_agrees_with_the_history():
    ledger = json.loads(nn.LEDGER.read_text(encoding="utf-8"))
    assert ledger["notices"][0]["notice"] == "ind_prs12112026.pdf"      # the launch itself
    assert all(len(n["sha256"]) == 64 for n in ledger["notices"])
    assert nn.check(ledger, json.loads(nn.HISTORY.read_text(encoding="utf-8")), today="2026-11-22") == []
