"""S193 PR 2 part B: type scale and spacing (I), accessibility (J1, J2) and the "–" wording (E2).

Owner, 23 Nov 2026: "Go with your recommendation on I and E" and "on all" (J). Each test keeps
one decision fixed; docs/archive/S193_ITEM_E_2026-11-23.md and S193_BENCHMARK_HJ_2026-11-23.md
hold the evidence.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "src" / "ui"

# Files another agent was editing while this was built (charts, S193 H). That work has landed, so
# every file in src/ui is held to these rules; the set stays empty.
OTHER_AGENT: set = set()


def _mine():
    return [f for f in UI.rglob("*.py") if f.name not in OTHER_AGENT and f.name != "tokens.py"]


# ── I1: every font size from tokens.TYPE ────────────────────────────────────

FONT_LITERAL = re.compile(r"font-size\s*:\s*[\d.]+\s*(px|rem)\b|fontSize\s*[:=]\s*[\d.]+")  # em: an icon sized to its text


def test_no_font_size_literal_outside_the_tokens():
    found = [f"{f.relative_to(ROOT)}:{n}" for f in _mine()
             for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1) if FONT_LITERAL.search(line)]
    assert not found, f"font sizes must be var(--fs-…) from tokens.TYPE: {found}"


def test_every_font_size_variable_is_a_step_of_the_scale():
    from src.ui.tokens import TYPE
    used = {m for f in UI.rglob("*.py") for m in re.findall(r"var\(--fs-([0-9a-z_]+)\)", f.read_text(encoding="utf-8"))}
    assert used <= set(TYPE), used - set(TYPE)


# ── I2: the spacing ladder; hand-typed spacings may only fall ──────────────

SPACING = re.compile(r"(?<![\w-])(?:margin|padding|gap|row-gap|column-gap)"
                     r"(?:-(?:top|bottom|left|right|inline|block)(?:-(?:start|end))?)?\s*:\s*[^;}\"'!]*?\d+(?:\.\d+)?px")
# Hand-typed px margins, paddings and gaps in src/ui: 503 on 23 Nov 2026 before the ladder was
# applied to the gaps between blocks (sections, cards, heading to text, chart to note), 465 after.
# Cell and chip padding stay as typed. Lower this number when a change removes some; never raise it.
SPACING_BUDGET = 465


def test_hand_typed_spacings_do_not_rise():
    n = sum(len(SPACING.findall(f.read_text(encoding="utf-8"))) for f in UI.rglob("*.py"))
    assert n <= SPACING_BUDGET, f"{n} hand-typed px spacings in src/ui, budget {SPACING_BUDGET}: use var(--sp-…)"


def test_block_gaps_read_the_ladder():
    from src.ui.views.dashboard_home_view import HOME_CSS
    assert ".dh-sec{padding:var(--sp-6) 0 0;display:flex;flex-direction:column;gap:var(--sp-5)}" in HOME_CSS
    assert ".dh-fig{margin:0;display:flex;flex-direction:column;gap:var(--sp-2)}" in HOME_CSS


# ── J2: text contrast ───────────────────────────────────────────────────────

def _lum(h: str) -> float:
    c = [int(h.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def _contrast(a: str, b: str) -> float:
    x, y = sorted((_lum(a), _lum(b)), reverse=True)
    return (x + 0.05) / (y + 0.05)


TEXT_TOKENS = ("ink", "ink_2", "text_2", "muted", "muted_2", "faint", "up", "up_dark", "down", "down_dark",
               "caution", "caution_ink", "violet")


@pytest.mark.parametrize("name", TEXT_TOKENS)
@pytest.mark.parametrize("ground", ("white", "subtle", "fill"))
def test_every_text_colour_is_4_5_to_1_on_every_ground(name, ground):
    """WCAG 1.4.3, no exemption for secondary text (S193 J2). `faint` was #70706B, 4.44:1 on fill."""
    from src.ui.tokens import PALETTE
    assert _contrast(PALETTE[name], PALETTE[ground]) >= 4.5, (name, ground, round(_contrast(PALETTE[name], PALETTE[ground]), 2))


def test_teal_and_quiet_are_never_text_in_these_files():
    """Teal (4.06:1) and quiet (2.4:1) are for chart lines and the tooltip on ink only."""
    bad = [f"{f.name}:{n}" for f in _mine() for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1)
           if re.search(r"(?<![-\w])color\s*:\s*var\(--c-(teal|quiet|mid|s_ema50|s_dii)\)", line)]
    assert not bad, bad


# ── J1: never colour alone ──────────────────────────────────────────────────

def test_every_caution_class_carries_the_icon():
    from src.ui import theme
    css = theme.WARN_ICON_CSS
    for sel in (".stale-notice:not(.stale-notice-info)", ".pg-note", ".pg-callout.warn > b", ".bt-warn",
                ".badge-yellow", ".hdr-pill-warn .hdr-dot", ".dh-watch", ".xw-pill.watch", ".cau"):
        assert f"{sel}::before" in css, sel
    # Generated content with empty alternative text: the glyph is not read aloud.
    assert 'content: "!" / ""' in css


