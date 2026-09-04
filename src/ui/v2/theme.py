"""Minimal v2 visual system. No legacy theme dependency."""

import streamlit as st


CSS = """
<style>
:root { color-scheme: light; }
[data-testid="stAppViewContainer"] { background:#f5f7fa; }
[data-testid="stHeader"] { background:rgba(245,247,250,.92); }
[data-testid="stMainBlockContainer"] { max-width:1540px; padding-top:1rem; padding-left:1.4rem; padding-right:1.4rem; }
section[data-testid="stSidebar"] { display:none; }
.block-container { padding-bottom:3rem; }
.v2-brand { display:flex; align-items:center; gap:12px; margin-bottom:8px; }
.v2-mark { width:34px; height:34px; border-radius:9px; background:#3157d5; color:white; display:flex; align-items:center; justify-content:center; font-weight:900; font-family:Arial,sans-serif; }
.v2-brand-name { font:800 1.08rem/1.1 Arial,sans-serif; color:#101828; letter-spacing:-.02em; }
.v2-brand-sub { font:500 .68rem/1.1 Arial,sans-serif; color:#667085; margin-top:3px; }
.v2-page-title { font:800 1.55rem/1.1 Arial,sans-serif; color:#101828; letter-spacing:-.025em; }
.v2-page-sub { color:#667085; font:500 .78rem/1.35 Arial,sans-serif; margin-top:4px; }
.v2-strip { display:flex; align-items:center; gap:0; overflow-x:auto; white-space:nowrap; background:#fff; border:1px solid #e4e7ec; border-radius:12px; margin:10px 0 14px; box-shadow:0 1px 2px rgba(16,24,40,.03); }
.v2-strip-item { padding:9px 15px; border-right:1px solid #eaecf0; }
.v2-strip-label { color:#667085; font:700 .58rem/1 Arial,sans-serif; text-transform:uppercase; letter-spacing:.07em; }
.v2-strip-value { color:#101828; font:800 .78rem/1.2 'JetBrains Mono',monospace; margin-top:4px; }
.v2-card { background:#fff; border:1px solid #e4e7ec; border-radius:14px; padding:14px; box-shadow:0 1px 2px rgba(16,24,40,.03); }
.v2-section { color:#101828; font:800 .78rem/1 Arial,sans-serif; text-transform:uppercase; letter-spacing:.06em; margin:16px 0 8px; }
.v2-muted { color:#667085; }
.v2-mono { font-family:'JetBrains Mono',monospace; }
.v2-stock-card { background:#fff; border:1px solid #e4e7ec; border-radius:14px; padding:14px; margin-bottom:9px; }
.v2-stock-top { display:flex; justify-content:space-between; gap:10px; }
.v2-rank { color:#3157d5; font:800 .72rem/1 'JetBrains Mono',monospace; }
.v2-symbol { color:#101828; font:900 1rem/1.1 Arial,sans-serif; }
.v2-industry { color:#667085; font:500 .66rem/1.2 Arial,sans-serif; margin-top:3px; }
.v2-price { color:#101828; font:800 .95rem/1 'JetBrains Mono',monospace; text-align:right; }
.v2-delta-pos { color:#087443; font:700 .65rem/1 'JetBrains Mono',monospace; text-align:right; margin-top:4px; }
.v2-delta-neg { color:#c43232; font:700 .65rem/1 'JetBrains Mono',monospace; text-align:right; margin-top:4px; }
.v2-badges { display:flex; flex-wrap:wrap; gap:5px; margin:10px 0; }
.v2-badge { display:inline-block; padding:3px 7px; border-radius:6px; background:#f2f4f7; border:1px solid #eaecf0; color:#475467; font:700 .59rem/1 'JetBrains Mono',monospace; }
.v2-badge-good { background:#ecfdf3; border-color:#abefc6; color:#067647; }
.v2-badge-warn { background:#fffaeb; border-color:#fedf89; color:#b54708; }
.v2-score { display:flex; align-items:center; gap:8px; }
.v2-score-track { flex:1; height:5px; background:#eaecf0; border-radius:10px; overflow:hidden; }
.v2-score-fill { height:100%; background:#3157d5; border-radius:10px; }
.v2-score-text { color:#475467; font:700 .62rem/1 'JetBrains Mono',monospace; }
.v2-metrics { display:grid; grid-template-columns:repeat(4,1fr); gap:6px; margin-top:10px; }
.v2-metric { border-top:1px solid #f0f2f5; padding-top:7px; }
.v2-metric-label { color:#98a2b3; font:700 .55rem/1 Arial,sans-serif; text-transform:uppercase; letter-spacing:.04em; }
.v2-metric-value { color:#101828; font:800 .68rem/1.2 'JetBrains Mono',monospace; margin-top:3px; }
.v2-detail-hero { background:#fff; border:1px solid #e4e7ec; border-radius:16px; padding:18px; }
.v2-detail-symbol { color:#101828; font:900 1.75rem/1 Arial,sans-serif; }
.v2-detail-meta { color:#667085; font:500 .72rem/1.3 Arial,sans-serif; margin-top:5px; }
.v2-big-number { color:#101828; font:900 1.6rem/1 'JetBrains Mono',monospace; }
.v2-grid2 { display:grid; grid-template-columns:1fr 1fr; gap:10px; }
.v2-grid3 { display:grid; grid-template-columns:repeat(3,1fr); gap:10px; }
.v2-table-note { color:#667085; font:500 .66rem/1.3 Arial,sans-serif; margin:5px 0 7px; }
@media (max-width: 760px) {
 [data-testid="stMainBlockContainer"] { padding-left:.75rem; padding-right:.75rem; }
 .v2-page-title { font-size:1.3rem; }
 .v2-grid2,.v2-grid3 { grid-template-columns:1fr; }
 .v2-metrics { grid-template-columns:repeat(2,1fr); }
 .v2-strip-item { padding:8px 11px; }
}
</style>
"""


def inject() -> None:
    st.html(CSS)
