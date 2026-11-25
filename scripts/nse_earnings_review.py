"""NSE's quarterly Corporate Earnings Review, as one table (S171 part 1).

NSE's Economic Policy & Research team publishes a "Corporate Performance
Review" (its file names say "Corporate Earnings Review") about 2.5 months after
each quarter: revenue and profit growth for the Nifty 50 and Nifty 500 and,
from 2024, the Nifty Next 50, Midcap 150 and Smallcap 250, from CMIE Prowess.
This script downloads those PDFs, reads their text with ``pdftotext -layout``
and writes ``data/reference/nse_earnings_review.csv``: one row per (quarter,
index, measure), each with the PDF link, the PDF page and the text the number
was read from.

    python -I scripts/nse_earnings_review.py --mode download --raw <scratch dir>
    python -I scripts/nse_earnings_review.py --mode build --raw <scratch dir> \
        --out data/reference/nse_earnings_review.csv

The PDFs are downloaded files: keep them outside the repository and run with
``-I``.

Measures (all % YoY, as NSE prints them):
  sales_agg_yoy     aggregate net sales growth
  sales_median_yoy  median net sales growth across the index's companies
  pat_agg_yoy       aggregate PAT growth (NSE's "adjusted PAT" where it says so)
  pat_median_yoy    median PAT growth across the index's companies

Where each number comes from (the ``source`` column):
  table             the issue's own table, current-quarter column. Aggregates:
                    "Sector-wise net sales / PAT growth of Nifty 50 / Nifty 500
                    companies", row "Nifty 50" / "Nifty 500". Medians: "Segment-
                    wise distribution of companies based on YoY aggregate and
                    median topline / PAT growth" (Q1 FY26 on), column "Median";
                    for Q4 FY23 and Q2 FY24 the Nifty 500 "Interquartile range"
                    table, column 50%.
  table, later issue  a quarter NSE published no issue for, read from the next
                    issue's previous-quarter column (or, for medians, the
                    interquartile table's row for that quarter). The ``issue``
                    column names the issue it came from.
  prose             a sentence of the issue (the Next 50, Midcap 150 and
                    Smallcap 250 aggregates are only ever in prose). The
                    sentences are listed in ``PROSE`` by hand; the build fails
                    unless each is found, word for word, on its page.

``page`` is the PDF's page number (1 = the cover), as a PDF viewer counts it,
not the number printed in the footer. ``cross_check`` names any other place in
the same issue that states the same figure, and says so when it differs.
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import subprocess
import sys
import time

USER_AGENT = "Mozilla/5.0 (compatible; umiya-research/1.0)"
INDICES = ["Nifty 50", "Nifty Next 50", "Nifty Midcap 150", "Nifty Smallcap 250", "Nifty 500"]
MEASURES = ["sales_agg_yoy", "sales_median_yoy", "pat_agg_yoy", "pat_median_yoy"]
COLUMNS = ["quarter", "index", "measure", "value_pct", "source", "issue", "published", "pdf_url", "page",
           "quote", "cross_check"]

# Every issue NSE's Market Reports page lists, Q1 FY22 onward
# (https://www.nseindia.com/static/research/market-reports, read 25 Nov 2026).
# published: the date in the file name where it has one, else the month on the cover.
ISSUES = {
    "Q1FY22": ("https://nsearchives.nseindia.com/s3fs-public/inline-files/Q1FY22_Corporate_Earnings_Review.pdf", "2021-09"),
    "Q3FY22": ("https://nsearchives.nseindia.com/s3fs-public/inline-files/Q3FY22_Corporate_Earnings_Review.pdf", "2022-02"),
    "Q4FY22": ("https://nsearchives.nseindia.com/s3fs-public/inline-files/Q4FY22_Corporate_Earnings_Review.pdf", "2022-06"),
    "Q1FY23": ("https://nsearchives.nseindia.com/s3fs-public/inline-files/Q1FY23%20Corporate%20Earnings%20Review_20220825_1.pdf", "2022-08-25"),
    "Q2FY23": ("https://nsearchives.nseindia.com/s3fs-public/inline-files/Q2FY23%20Corporate%20Earnings%20Review_20221223.pdf", "2022-12-23"),
    "Q4FY23": ("https://nsearchives.nseindia.com/s3fs-public/inline-files/Q4FY23%20Corporate%20Earnings%20Review.pdf", "2023-07"),
    "Q2FY24": ("https://nsearchives.nseindia.com/web/sites/default/files/inline-files/Q2FY24%20Corporate%20Earnings%20Review.pdf", "2023-11"),
    "Q4FY24": ("https://nsearchives.nseindia.com/web/sites/default/files/inline-files/Q4FY24%20Corporate%20Earnings%20Review.pdf", "2024-06"),
    "Q1FY25": ("https://nsearchives.nseindia.com/web/sites/default/files/inline-files/Q1FY25_CorporateEarningsReview.pdf", "2024-09"),
    "Q2FY25": ("https://nsearchives.nseindia.com/web/sites/default/files/inline-files/Q2FY25%20Corporate%20Earnings%20Review.pdf", "2024-12"),
    "Q3FY25": ("https://nsearchives.nseindia.com/web/sites/default/files/inline-files/Q3FY25%20Corporate%20Earnings%20Review_1.pdf", "2025-03"),
    "Q4FY25": ("https://nsearchives.nseindia.com/web/sites/default/files/inline-files/Q4FY25%20Corporate%20Earnings%20Review_20250627.pdf", "2025-06-27"),
    "Q1FY26": ("https://nsearchives.nseindia.com/web/sites/default/files/inline-files/Q1FY26%20Corporate%20Earnings%20Review_v1.0_20250912.pdf", "2025-09-12"),
    "Q2FY26": ("https://nsearchives.nseindia.com/web/sites/default/files/inline-files/Q2FY26%20Corporate%20Earnings%20Review_20251126.pdf", "2025-11-26"),
    "Q3FY26": ("https://nsearchives.nseindia.com/web/mediaattachment/2026-03/Q3FY26_Corporate_Earnings_Review_20260305120652.pdf", "2026-03-05"),
    "Q1FY27": ("https://nsearchives.nseindia.com/web/mediaattachment/2026-09/Q1FY27_Corporate_Earnings_Review_v1.0_20260911_20260916121318.pdf", "2026-09-16"),
}

# Quarters since Q1 FY22 with no issue of their own (25 Nov 2026).
GAPS = {
    "Q2FY22": "No issue on NSE's Market Reports page; aggregates from the Q3FY22 issue's Sep-21 column, "
              "Nifty 500 medians from the Q2FY24 issue's interquartile table (Sep-21 row)",
    "Q3FY23": "No issue on NSE's Market Reports page; Nifty 50 and Nifty 500 aggregates from the Q4FY23 issue's Dec-22 column",
    "Q1FY24": "No issue on NSE's Market Reports page; Nifty 50 and Nifty 500 aggregates from the Q2FY24 issue's Jun-23 column",
    "Q3FY24": "No issue on NSE's Market Reports page; Nifty 50 and Nifty 500 aggregates from the Q4FY24 issue's Dec-23 column",
    "Q4FY26": "No issue on NSE's Market Reports page; Nifty 50 and Nifty 500 aggregates from the Q1FY27 issue's Mar-26 column",
    "Q2FY27": "Not published yet (the Q2 issue came out on 26 Nov in 2025)",
}

# Sentences read by hand: (issue, index, measure, value, page, role, sentence). The build checks each
# sentence is on that page word for word and holds the value. role "value": the only source for the figure;
# "check": a second statement of a figure a table already gives (a difference is reported as a conflict);
# "basis": the same measure on another basis (NSE's Q3 FY26 summary excludes Tata Motors, demerged
# 1 Oct 2025, while the tables' index row includes it): noted in cross_check, not a conflict.
PROSE = [
    ("Q1FY25", "Nifty Smallcap 250", "pat_agg_yoy", 16.8, 24, "value",
     "led by 16.8% YoY growth in Nifty Smallcap 250 universe followed by 11.4% YoY growth in Nifty Midcap 150 universe."),
    ("Q1FY25", "Nifty Midcap 150", "pat_agg_yoy", 11.4, 24, "value",
     "led by 16.8% YoY growth in Nifty Smallcap 250 universe followed by 11.4% YoY growth in Nifty Midcap 150 universe."),
    ("Q3FY26", "Nifty Next 50", "sales_agg_yoy", 6.8, 24, "value",
     "The Nifty Next 50 posted 6.8% YoY revenue growth, contributing 16% to aggregate Nifty 500 expansion."),
    ("Q3FY26", "Nifty Midcap 150", "sales_agg_yoy", 14.0, 24, "value",
     "the Nifty Midcap 150 and Nifty Smallcap 250 delivered YoY growth of 14% and 10%, contributing 25% and 10%, respectively."),
    ("Q3FY26", "Nifty Smallcap 250", "sales_agg_yoy", 10.0, 24, "value",
     "the Nifty Midcap 150 and Nifty Smallcap 250 delivered YoY growth of 14% and 10%, contributing 25% and 10%, respectively."),
    ("Q1FY27", "Nifty Smallcap 250", "pat_agg_yoy", 33.9, 42, "value",
     "Aggregate PAT of Nifty Smallcap 250 companies grew by a strong 33.9% YoY in Q1 FY27."),
    ("Q1FY27", "Nifty Smallcap 250", "pat_agg_yoy", 33.9, 29, "check",
     "The segment delivered a robust 33.9% YoY increase in PAT, with median PAT growth of 18.6% YoY in Q1FY27."),
    ("Q1FY27", "Nifty Next 50", "pat_agg_yoy", 4.5, 29, "value",
     "PAT growth for the Nifty Next 50 and Nifty Midcap 150 remained in single digits at 4.5% YoY and 6.1% YoY, respectively, both trailing the Nifty 50."),
    ("Q1FY27", "Nifty Midcap 150", "pat_agg_yoy", 6.1, 29, "value",
     "PAT growth for the Nifty Next 50 and Nifty Midcap 150 remained in single digits at 4.5% YoY and 6.1% YoY, respectively, both trailing the Nifty 50."),
    # Second statements of table figures, kept as cross-checks.
    # The issues' own summaries (page 1), checked against the tables.
    ("Q1FY22", "Nifty 50", "sales_agg_yoy", 41.7, 1, "check",
     "Aggregate net sales grew by a record 41.7%/41.8% YoY in the June quarter for the Nifty 50/Nifty 500 universe"),
    ("Q1FY22", "Nifty 500", "sales_agg_yoy", 41.8, 1, "check",
     "Aggregate net sales grew by a record 41.7%/41.8% YoY in the June quarter for the Nifty 50/Nifty 500 universe"),
    ("Q1FY22", "Nifty 50", "pat_agg_yoy", 104.3, 1, "check",
     "Net adjusted PAT shot up by 104.3%/118.1% YoY but fell by 14.2%/15.1% QoQ for Nifty 50/Nifty 500 universe"),
    ("Q1FY22", "Nifty 500", "pat_agg_yoy", 118.1, 1, "check",
     "Net adjusted PAT shot up by 104.3%/118.1% YoY but fell by 14.2%/15.1% QoQ for Nifty 50/Nifty 500 universe"),
    ("Q3FY22", "Nifty 50", "pat_agg_yoy", 27.0, 1, "check",
     "Net adjusted PAT rose by 27%/25.7 YoY for Nifty 50/Nifty 500 companies"),
    ("Q3FY22", "Nifty 500", "pat_agg_yoy", 25.7, 1, "check",
     "Net adjusted PAT rose by 27%/25.7 YoY for Nifty 50/Nifty 500 companies"),
    ("Q4FY22", "Nifty 50", "sales_agg_yoy", 21.7, 1, "check",
     "Aggregate net sales for Nifty 50/Nifty 500 companies 1 grew by 21.7% YoY in Q4FY22"),
    ("Q4FY22", "Nifty 500", "sales_agg_yoy", 21.7, 1, "check",
     "Aggregate net sales for Nifty 50/Nifty 500 companies 1 grew by 21.7% YoY in Q4FY22"),
    ("Q4FY22", "Nifty 50", "pat_agg_yoy", 22.5, 1, "check",
     "Net adjusted PAT rose by 22.5%/24.6 YoY for Nifty 50/Nifty 500 companies"),
    ("Q4FY22", "Nifty 500", "pat_agg_yoy", 24.6, 1, "check",
     "Net adjusted PAT rose by 22.5%/24.6 YoY for Nifty 50/Nifty 500 companies"),
    ("Q4FY22", "Nifty 50", "pat_agg_yoy", 22.4, 2, "check",
     "a row to 22.4%/24.8% YoY and 7.1%/8.4% QoQ in Q4FY22."),
    ("Q4FY22", "Nifty 500", "pat_agg_yoy", 24.8, 2, "check",
     "a row to 22.4%/24.8% YoY and 7.1%/8.4% QoQ in Q4FY22."),
    ("Q1FY23", "Nifty 50", "sales_agg_yoy", 31.7, 1, "check",
     "Overall net sales for Nifty 50/Nifty 500 companies 1 grew by 31.7%/35.5% YoY"),
    ("Q1FY23", "Nifty 500", "sales_agg_yoy", 35.5, 1, "check",
     "Overall net sales for Nifty 50/Nifty 500 companies 1 grew by 31.7%/35.5% YoY"),
    ("Q1FY23", "Nifty 50", "pat_agg_yoy", 15.4, 1, "check",
     "Aggregate adjusted PAT growth at 15.4%/19% YoY in Q1FY23 for the Nifty 50/Nifty 500 companies"),
    ("Q1FY23", "Nifty 500", "pat_agg_yoy", 19.0, 1, "check",
     "Aggregate adjusted PAT growth at 15.4%/19% YoY in Q1FY23 for the Nifty 50/Nifty 500 companies"),
    ("Q2FY23", "Nifty 50", "sales_agg_yoy", 27.4, 1, "check",
     "Aggregate net sales for Nifty 50/Nifty 500 companies 1 grew by 27.4% YoY"),
    ("Q2FY23", "Nifty 500", "sales_agg_yoy", 27.4, 1, "check",
     "Aggregate net sales for Nifty 50/Nifty 500 companies 1 grew by 27.4% YoY"),
    ("Q2FY23", "Nifty 50", "pat_agg_yoy", -1.8, 1, "check",
     "Aggregate adjusted PAT growth in Q2FY23 for the Nifty 50/Nifty 500 companies was the lowest in last nine quarters at -1.8%/-8.4% YoY."),
    ("Q2FY23", "Nifty 500", "pat_agg_yoy", -8.4, 1, "check",
     "Aggregate adjusted PAT growth in Q2FY23 for the Nifty 50/Nifty 500 companies was the lowest in last nine quarters at -1.8%/-8.4% YoY."),
    ("Q4FY23", "Nifty 50", "sales_agg_yoy", 14.0, 1, "check",
     "The top line growth of Nifty 50/Nifty 500 1 universes slowed to nine-quarter low of 14%/14.5% YoY in Q4FY23"),
    ("Q4FY23", "Nifty 500", "sales_agg_yoy", 14.5, 1, "check",
     "The top line growth of Nifty 50/Nifty 500 1 universes slowed to nine-quarter low of 14%/14.5% YoY in Q4FY23"),
    ("Q4FY23", "Nifty 50", "pat_agg_yoy", 11.1, 1, "check",
     "aggregate adjusted PAT growth for the Nifty 50/Nifty 500 companies expanding 11.1%/10.3% YoY and 9.6%/18.9% QoQ in Q4 FY23."),
    ("Q4FY23", "Nifty 500", "pat_agg_yoy", 10.3, 1, "check",
     "aggregate adjusted PAT growth for the Nifty 50/Nifty 500 companies expanding 11.1%/10.3% YoY and 9.6%/18.9% QoQ in Q4 FY23."),
    ("Q2FY24", "Nifty 50", "sales_agg_yoy", 7.3, 1, "check",
     "The top line growth of Nifty 50/Nifty 500 1 universes slowed to a 11-quarter low of 7.3%/5% YoY in Q2FY24"),
    ("Q2FY24", "Nifty 500", "sales_agg_yoy", 5.0, 1, "check",
     "The top line growth of Nifty 50/Nifty 500 1 universes slowed to a 11-quarter low of 7.3%/5% YoY in Q2FY24"),
    ("Q2FY24", "Nifty 50", "pat_agg_yoy", 36.1, 1, "check",
     "This led to a strong 36.1%/45.2% YoY growth in aggregate adjusted PAT for the Nifty 50/Nifty 500 companies"),
    ("Q2FY24", "Nifty 500", "pat_agg_yoy", 45.2, 1, "check",
     "This led to a strong 36.1%/45.2% YoY growth in aggregate adjusted PAT for the Nifty 50/Nifty 500 companies"),
    ("Q4FY24", "Nifty 50", "sales_agg_yoy", 10.2, 1, "check",
     "Net revenue growth of Nifty50 and Nifty500 companies came in at a steady 10.2% and 9.9% YoY"),
    ("Q4FY24", "Nifty 500", "sales_agg_yoy", 9.9, 1, "check",
     "Net revenue growth of Nifty50 and Nifty500 companies came in at a steady 10.2% and 9.9% YoY"),
    ("Q4FY24", "Nifty 50", "pat_agg_yoy", 21.5, 1, "check",
     "Adjusted net profit growth, however improved sequentially to 21.5% for the Nifty50 companies"),
    ("Q4FY24", "Nifty 500", "pat_agg_yoy", 17.9, 1, "check",
     "while it moderated marginally for the Nifty500 companies to 17.9%"),
    ("Q1FY25", "Nifty 50", "sales_agg_yoy", 9.6, 1, "check",
     "low of 9.6% YoY and 9.4% YoY respectively."),
    ("Q1FY25", "Nifty 500", "sales_agg_yoy", 9.4, 1, "check",
     "low of 9.6% YoY and 9.4% YoY respectively."),
    ("Q1FY25", "Nifty 50", "pat_agg_yoy", 3.3, 1, "check",
     "Aggregate adjusted profit growth, however, declined to a seven-quarter low of 3.3% YoY and 3.7% YoY for Nifty50 and Nifty500 companies"),
    ("Q1FY25", "Nifty 500", "pat_agg_yoy", 3.7, 1, "check",
     "Aggregate adjusted profit growth, however, declined to a seven-quarter low of 3.3% YoY and 3.7% YoY for Nifty50 and Nifty500 companies"),
    ("Q2FY25", "Nifty 50", "sales_agg_yoy", 6.6, 1, "check",
     "Topline growth for Nifty 50 and Nifty 500 companies moderated to a 15-quarter low of 6.6% and a three-quarter low of 8.3% YoY, respectively."),
    ("Q2FY25", "Nifty 500", "sales_agg_yoy", 8.3, 1, "check",
     "Topline growth for Nifty 50 and Nifty 500 companies moderated to a 15-quarter low of 6.6% and a three-quarter low of 8.3% YoY, respectively."),
    ("Q2FY25", "Nifty 50", "pat_agg_yoy", 0.8, 1, "check",
     "Adjusted PAT growth fell to an eight-quarter low of 0.8% YoY for Nifty 50 and -4.1% YoY for Nifty 500."),
    ("Q2FY25", "Nifty 500", "pat_agg_yoy", -4.1, 1, "check",
     "Adjusted PAT growth fell to an eight-quarter low of 0.8% YoY for Nifty 50 and -4.1% YoY for Nifty 500."),
    ("Q3FY25", "Nifty 50", "sales_agg_yoy", 4.5, 1, "check",
     "hitting a 16-quarter low for Nifty 50 (4.5% YoY) and a five-quarter low for Nifty 500 (4.6% YoY)."),
    ("Q3FY25", "Nifty 500", "sales_agg_yoy", 4.6, 1, "check",
     "hitting a 16-quarter low for Nifty 50 (4.5% YoY) and a five-quarter low for Nifty 500 (4.6% YoY)."),
    ("Q3FY25", "Nifty 50", "pat_agg_yoy", 9.5, 1, "check",
     "PAT rebounded, reaching a three-quarter high of 9.5% YoY for Nifty 50 and a four-quarter high of 11.1% YoY for Nifty 500,"),
    ("Q3FY25", "Nifty 500", "pat_agg_yoy", 11.1, 1, "check",
     "PAT rebounded, reaching a three-quarter high of 9.5% YoY for Nifty 50 and a four-quarter high of 11.1% YoY for Nifty 500,"),
    ("Q4FY25", "Nifty 50", "sales_agg_yoy", 6.4, 1, "check",
     "with Nifty 50 and Nifty 500 companies posting YoY growth of 6.4% and 5.7%, respectively"),
    ("Q4FY25", "Nifty 500", "sales_agg_yoy", 5.7, 1, "check",
     "with Nifty 50 and Nifty 500 companies posting YoY growth of 6.4% and 5.7%, respectively"),
    ("Q4FY25", "Nifty 50", "pat_agg_yoy", 0.8, 1, "check",
     "Nifty 50 PAT rose just 0.8% YoY"),
    ("Q4FY25", "Nifty 500", "pat_agg_yoy", 9.5, 1, "check",
     "In contrast, Nifty 500 PAT expanded 9.5% YoY"),
    ("Q1FY26", "Nifty 50", "sales_agg_yoy", 6.2, 1, "check",
     "Nifty 50 companies posted revenue growth of 6.2% YoY"),
    ("Q1FY26", "Nifty 500", "sales_agg_yoy", 5.9, 1, "check",
     "Nifty 500 companies recorded a slightly lower yet stable growth of 5.9% YoY."),
    ("Q1FY26", "Nifty 50", "pat_agg_yoy", 14.8, 1, "check",
     "aggregate PAT growth for Nifty 50 and Nifty 500 companies returned to a double-digit trajectory at 14.8% and 13.2% YoY, respectively."),
    ("Q1FY26", "Nifty 500", "pat_agg_yoy", 13.2, 1, "check",
     "aggregate PAT growth for Nifty 50 and Nifty 500 companies returned to a double-digit trajectory at 14.8% and 13.2% YoY, respectively."),
    ("Q2FY26", "Nifty 50", "sales_agg_yoy", 7.0, 1, "check",
     "Nifty 50 net sales (ex-Tata Motors) grew 7% YoY in Q2FY26"),
    ("Q2FY26", "Nifty 50", "pat_agg_yoy", 7.9, 1, "check",
     "Nifty 50 profits rose 7.9% YoY"),
    ("Q2FY26", "Nifty 500", "sales_agg_yoy", 6.6, 1, "check",
     "topline growth improved to a four/six quarter high of 6.6% YoY"),
    ("Q3FY26", "Nifty 50", "sales_agg_yoy", 12.5, 1, "check",
     "Nifty 50 net sales (ex-Tata Motors) rose 12.5% YoY in Q3 FY26"),
    ("Q3FY26", "Nifty 500", "sales_agg_yoy", 11.1, 1, "check",
     "The broader Nifty 500 also delivered 11.1% YoY revenue growth"),
    ("Q3FY26", "Nifty 50", "pat_agg_yoy", 12.8, 1, "check",
     "Nifty 50 aggregate PAT increased 12.8% YoY and 10.6% QoQ"),
    ("Q1FY27", "Nifty 500", "pat_agg_yoy", 11.1, 29, "check",
     "Aggregate PAT of Nifty 500 companies rose 11.1% YoY to Rs. 4.67 lakh crore in Q1FY27,"),
    ("Q1FY27", "Nifty 500", "sales_agg_yoy", 18.9, 1, "check",
     "Net sales of Nifty 500 universe was marginally better at 18.9% YoY"),
    ("Q1FY27", "Nifty 50", "sales_median_yoy", 16.8, 19, "check",
     "Median YoY revenue growth stood at 16.8% for Nifty 50 companies and 17.1% for Nifty 500 companies,"),
    ("Q1FY27", "Nifty 500", "sales_median_yoy", 17.1, 19, "check",
     "Median YoY revenue growth stood at 16.8% for Nifty 50 companies and 17.1% for Nifty 500 companies,"),
    ("Q1FY27", "Nifty Midcap 150", "sales_median_yoy", 17.2, 19, "check",
     "while Nifty Midcap 150 and Nifty Smallcap 250 recorded a slightly higher median growth of 17.2%."),
    ("Q1FY27", "Nifty Smallcap 250", "sales_median_yoy", 17.2, 19, "check",
     "while Nifty Midcap 150 and Nifty Smallcap 250 recorded a slightly higher median growth of 17.2%."),
    ("Q1FY27", "Nifty Smallcap 250", "pat_median_yoy", 18.6, 29, "check",
     "The segment delivered a robust 33.9% YoY increase in PAT, with median PAT growth of 18.6% YoY in Q1FY27."),
    ("Q1FY27", "Nifty Next 50", "pat_median_yoy", 16.3, 29, "check",
     "median PAT growth for these cohorts was relatively stronger at 16.3% YoY and 20.1% YoY,"),
    ("Q1FY27", "Nifty Midcap 150", "pat_median_yoy", 20.1, 29, "check",
     "median PAT growth for these cohorts was relatively stronger at 16.3% YoY and 20.1% YoY,"),
    ("Q3FY26", "Nifty 50", "sales_median_yoy", 11.1, 24, "check",
     "For the Nifty 50, it rose from 10% to 11.1%; for the Nifty Next 50, from 8.4% to 11.6%."),
    ("Q3FY26", "Nifty Next 50", "sales_median_yoy", 11.6, 24, "check",
     "For the Nifty 50, it rose from 10% to 11.1%; for the Nifty Next 50, from 8.4% to 11.6%."),
    ("Q3FY26", "Nifty Midcap 150", "sales_median_yoy", 11.8, 24, "check",
     "median growth for the Nifty Midcap 150 increasing from 10.3% to 11.8%, and for the Nifty Smallcap 250 from 9.8% to 12.5%."),
    ("Q3FY26", "Nifty Smallcap 250", "sales_median_yoy", 12.5, 24, "check",
     "median growth for the Nifty Midcap 150 increasing from 10.3% to 11.8%, and for the Nifty Smallcap 250 from 9.8% to 12.5%."),
    ("Q3FY26", "Nifty Next 50", "pat_median_yoy", 13.0, 38, "check",
     "the Nifty Next 50 accounted for 48% of the YoY PAT expansion, with median growth of 13%."),
    ("Q3FY26", "Nifty Midcap 150", "pat_median_yoy", 19.1, 38, "check",
     "contributed the remaining 52%, delivering median growth of 19.1% and 21.8%, respectively."),
    ("Q3FY26", "Nifty Smallcap 250", "pat_median_yoy", 21.8, 38, "check",
     "contributed the remaining 52%, delivering median growth of 19.1% and 21.8%, respectively."),
    ("Q2FY26", "Nifty 50", "sales_median_yoy", 10.0, 23, "check",
     "Median revenue growth strengthened for Nifty 50 and Nifty Smallcap companies in Q2, rising to 10% and 9.8% YoY"),
    ("Q2FY26", "Nifty Smallcap 250", "sales_median_yoy", 9.8, 23, "check",
     "Median revenue growth strengthened for Nifty 50 and Nifty Smallcap companies in Q2, rising to 10% and 9.8% YoY"),
    ("Q2FY26", "Nifty 500", "sales_median_yoy", 10.0, 23, "check",
     "leaving the overall median revenue growth for the Nifty 500 universe at 10% in Q2,"),
    ("Q2FY26", "Nifty 500", "pat_median_yoy", 12.2, 36, "check",
     "the Nifty 500 median stood at 12.2%, compared with a stronger 15.8% for Midcaps and a softer 9.3% for Smallcaps."),
    ("Q2FY26", "Nifty Midcap 150", "pat_median_yoy", 15.8, 36, "check",
     "the Nifty 500 median stood at 12.2%, compared with a stronger 15.8% for Midcaps and a softer 9.3% for Smallcaps."),
    ("Q2FY26", "Nifty Smallcap 250", "pat_median_yoy", 9.3, 36, "check",
     "the Nifty 500 median stood at 12.2%, compared with a stronger 15.8% for Midcaps and a softer 9.3% for Smallcaps."),
    ("Q1FY26", "Nifty 500", "sales_median_yoy", 9.2, 18, "check",
     "The overall Nifty 500 median net sales growth stood at 9.2% YoY, with Nifty Midcap 150 companies leading at a median growth rate of 10.7% YoY."),
    ("Q1FY26", "Nifty Midcap 150", "sales_median_yoy", 10.7, 18, "check",
     "The overall Nifty 500 median net sales growth stood at 9.2% YoY, with Nifty Midcap 150 companies leading at a median growth rate of 10.7% YoY."),
    ("Q1FY26", "Nifty Midcap 150", "pat_median_yoy", 11.9, 29, "check",
     "The median YoY PAT growth for the Nifty Midcap 150 stood at a robust 11.9% YoY, outpacing the Nifty 50 (9.9% YoY) and the overall Nifty 500 (9.2% YoY)."),
    ("Q1FY26", "Nifty 50", "pat_median_yoy", 9.9, 29, "check",
     "The median YoY PAT growth for the Nifty Midcap 150 stood at a robust 11.9% YoY, outpacing the Nifty 50 (9.9% YoY) and the overall Nifty 500 (9.2% YoY)."),
    ("Q1FY26", "Nifty 500", "pat_median_yoy", 9.2, 29, "check",
     "The median YoY PAT growth for the Nifty Midcap 150 stood at a robust 11.9% YoY, outpacing the Nifty 50 (9.9% YoY) and the overall Nifty 500 (9.2% YoY)."),
    ("Q1FY26", "Nifty Next 50", "pat_median_yoy", 5.9, 29, "check",
     "the Nifty Next 50 and Nifty Smallcap 250 posted more modest median PAT growth rates of 5.9% YoY and 5.3% YoY, respectively"),
    ("Q1FY26", "Nifty Smallcap 250", "pat_median_yoy", 5.3, 29, "check",
     "the Nifty Next 50 and Nifty Smallcap 250 posted more modest median PAT growth rates of 5.9% YoY and 5.3% YoY, respectively"),
]

MONTHS = {"Jun": 1, "Sep": 2, "Dec": 3, "Mar": 4}
MONTH_RE = re.compile(r"\b(Jun|Sep|Dec|Mar)-(\d{2})\b")
TOC_RE = re.compile(r"\.{3,}\s*\d+\s*$")   # a contents-page line: "... caption ......34"
NUM_RE = re.compile(r"\(\s*-?[\d,]*\.?\d+\s*\)|-?[\d,]*\.?\d+")


def month_quarter(label: str) -> str:
    """'Sep-23' -> 'Q2FY24'; 'Mar-26' -> 'Q4FY26'."""
    m = MONTH_RE.fullmatch(label.strip())
    if not m:
        raise ValueError(label)
    q, yy = MONTHS[m.group(1)], int(m.group(2))
    return f"Q{q}FY{yy if q == 4 else yy + 1:02d}"


def number(tok: str) -> float:
    """'(2.3)' -> -2.3, '1,234.5' -> 1234.5."""
    t = tok.replace(",", "").strip()
    if t.startswith("("):
        return -float(t.strip("() "))
    return float(t)


def squash(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def pages(pdf: str) -> list[str]:
    """The PDF's text, one string per page (pdftotext -layout separates pages with a form feed)."""
    out = subprocess.run(["pdftotext", "-layout", pdf, "-"], capture_output=True, text=True, check=True).stdout
    return out.split("\f")


