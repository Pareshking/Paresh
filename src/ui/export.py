"""The CSV files the pages offer, in one unit and one precision (S236 F19; owner, 28 Nov 2026: "With your
recommendation ... Not using download files yet and you can keep them").

The site audit of 28 Nov found the Screener's file giving returns as fractions (0.10) beside drawdowns in
percent (-2.59), the Portfolio's rebalance lines a "Return %" in fractions where its trades file has percent,
floats such as 1542.300048828125, and emoji in a text column. Every file now gives:

- every return and fall in percent, a fraction column renamed with " %" so the unit is in the header;
- two decimals, except the ranking score, kept at four (it is the order the ranking sorts by, and two
  decimals would tie stocks the ranking tells apart);
- plain text, without emoji.

The Kite basket (`actions_page`) is not written here: its columns are Kite's import format.
"""
from __future__ import annotations

import re

import pandas as pd

# "1M Return" ... "12M Return": the ranking keeps these as fractions (0.0752 for +7.5%).
FRACTION_COLUMN = re.compile(r"^\d+M Return$")
KEEP_FOUR = frozenset({"Score"})
# Emoji and pictographs, the variation selector that makes a symbol an emoji, and the joiner.
_EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿⬀-⯿️‍]")


def tidy(frame: pd.DataFrame, fractions: tuple[str, ...] = ()) -> pd.DataFrame:
    """A copy of `frame` as the file gives it. `fractions`: further columns held as fractions."""
    out = frame.copy()
    renames = {}
    for col in out.columns:
        name = str(col)
        if FRACTION_COLUMN.match(name) or name in fractions:
            out[col] = pd.to_numeric(out[col], errors="coerce") * 100
            if not name.endswith("%"):
                renames[col] = f"{name} %"
    for col in out.columns:
        if pd.api.types.is_float_dtype(out[col]):
            out[col] = out[col].round(4 if str(col) in KEEP_FOUR else 2)
        elif pd.api.types.is_object_dtype(out[col]) or pd.api.types.is_string_dtype(out[col]):
            out[col] = out[col].map(lambda v: _EMOJI.sub("", v).strip() if isinstance(v, str) else v)
    return out.rename(columns=renames)


def csv_bytes(frame: pd.DataFrame, fractions: tuple[str, ...] = ()) -> bytes:
    return tidy(frame, fractions).to_csv(index=False).encode()