def test_inline_caution_text_is_marked_for_the_icon():
    """Text coloured caution in an inline style must carry the `cau` class (or sit in an SVG)."""
    bad = []
    for f in _mine():
        for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"style=\"[^\"]*(?<![-\w])color\s*:\s*\{?\"?var\(--c-caution\)", line) and "cau" not in line:
                bad.append(f"{f.name}:{n}")
    assert not bad, bad


def test_notes_and_warning_boxes_lead_with_a_word(monkeypatch):
    from src.ui import page_kit as kit
    out = []
    monkeypatch.setattr(kit.st, "html", lambda t, **k: out.append(t))
    kit.note("Check this.", "detail", kind="warning")
    kit.callout("Check this.", "body", tone="warn")
    kit.callout("Fine.", "body", tone="up")
    kit.note("Prices are behind.", "detail", kind="late")
    kit.note("Each run picks its own index.", "detail", kind="info")
    assert 'class="warn-word">Warning:</span>' in out[0] and "pg-note" in out[0]
    assert 'class="warn-word">Warning:</span>' in out[1]
    assert "warn-word" not in out[2]
    assert 'class="warn-word">Late:</span>' in out[3]
    # An explaining note: muted, no icon (pg-info has no ::before), no leading word, no caution colour.
    assert "pg-info" in out[4] and "warn-word" not in out[4] and "pg-note" not in out[4]
    from src.ui import theme
    assert ".pg-info" not in theme.WARN_ICON_CSS
    with pytest.raises(TypeError):
        kit.note("No kind chosen.")            # the choice is explicit at every call site


# Every caution note (kit.note kind "warning" or "late"), by file and its lead's source, with why it is a
# warning: something wrong, late, missing or risky. A note that only explains is kind="info" (owner's
# coordinator, 23 Nov 2026: Backtest's "does not change these runs" read "Warning:" and was information).
CAUTION_NOTES = {
    ("app.py", "*system_note(system_name, rank_df"): "the Nifty 1000's members not ranked yet: missing",
    ("actions_page.py", "*note"): "unpriced_note: members the book was formed without a close for: missing",
    ("actions_view.py", '"That file could not be read as Kite'): "the upload failed: wrong",
    ("backtest_view.py", 'f"No membership history for'): "the index's list is missing",
    ("backtest_view.py", 'f"{iu.INDICES[key]} has no completed month'): "the window chosen holds nothing: wrong",
    ("backtest_view.py", '"The Nifty 500\'s closes are unavailable."'): "the benchmark is missing",
    ("backtest_view.py", '"Not enough price history for this window."'): "history missing for the window",
    ("backtest_view.py", '"Traded value is not available right now'): "traded value missing; the floor is off",
    ("config_view.py", 'f"The last sync ('): "the sync failed",
    ("config_view.py", '"All five lookback weights are zero'): "a setting that cannot rank: wrong",
    ("config_view.py", 'f"The stock cap ({new_stc}%) is above'): "two caps no book can meet: wrong",
    ("config_view.py", 'f"At {new_stc}% per stock and {n_hold}'): "the weighting setting has no effect: risky",
    ("portfolio_page.py", "*note"): "unpriced_note: missing closes",
    ("portfolio_page.py", '"The model book could not be read just now."'): "the book failed its check",
    ("portfolio_page.py", '"The track record could not be read just now."'): "the ledger could not be read",
    ("portfolio_page.py", '"The model book’s holdings could not be valued just now."'): "the book could not be valued",
}


def _kit_notes():
    import ast
    for f in [ROOT / "app.py", *sorted((ROOT / "src").rglob("*.py"))]:
        src = f.read_text(encoding="utf-8")
        for n in ast.walk(ast.parse(src)):
            if (isinstance(n, ast.Call) and getattr(n.func, "attr", None) == "note"
                    and getattr(getattr(n.func, "value", None), "id", None) == "kit"):
                kind = next((k.value for k in n.keywords if k.arg == "kind"), None)
                yield f.name, ast.get_source_segment(src, n.args[0]), getattr(kind, "value", None)


def test_every_caution_note_is_a_listed_warning():
    notes = list(_kit_notes())
    assert notes
    bad, used = [], set()
    for name, lead, kind in notes:
        assert kind in ("warning", "late", "info"), (name, lead, kind)
        if kind == "info":
            continue
        hit = next((k for k in CAUTION_NOTES if k[0] == name and lead.startswith(k[1])), None)
        if hit is None:
            bad.append(f"{name}: {lead[:50]}")
        used.add(hit)
    assert not bad, ("a caution note not in CAUTION_NOTES: add it with why it is a warning, or make it "
                     f"kind='info' if it only explains: {bad}")
    assert used >= set(CAUTION_NOTES), f"listed but no longer a caution note: {set(CAUTION_NOTES) - used}"


def test_backtest_system_note_is_information():
    src = (UI / "views" / "backtest_view.py").read_text(encoding="utf-8")
    assert '"index in the settings below.", kind="info")' in src