def _captions(pgs: list[str], pattern: str):
    """(page number, line index, lines) for each table caption matching pattern; lines are that page's and the
    next page's, so a table that runs over the page break is read whole. A line at index >= the page's own line
    count is on the next page (see _page_of)."""
    rx = re.compile(r"^\s*Table\s+\d+\s*:\s*" + pattern, re.I)
    for pi, page in enumerate(pgs):
        lines = page.splitlines()
        for li, line in enumerate(lines):
            if rx.search(line) and not TOC_RE.search(line):
                following = lines + (pgs[pi + 1].splitlines() if pi + 1 < len(pgs) else [])
                yield pi + 1, li, following


def _page_of(pgs: list[str], page: int, line_index: int) -> int:
    return page if line_index < len(pgs[page - 1].splitlines()) else page + 1


AGG_TABLES = [
    ("sales_agg_yoy", "Nifty 50", r"(Sector-wise\s+)?net sales growth\s*(\(%\)\s*)?of Nifty 50 companies"),
    ("pat_agg_yoy", "Nifty 50", r"(Sector-wise\s+)?PAT growth\s*(\(%\)\s*)?of Nifty 50 companies"),
    ("sales_agg_yoy", "Nifty 500", r"(Sector-wise\s+)?net sales growth\s*(\(%\)\s*)?of Nifty 500 companies(?!\s*\(ex)"),
    ("pat_agg_yoy", "Nifty 500", r"(Sector-wise\s+)?PAT growth\s*(\(%\)\s*)?of Nifty 500 companies(?!\s*\(ex)"),
]
# Rows some tables add beside the index row; their YoY figure goes into the quote, as a different basis.
COMPANION_ROWS = ("ex-Tata Motors", "excl HDFCBK")
# Quarters whose aggregate is read from the index's "ex-Tata Motors" row (owner, 25 Nov 2026: Q3 FY26 excludes
# Tata Motors, demerged 1 Oct 2025, as Q2 FY26's index row already does and as NSE's own summary reports it).
EX_TATA_QUARTERS = frozenset({"Q3FY26"})


