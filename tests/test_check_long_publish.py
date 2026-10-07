"""A long NSE price file smaller than the published one is not published (scripts/check_long_publish.py)."""
import pandas as pd

from scripts import check_long_publish as clp


def _write(folder, sessions, symbols=3, pack_rows=None, start="2008-01-01"):
    folder.mkdir()
    idx = pd.bdate_range(start, periods=sessions, name="date")
    pd.DataFrame(1.0, index=idx, columns=[f"S{i}" for i in range(symbols)]).to_parquet(folder / clp.CLOSE)
    rows = pack_rows or sessions
    days = list(idx) * (rows // sessions + 1)
    pd.DataFrame({"date": days[:rows], "close": 1.0}).to_parquet(folder / clp.PACK)
    return folder


def test_a_file_as_long_as_the_published_one_passes(tmp_path):
    old, new = _write(tmp_path / "old", 100), _write(tmp_path / "new", 101)
    assert clp.problems(new, old) == []
    assert clp.main(["--new", str(new), "--old", str(old)]) == 0


def test_a_shorter_or_later_starting_file_is_refused(tmp_path):
    old = _write(tmp_path / "old", 100)
    late = _write(tmp_path / "late", 100, start="2015-01-01")
    assert any("starts" in p for p in clp.problems(late, old))
    short = _write(tmp_path / "short", 60)
    found = clp.problems(short, old)
    assert any("sessions" in p for p in found) and any("ends" in p for p in found)
    assert clp.main(["--new", str(short), "--old", str(old)]) == 1


def test_lost_symbols_or_pack_rows_are_refused(tmp_path):
    old = _write(tmp_path / "old", 100, symbols=200, pack_rows=500)
    fewer = _write(tmp_path / "fewer", 100, symbols=150, pack_rows=500)
    assert any("symbols" in p for p in clp.problems(fewer, old))
    thin = _write(tmp_path / "thin", 100, symbols=200, pack_rows=300)
    assert any("raw pack" in p for p in clp.problems(thin, old))


def test_the_first_build_has_nothing_to_compare_with(tmp_path):
    new = _write(tmp_path / "new", 10)
    (tmp_path / "none").mkdir()
    assert clp.problems(new, tmp_path / "none") == []


def _workflow(name):
    from pathlib import Path

    import yaml

    path = Path(__file__).resolve().parents[1] / ".github" / "workflows" / name
    return yaml.safe_load(path.read_text(encoding="utf-8"))["jobs"]


def test_the_long_file_is_checked_before_it_is_published():
    steps = [s.get("name", "") + "\n" + s.get("run", "") for s in _workflow("nse_long_prices.yml")["build"]["steps"]]
    check = next(i for i, s in enumerate(steps) if "check_long_publish.py" in s)
    upload = next(i for i, s in enumerate(steps) if "nse_long_close.parquet" in s and "upload" in s)
    assert check < upload
    assert "2008-01-01" in steps[check]          # a partial build may not replace the file


def test_the_ss_and_screener_stores_never_shrink_on_upload():
    ss = "\n".join(s.get("run", "") for s in _workflow("ss_sync.yml")["sync"]["steps"])
    assert "could not be downloaded; stopping" in ss and "restored_rows" in ss
    scr = "\n".join(s.get("run", "") for job in _workflow("screener_sync.yml").values() for s in job["steps"])
    assert "fewer rows than the published one" in scr
