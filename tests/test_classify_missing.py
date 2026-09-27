"""Filling in sectors: TradingView first, Screener.in mapped onto TradingView's names."""

import pandas as pd

from scripts import classify_missing as cm


class _Resp:
    def __init__(self, payload=None, text="", status=200):
        self._p, self.text, self.status_code = payload, text, status

    def json(self):
        return self._p

    def raise_for_status(self):
        pass


def test_tradingview_answers_in_its_own_taxonomy_and_hyphens_round_trip():
    seen = {}

    def post(url, json, timeout, headers):
        seen["tickers"] = json["symbols"]["tickers"]
        return _Resp({"data": [
            {"s": "NSE:BAJAJ_AUTO", "d": ["BAJAJ_AUTO", "Consumer Durables", "Motor Vehicles"]},
            {"s": "NSE:ODD", "d": ["ODD", "Not A Sector", "x"]},
        ]})

    got = cm.from_tradingview(["BAJAJ-AUTO", "ODD"], post=post)
    assert seen["tickers"] == ["NSE:BAJAJ_AUTO", "NSE:ODD"]
    assert got == {"BAJAJ-AUTO": ("Consumer Durables", "Motor Vehicles")}


def test_screener_sector_maps_to_a_tradingview_sector():
    html = ('<a title="Broad Sector">Consumer Discretionary</a>'
            '<a title="Sector">Consumer Durables</a>'
            '<a title="Industry">Household Appliances</a>')
    assert cm.parse_screener(html) == ("Consumer Durables", "Household Appliances")
    assert cm.parse_screener('<a title="Sector">Something New</a>') is None
    assert set(cm.SCREENER_TO_TV.values()) <= cm.TV_SECTORS


def test_targets_are_unclassified_nano_rows_and_foreign_sector_names():
    cls = pd.DataFrame({"Symbol": ["ABB", "XYZ"], "TV_Sector": ["Producer Manufacturing", "Capital Goods"],
                        "TV_Industry": ["a", "b"]})
    nano = pd.DataFrame({"Symbol": ["NEW", "OLD"], "Industry": ["Unclassified", "Finance"]})
    assert cm.targets(cls, nano) == ["NEW", "XYZ"]