def _index_row(window: list[str], label: str) -> tuple[int, list[str]] | None:
    rx = re.compile(r"^\s*" + re.escape(label) + r"\s{2,}(?=[\d(-])")
    for i, w in enumerate(window):
        m = rx.match(w)
        if m:
            nums = NUM_RE.findall(w[m.end():])
            if len(nums) >= 6:
                return i, nums
    return None


def aggregate_rows(issue: str, pgs: list[str]) -> list[dict]:
    """The index row of the sector-wise growth tables: YoY for the issue's quarter (and for the quarter before,
    when that quarter has no issue of its own)."""
    out = []
    for measure, index, pattern in AGG_TABLES:
        found = False
        for page, li, lines in _captions(pgs, pattern):
            caption = squash(lines[li])
            end = next((j for j in range(li + 1, min(li + 45, len(lines)))
                        if re.match(r"^\s*(Table|Figure)\s+\d+", lines[j])), min(li + 45, len(lines)))
            window = lines[li + 1: end]
            header = next((w for w in window if len(MONTH_RE.findall(w)) >= 6), None)
            hit = _index_row(window, index)
            if header is None or hit is None:
                continue
            pos, nums = hit
            months = ["-".join(m) for m in MONTH_RE.findall(header)][:6]
            if month_quarter(months[5]) != issue:
                raise ValueError(f"{issue} {caption}: last YoY column is {months[5]}")
            notes = [squash(w) for w in window[pos:] if re.search(r"exclud|as on|as of", w, re.I)][:2]
            base = (f"{caption} | YoY columns {' '.join(months[3:6])} | row: {squash(window[pos])}"
                    + "".join(f" | {n}" for n in notes))
            for col, quarter in ((5, issue), (4, month_quarter(months[4]))):
                if col == 4 and quarter not in GAPS:
                    continue   # the previous quarter is kept only where it has no issue of its own
                value, row_pos = number(nums[col]), pos
                ex = _index_row(window, f"{index} ex-Tata Motors") if quarter in EX_TATA_QUARTERS else None
                if quarter in EX_TATA_QUARTERS and ex is None:
                    raise ValueError(f"{issue} {caption}: no '{index} ex-Tata Motors' row for {quarter}")
                if ex is not None:
                    value, row_pos = number(ex[1][col]), ex[0]
                    quote = (base + f" | value: YoY {months[col]} from the row '{squash(window[ex[0]])}' (ex-Tata Motors,"
                             f" owner 25 Nov 2026); the index row with Tata Motors gives {number(nums[col]):g}")
                else:
                    quote = base + f" | value: YoY {months[col]}"
                    for extra in COMPANION_ROWS:
                        other = _index_row(window, f"{index} {extra}")
                        if other:
                            quote += f" | the table's '{index} {extra}' row gives {number(other[1][col]):g} for {months[col]}"
                out.append({"quarter": quarter, "index": index, "measure": measure, "value_pct": value,
                            "source": "table" if quarter == issue else "table, later issue", "issue": issue,
                            "page": _page_of(pgs, page, li + 1 + row_pos), "quote": quote})
            found = True
            break
        if not found:
            raise ValueError(f"{issue}: no '{pattern}' table with a {index} row")
    return out


