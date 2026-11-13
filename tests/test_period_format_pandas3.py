"""pandas 3's Period.__format__ rejects a date spec such as "%b %Y": an
f-string like f"{pd.Period(m, freq='M'):%b %Y}" raises TypeError at render
time (it crashed the US port's Dashboard and Portfolio pages, 10-11 Nov 2026)."""
import pathlib
import re


def test_no_period_fstring_date_spec_in_the_app():
    pat = re.compile(r"Period\([^)]*\)\s*:%")
    hits = [f"{p}:{i}" for p in [*pathlib.Path("src").rglob("*.py"), pathlib.Path("app.py")]
            for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1) if pat.search(line)]
    assert not hits, hits
