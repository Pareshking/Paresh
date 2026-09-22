from src.core.tickers import is_tradeable_symbol


def test_dummy_symbols_are_not_tradeable():
    for symbol in ("DUMMY", "DUMMYTRVN", " dummyfoo ", "dummyxyz"):
        assert is_tradeable_symbol(symbol) is False


def test_real_symbols_remain_tradeable():
    for symbol in ("RELIANCE", "CASTROLIND", "NIFTYBEES"):
        assert is_tradeable_symbol(symbol) is True