MEDIAN_TABLES = [
    ("sales_median_yoy", r"Segment-wise distribution of companies based on YoY aggregate and median topline growth"),
    ("pat_median_yoy", r"Segment-wise distribution of companies based on YoY aggregate and median PAT growth"),
]


def median_rows(issue: str, pgs: list[str]) -> list[dict]:
    """The Median column of the segment-wise distribution tables (Q1 FY26 issue on)."""
    out = []
    for measure, pattern in MEDIAN_TABLES:
        for page, li, lines in _captions(pgs, pattern):
            caption = squash(lines[li])
            if lines[li + 1].strip().lower().startswith("500 constituents"):
                caption += " " + squash(lines[li + 1])
            got = {}
            for j in range(li + 1, min(li + 20, len(lines))):
                for index in INDICES:
                    m = re.match(r"^\s*" + re.escape(index) + r"\s{2,}((?:\d+\s+){7})(-?\d+(?:\.\d+)?)%\s*$", lines[j])
                    if m and index not in got:
                        got[index] = (float(m.group(2)), squash(lines[j]), _page_of(pgs, page, j))
            note = next((squash(w) for w in lines[li + 1: li + 20] if w.strip().startswith("Note:")), "")
            named = re.search(r"\bin (Q[1-4]FY\d{2})\b", caption)
            if got and named and named.group(1) != issue:
                # Q1 FY27's Table 13 is captioned "in Q3FY26"; its note dates it to the issue's own quarter end.
                end_month = {1: "June", 2: "September", 3: "December", 4: "March"}[int(issue[1])]
                end_year = 2000 + int(issue[4:]) - (0 if issue[1] == "4" else 1)
                if not re.search(rf"{end_month} \d+\w*, {end_year}", note):
                    raise ValueError(f"{issue}: '{caption}' names {named.group(1)} and its note does not date it")
                caption += (f" [caption says {named.group(1)}; the note dates the data {end_month} {end_year},"
                            f" the {issue} quarter end]")
            for index, (v, row, row_page) in got.items():
                out.append({"quarter": issue, "index": index, "measure": measure, "value_pct": v, "source": "table",
                            "issue": issue, "page": row_page,
                            "quote": f"{caption} | columns <=0% 0-10% 10-20% 20-30% 30-40% 40-50% >50% Median"
                                     f" | row: {row}" + (f" | {note}" if note else "")})
            if got:
                break
    return out


