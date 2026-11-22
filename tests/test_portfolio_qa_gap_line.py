"""Portfolio QA's gap pattern matches the line Portfolio writes (run 45083394151, 23 Nov 2026).

#631 (glossary 1) changed "4.0 pts ahead of the market" to "... ahead of Nifty Total Market";
the QA pattern still asked for "the market" and failed on a correct page.
"""
import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = (ROOT / "src/ui/views/portfolio_page.py").read_text(encoding="utf-8")


def _qa():
    spec = importlib.util.spec_from_file_location("pqa", ROOT / "scripts/portfolio_production_qa.py")
    src = spec.loader.get_source("pqa") if hasattr(spec.loader, "get_source") else ""
    return re.search(r'GAP_LINE = re\.compile\(r"([^"]+)"\)', src).group(1)


def test_the_page_writes_the_line_qa_looks_for():
    assert "pts {'ahead of' if gap >= 0 else 'behind'} Nifty Total Market" in PAGE


def test_qa_pattern_matches_both_directions_and_not_the_old_wording():
    pat = re.compile(_qa())
    assert pat.search("4.0 pts ahead of nifty total market")
    assert pat.search("1.2 pts behind nifty total market")
    assert not pat.search("4.0 pts ahead of the market")
