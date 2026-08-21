# config_correlations.py

CORRELATION_MATRIX = {
    # ------------------ GPW (POLSKA) ------------------
    "KGH.WA": {
        "nazwa": "KGHM Polska Miedź",
        "drivery": {
            "Miedź (Futures)": "HG=F",
            "Srebro (Futures)": "SI=F",
            "Kurs USD/PLN": "PLN=X",
            "WIG20": "WIG20.WA",
        },
        "opis": "Kluczowe: Ceny surowców (miedź, srebro), kurs USD (przychody w USD) oraz szeroki rynek GPW."
    },
    "PKN.WA": {
        "nazwa": "Orlen",
        "drivery": {
            "Ropa Brent": "BZ=F",
            "Gaz Ziemny": "NG=F",
            "Kurs USD/PLN": "PLN=X",
            "WIG20": "WIG20.WA",
        },
        "opis": "Kluczowe: Marże rafineryjne powiązane z cenami ropy Brent i gazu oraz relacja USD/PLN."
    },
    "CDR.WA": {
        "nazwa": "CD Projekt",
        "drivery": {
            "Kurs USD/PLN": "PLN=X",
            "Nasdaq 100": "^IXIC",
            "WIG20": "WIG20.WA",
        },
        "opis": "Kluczowe: Sprzedaż gier w USD/EUR (kurs walutowy) oraz sentyment do sektora tech/gaming."
    },
    "PKO.WA": {
        "nazwa": "PKO BP",
        "drivery": {
            "WIG20": "WIG20.WA",
            "Kurs EUR/PLN": "EURPLN=X",
            "Rentowności USA 10Y": "^TNX",
        },
        "opis": "Kluczowe: Koniunktura sektora bankowego, stopy procentowe i indeks WIG20."
    },
    "JSW.WA": {
        "nazwa": "JSW",
        "drivery": {
            "WIG20": "WIG20.WA",
            "Gaz Ziemny": "NG=F",
            "Kurs USD/PLN": "PLN=X",
        },
        "opis": "Kluczowe: Ceny węgla koksowego/energii, kurs dolara i sentyment na GPW."
    },

    # ------------------ US TECH / BIG TECH ------------------
    "NVDA": {
        "nazwa": "NVIDIA",
        "drivery": {
            "Rentowności Obligacji USA 10Y": "^TNX",
            "Nasdaq 100 ETF (QQQ)": "QQQ",
            "Indeks Strachu (VIX)": "^VIX",
            "Indeks Dolara (DXY)": "DX-Y.NYB",
        },
        "opis": "Kluczowe: Koszt kapitału (stopy/TNX), popyt na AI/chipy i ogólny sentyment do Big Tech."
    },
    "AAPL": {
        "nazwa": "Apple",
        "drivery": {
            "Nasdaq 100 ETF (QQQ)": "QQQ",
            "Rentowności USA 10Y": "^TNX",
            "Indeks Dolara (DXY)": "DX-Y.NYB",
            "S&P 500 (SPY)": "SPY",
        },
        "opis": "Kluczowe: Siła konsumenta, sentyment Nasdaq oraz kurs dolara (sprzedaż globalna)."
    },
    "MSFT": {
        "nazwa": "Microsoft",
        "drivery": {
            "Nasdaq 100 ETF (QQQ)": "QQQ",
            "Rentowności USA 10Y": "^TNX",
            "S&P 500 (SPY)": "SPY",
        },
        "opis": "Kluczowe: Wydatki na chmurę/AI, korelacja z szerokim indeksem Nasdaq."
    },
    "TSLA": {
        "nazwa": "Tesla",
        "drivery": {
            "Nasdaq 100 ETF (QQQ)": "QQQ",
            "Ropa WTI": "CL=F",
            "Rentowności USA 10Y": "^TNX",
            "Indeks Strachu (VIX)": "^VIX",
        },
        "opis": "Kluczowe: Ceny energii/paliw, sentyment do spółek wzrostowych i apetyt na ryzyko."
    },

    # ------------------ SUROWCE I KRYPTO ------------------
    "GC=F": {
        "nazwa": "Złoto",
        "drivery": {
            "Indeks Dolara (DXY)": "DX-Y.NYB",
            "Rentowności Obligacji USA 10Y": "^TNX",
            "Srebro": "SI=F",
            "Indeks Strachu (VIX)": "^VIX",
        },
        "opis": "Kluczowe: Zależność odwrotna do siły dolara (DXY) i rentowności obligacji, popyt safe-haven (VIX)."
    },
    "CL=F": {
        "nazwa": "Ropa WTI",
        "drivery": {
            "Indeks Dolara (DXY)": "DX-Y.NYB",
            "Gaz Ziemny": "NG=F",
            "S&P 500 (SPY)": "SPY",
        },
        "opis": "Kluczowe: Siła gospodarki globalnej (SPY), kurs dolara i rynek paliw kopalnych."
    },
    "BTC-USD": {
        "nazwa": "Bitcoin",
        "drivery": {
            "Nasdaq 100 ETF (QQQ)": "QQQ",
            "Indeks Dolara (DXY)": "DX-Y.NYB",
            "Indeks Strachu (VIX)": "^VIX",
            "Złoto": "GC=F",
        },
        "opis": "Kluczowe: Płynność rynkowa, korelacja z rynkiem tech i apetyt na ryzyko (risk-on / risk-off)."
    }
}

DEFAULT_DRIVERS = {
    "S&P 500 (SPY)": "SPY",
    "Indeks Dolara (DXY)": "DX-Y.NYB",
    "Indeks Strachu (VIX)": "^VIX",
    "Rentowności USA 10Y": "^TNX"
}