def iqr_rows(issue: str, pgs: list[str], wanted: set[str]) -> list[dict]:
    """Nifty 500 medians from the 'Interquartile range across performance parameters' table (Q4 FY23, Q2 FY24):
    revenue growth 50% (2nd number) and PAT growth 50% (8th number), for the quarters in `wanted`."""
    out = []
    for page, li, lines in _captions(pgs, r"Interquartile range across performance parameters"):
        caption = squash(lines[li])
        heading = next((squash(w) for w in reversed(pgs[page - 1].splitlines()[:li])
                        if "distribution analysis of Nifty 500" in w), None)
        if heading is None:
            raise ValueError(f"{issue}: interquartile table not under the Nifty 500 heading")
        for j in range(li + 1, min(li + 30, len(lines))):
            w = lines[j]
            m = re.match(r"^\s*((?:Jun|Sep|Dec|Mar)-\d{2})\s+(.*)$", w)
            if not m:
                continue
            nums = NUM_RE.findall(m.group(2))
            quarter = month_quarter(m.group(1))
            if len(nums) != 15 or quarter not in wanted:
                continue
            for measure, col, name in (("sales_median_yoy", 1, "Revenue Growth (%YoY) 50%"),
                                       ("pat_median_yoy", 7, "PAT Growth (%YoY) 50%")):
                out.append({"quarter": quarter, "index": "Nifty 500", "measure": measure,
                            "value_pct": number(nums[col]),
                            "source": "table" if quarter == issue else "table, later issue", "issue": issue,
                            "page": _page_of(pgs, page, j),
                            "quote": f"{heading} | {caption} | columns 25% 50% 75% for Revenue, EBITDA, PAT growth,"
                                     f" EBITDA, PAT margin | row: {squash(w)} | value: {name}"})
        break
    return out