def test_the_late_banner_and_pill_say_late(monkeypatch):
    from src.ui import components as c
    monkeypatch.setattr(c, "data_freshness", lambda: [{"label": "Prices", "as_of": "18 Nov", "stale": True}])
    pill = c._status_pill_html()
    assert "hdr-pill-warn" in pill and "Late:" in pill
    src = (UI / "components.py").read_text(encoding="utf-8")
    assert '<span class="warn-word">Late:</span> {html.escape(notice)}' in src


# ── E2: one wording per cause, from one module ──────────────────────────────

def test_the_fixed_words():
    from src.ui import missing_words as mw
    assert mw.OUT == "Out" and mw.DASH == "–" and mw.NOT_APPLICABLE == ""
    assert mw.column_note("12M", mw.system_too_young()) == "– in 12M: the system is too young."
    assert mw.since("2026-01-28") == "since 28 Jan 2026"
    assert mw.no_events("your stocks", "2026-12-01") == \
        "No board meeting or ex-date is announced for your stocks before the 1 Dec fill."
    assert mw.no_such_index("Nano Cap") == "no NSE index for Nano Cap"


# Each repeated state's words, and the one module allowed to write them by hand.
REPEATED = {
    "No model book yet": "NO_MODEL_BOOK",
    "ex-date is announced for": "no_events",
    "No stocks match": "NO_MATCH",
    "No stock matches": "NO_MATCH",
    "No data available": "NO_ROWS",
    "the system is too young": "SYSTEM_TOO_YOUNG",
}


@pytest.mark.parametrize("words", sorted(REPEATED))
def test_a_cause_is_worded_only_in_missing_words(words):
    hits = [f"{f.name}:{n}" for f in _mine() if f.name != "missing_words.py"
            for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1)
            if words in line and not line.lstrip().startswith("#")]
    assert not hits, f"{words!r} written by hand, use missing_words.{REPEATED[words]}: {hits}"


def test_no_blue_info_box_for_an_empty_state():
    bad = [f"{f.name}:{n}" for f in _mine() for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1)
           if re.search(r"\bst\.(info|warning|error)\(", line)]
    assert not bad, f"an empty state is kit.empty, a failure kit.note (R4): {bad}"


def test_rank_turnover_says_out_for_a_failed_filter():
    import pandas as pd

    from src.engine import dashboard_insights as di
    from src.ui.views import dashboard_home_view as dh

    t = di.Turnover(top=50, new=1, climbers=[("LENSKART", 17, None, 18)], fallers=[])
    html = dh._turnover_html(t, pd.Series({"LENSKART": "Retail"}))
    assert "#17</td>" in html and ">Out</td>" in html and "–" not in html


def test_backtest_index_column_blank_where_it_does_not_apply():
    src = (UI / "views" / "backtest_view.py").read_text(encoding="utf-8")
    assert '["A year before costs", _pc(st_.get("cagr_gross")), mw.NOT_APPLICABLE]' in src
    assert '["Turnover, one way, a month", f"{st_.get(\'avg_turnover\', 0):.0f}%", mw.NOT_APPLICABLE]' in src


def test_backtest_months_grid_footnotes_its_dash():
    import pandas as pd

    from src.ui.views.backtest_view import _months_dash_note
    m = pd.DataFrame({"rule": [0.01] * 3}, index=pd.to_datetime(["2026-08-31", "2026-09-30", "2026-10-31"]))
    note = _months_dash_note(m)
    # S203 bt.yr.3: the months after the last one tested are blank cells, so the note names only the start.
    assert note.startswith("– in a month:") and "Aug 2026" in note and "Oct 2026" not in note


def test_watchlist_headline_for_one_stock():
    import pandas as pd

    from src.ui import watchlist_lines as wl
    ln = wl.Lines(buy=20, keep=40, high_gap=20)
    t = pd.DataFrame({"Symbol": ["ABC"], "Qualified Rank": [55]})
    head = wl.title(t, 1, None, ln)
    assert head.startswith("Your 1 stock is ") and "not in the top 20 qualified" in head and "None of" not in head
    assert 'class="dh-down"' in head


def test_watchlist_headline_says_the_check_not_a_sale_date():
    """S203 wl.head.1: "sold on 30 Nov" read as a trade on the 30th; sales fill the next session."""
    import re
    from types import SimpleNamespace

    import pandas as pd

    from src.ui import watchlist_lines as wl
    ln = wl.Lines(buy=20, keep=40, high_gap=20)
    t = pd.DataFrame({"Symbol": ["A", "B", "C"], "Qualified Rank": [3, 30, 60]})
    plan = SimpleNamespace(book=["A", "B"], sells=["B"], check=pd.Timestamp("2026-11-30"))
    txt = re.sub(r"<[^>]+>", "", wl.title(t, 3, plan, ln))
    assert txt == "1 of your 3 stocks is in the top 20 qualified. The book holds 2 of them; 1 would be sold at the 30 Nov check."
    plan = SimpleNamespace(book=["A"], sells=[], check=pd.Timestamp("2026-11-30"))
    assert re.sub(r"<[^>]+>", "", wl.title(t, 3, plan, ln)).endswith(
        "The book holds one of them, A, and would keep it at the 30 Nov check.")