def prose_rows(issue: str, pgs: list[str]) -> list[dict]:
    """The PROSE sentences of this issue, each checked against its page."""
    out = []
    for q, index, measure, value, page, role, sentence in PROSE:
        if q != issue:
            continue
        text = squash(pgs[page - 1]) if page <= len(pgs) else ""
        if squash(sentence) not in text:
            raise ValueError(f"{issue} p{page}: sentence not found: {sentence!r}")
        if not re.search(r"(?<![\d.])" + re.escape(f"{value:g}") + r"(?!\d|\.\d)", sentence):
            raise ValueError(f"{issue} p{page}: {value}% is not in {sentence!r}")
        out.append({"quarter": issue, "index": index, "measure": measure, "value_pct": value, "source": "prose",
                    "issue": issue, "page": page, "quote": sentence, "role": role})
    return out


def assemble(by_issue: dict[str, list[dict]]) -> tuple[list[dict], list[str]]:
    """One row per (quarter, index, measure). An issue's own table beats its prose; a quarter's own issue beats a
    later one. Every other statement of the same figure in the same issue goes to cross_check; differences are
    also returned as conflicts."""
    best: dict[tuple, dict] = {}
    checks: dict[tuple, list[dict]] = {}
    rank = {"table": 0, "prose": 1, "table, later issue": 2}
    for rows in by_issue.values():
        for r in rows:
            key = (r["quarter"], r["index"], r["measure"])
            if r.get("role") in ("check", "basis"):
                checks.setdefault(key, []).append(r)
                continue
            if r["source"] == "table, later issue" and r["quarter"] in ISSUES:
                continue       # the quarter has its own issue
            cur = best.get(key)
            if cur is None or rank[r["source"]] < rank[cur["source"]]:
                if cur is not None and cur["issue"] == r["issue"]:
                    checks.setdefault(key, []).append(cur)
                best[key] = r
            elif cur["issue"] == r["issue"]:
                checks.setdefault(key, []).append(r)
    conflicts = []
    for key, r in best.items():
        notes = []
        for c in checks.get(key, []):
            if c["issue"] != r["issue"]:
                continue
            if c.get("role") == "basis":
                notes.append(f"p{c['page']} {c['source']} gives {c['value_pct']:g} on another basis: {c['quote']}")
            elif abs(c["value_pct"] - r["value_pct"]) < 1e-9:
                notes.append(f"p{c['page']} {c['source']} agrees")
            else:
                notes.append(f"p{c['page']} {c['source']} says {c['value_pct']:g}: {c['quote']}")
                conflicts.append(f"{' '.join(key)}: p{r['page']} {r['source']} {r['value_pct']:g} vs "
                                 f"p{c['page']} {c['source']} {c['value_pct']:g}")
        r["cross_check"] = "; ".join(notes)
    order = {q: i for i, q in enumerate(sorted(set(ISSUES) | set(GAPS), key=lambda q: (q[4:], q[:2])))}
    rows = sorted(best.values(), key=lambda r: (order.get(r["quarter"], 99), INDICES.index(r["index"]),
                                                MEASURES.index(r["measure"])))
    for r in rows:
        url, published = ISSUES[r["issue"]]
        r["pdf_url"], r["published"] = url, published
    return [{c: r.get(c, "") for c in COLUMNS} for r in rows], conflicts


def parse_issue(issue: str, pgs: list[str]) -> list[dict]:
    rows = aggregate_rows(issue, pgs) + median_rows(issue, pgs) + prose_rows(issue, pgs)
    rows += iqr_rows(issue, pgs, {issue} | set(GAPS))
    return rows


def download(raw: str) -> None:
    os.makedirs(raw, exist_ok=True)
    for quarter, (url, _) in ISSUES.items():
        dest = os.path.join(raw, quarter + ".pdf")
        if os.path.exists(dest) and os.path.getsize(dest) > 10000:
            continue
        for attempt in range(3):
            r = subprocess.run(["curl", "-sS", "-m", "120", "-A", USER_AGENT, "-o", dest + ".tmp",
                                "-w", "%{http_code}", url], capture_output=True, text=True)
            if r.stdout.strip() == "200" and os.path.exists(dest + ".tmp"):
                with open(dest + ".tmp", "rb") as f:
                    if f.read(5) == b"%PDF-":
                        os.replace(dest + ".tmp", dest)
                        print(quarter, "saved", os.path.getsize(dest))
                        break
            time.sleep(3 * (attempt + 1))
        else:
            print(quarter, "FAILED", r.stdout.strip(), r.stderr.strip(), file=sys.stderr)


def build(raw: str, out: str) -> list[str]:
    by_issue = {}
    for issue in ISSUES:
        by_issue[issue] = parse_issue(issue, pages(os.path.join(raw, issue + ".pdf")))
    rows, conflicts = assemble(by_issue)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({**r, "value_pct": f"{r['value_pct']:g}"})
    have = {r["quarter"] for r in rows}
    print(f"{len(rows)} rows, {len(have)} quarters -> {out}")
    for q, why in GAPS.items():
        print(f"gap {q}: {why}")
    for c in conflicts:
        print("CONFLICT", c)
    return conflicts


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--mode", choices=["download", "build"], required=True)
    ap.add_argument("--raw", required=True, help="scratch directory for the PDFs, outside the repository")
    ap.add_argument("--out", default="data/reference/nse_earnings_review.csv")
    a = ap.parse_args()
    if a.mode == "download":
        download(a.raw)
    else:
        build(a.raw, a.out)


if __name__ == "__main__":
    main()
