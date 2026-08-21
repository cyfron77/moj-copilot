# config_correlations.py

CORRELATION_MATRIX = {
    # ------------------ GPW (SUROWCE I ENERGIA) ------------------
    "KGH.WA": {
        "nazwa": "KGHM Polska Miedź",
        "drivery": {
            "Miedź (Cena globalna)": {"ticker": "HG=F", "waga": 0.85, "opis": "Bezpośredni i natychmiastowy wpływ na wycenę. KGHM rośnie razem z miedzią."},
            "Srebro": {"ticker": "SI=F", "waga": 0.50, "opis": "KGHM to jeden z czołowych producentów srebra na świecie (produkt uboczny)."},
            "Kurs USD/PLN": {"ticker": "PLN=X", "waga": 0.60, "opis": "Przychody ze sprzedaży są w USD, koszty wydobycia w PLN. Drogi dolar to wyższe marże."},
            "Gospodarka Chin (MCHI)": {"ticker": "MCHI", "waga": 0.40, "opis": "Chiny konsumują ponad 50% globalnej miedzi. Spowolnienie w Chinach uderza w popyt."}
        }
    },
    "PKN.WA": {
        "nazwa": "Orlen",
        "drivery": {
            "Ropa Brent": {"ticker": "BZ=F", "waga": 0.40, "opis": "Wpływa na wycenę zapasów i przychody z wydobycia, ale wysoka cena niszczy marże rafineryjne."},
            "Sektor Energetyczny EU": {"ticker": "EXSA.DE", "waga": 0.60, "opis": "Sentyment do europejskiego sektora paliwowo-energetycznego (Stoxx 600 Energy)."},
            "Gaz Ziemny": {"ticker": "NG=F", "waga": -0.30, "opis": "Gaz to ogromny koszt dla zakładów petrochemicznych (np. nawozy)."},
            "Kurs USD/PLN": {"ticker": "PLN=X", "waga": 0.30, "opis": "Ropa kupowana jest w USD, zyski realizowane w PLN/EUR."}
        }
    },
    "JSW.WA": {
        "nazwa": "Jastrzębska Spółka Węglowa",
        "drivery": {
            "Sektor Stali (XME)": {"ticker": "XME", "waga": 0.70, "opis": "JSW produkuje węgiel koksowy (baza do produkcji stali). ETF XME to świetny wskaźnik koniunktury."},
            "WIG20": {"ticker": "WIG20.WA", "waga": 0.40, "opis": "Sentyment kapitału zagranicznego do polskiego rynku ciężkiego."}
        }
    },

    # ------------------ GPW (FINANSE I KONSUMPCJA) ------------------
    "PKO.WA": {
        "nazwa": "PKO BP",
        "drivery": {
            "WIG20": {"ticker": "WIG20.WA", "waga": 0.80, "opis": "Banki stanowią trzon WIG20. Mocna korelacja z kapitałem zagranicznym."},
            "Kurs EUR/PLN": {"ticker": "EURPLN=X", "waga": -0.50, "opis": "Słaby złoty (wzrost EURPLN) oznacza wyjście zagranicy z GPW i spadki banków."},
            "Sektor Bankowy EU": {"ticker": "EUFN", "waga": 0.60, "opis": "Europejski ETF finansowy. Koniunktura na europejskie banki udziela się polskim."}
        }
    },
    "CDR.WA": {
        "nazwa": "CD Projekt",
        "drivery": {
            "Sektor Gamingowy (ESPO)": {"ticker": "ESPO", "waga": 0.60, "opis": "VanEck Video Gaming ETF. Wyznacza globalny trend dla twórców gier."},
            "Electronic Arts": {"ticker": "EA", "waga": 0.40, "opis": "Konkurencja z USA. Sentyment do branży AAA."},
            "Kurs USD/PLN": {"ticker": "PLN=X", "waga": 0.50, "opis": "Większość gier sprzedawana jest w USD/EUR, koszty pracy są w PLN."}
        }
    },
    "DNP.WA": {
        "nazwa": "Dino Polska",
        "drivery": {
            "Sektor Dóbr Podstawowych": {"ticker": "XLP", "waga": 0.50, "opis": "Globalny kapitał rotujący do spółek typu Consumer Staples."},
            "Jeronimo Martins (Biedronka)": {"ticker": "JMT.LS", "waga": 0.70, "opis": "Główny rynkowy rywal. Spółki te często są wyceniane przez analityków parami."}
        }
    },

    # ------------------ US MEGA TECH / SEMICONDUCTORS ------------------
    "NVDA": {
        "nazwa": "NVIDIA",
        "drivery": {
            "TSMC (Produkcja chipów)": {"ticker": "TSM", "waga": 0.80, "opis": "TSMC produkuje fizycznie układy dla Nvidii. Ich wyniki to wskaźnik wyprzedzający."},
            "Rentowności USA 10Y": {"ticker": "^TNX", "waga": -0.60, "opis": "Wzrost rentowności obligacji mocno dusi wyceny spółek technologicznych (koszt pieniądza)."},
            "Sektor Półprzewodników": {"ticker": "SMH", "waga": 0.90, "opis": "Branżowy ETF (VanEck Semiconductor). Wyznacza trend dla całej gałęzi AI."}
        }
    },
    "AAPL": {
        "nazwa": "Apple",
        "drivery": {
            "Nasdaq 100": {"ticker": "QQQ", "waga": 0.85, "opis": "Apple to waga ciężka w Nasdaq. Podążają niemal identycznie."},
            "Indeks Dolara (DXY)": {"ticker": "DX-Y.NYB", "waga": -0.40, "opis": "Apple generuje zyski globalnie. Silny dolar obniża ich przychody z zagranicy po przewalutowaniu."},
            "Foxconn / TSMC": {"ticker": "TSM", "waga": 0.50, "opis": "Łańcuch dostaw (produkcja iPhone'ów)."}
        }
    },
    "TSLA": {
        "nazwa": "Tesla",
        "drivery": {
            "Indeks Strachu (VIX)": {"ticker": "^VIX", "waga": -0.70, "opis": "Tesla to walor wysokiego ryzyka. Gdy rośnie strach na rynku (VIX), Tesla mocno traci."},
            "Sektor Baterii / Lit": {"ticker": "LIT", "waga": 0.60, "opis": "ETF na producentów litu i baterii. Koszt i podaż kluczowych komponentów."},
            "Ropa WTI": {"ticker": "CL=F", "waga": 0.30, "opis": "Wysokie ceny paliw napędzają długoterminowy popyt na auta EV."}
        }
    },

    # ------------------ KRYPTOWALUTY ------------------
    "BTC-USD": {
        "nazwa": "Bitcoin",
        "drivery": {
            "Nasdaq 100": {"ticker": "QQQ", "waga": 0.70, "opis": "Krypto jest obecnie wyceniane jako lewarowany sektor technologiczny."},
            "Indeks Dolara (DXY)": {"ticker": "DX-Y.NYB", "waga": -0.75, "opis": "Odwrotna korelacja. Gdy fiat (dolar) słabnie, krypto rośnie."},
            "Złoto": {"ticker": "GC=F", "waga": 0.30, "opis": "Konkurent o miano 'cyfrowego złota', choć korelacja bywa zmienna."}
        }
    },

    # ------------------ SUROWCE BAZOWE ------------------
    "GC=F": {
        "nazwa": "Złoto",
        "drivery": {
            "Realne Stopy / US 10Y": {"ticker": "^TNX", "waga": -0.85, "opis": "Złoto nie płaci dywidendy. Gdy obligacje dają wysoki procent, kapitał ucieka ze złota."},
            "Indeks Dolara (DXY)": {"ticker": "DX-Y.NYB", "waga": -0.80, "opis": "Złoto wyceniane w USD. Silny dolar = tańsze złoto dla reszty świata."},
            "Indeks Strachu (VIX)": {"ticker": "^VIX", "waga": 0.50, "opis": "Bezpieczna przystań (Safe Haven) w czasach paniki rynkowej."}
        }
    },
    "CL=F": {
        "nazwa": "Ropa WTI",
        "drivery": {
            "Sektor Transportu / Przemysł": {"ticker": "XLI", "waga": 0.60, "opis": "Przemysł i logistyka to główni konsumenci energii i paliw."},
            "Indeks Dolara (DXY)": {"ticker": "DX-Y.NYB", "waga": -0.50, "opis": "Ropa rozliczana w USD. Słaby dolar sztucznie podbija cenę za baryłkę."}
        }
    }
}

# Domyślny fallback dla pozostałych, niewymienionych wyżej walorów z Twojej listy (np. indeksów)
DEFAULT_DRIVERS = {
    "S&P 500": {"ticker": "SPY", "waga": 1.0, "opis": "Ogólny rynek akcji USA."},
    "Indeks Dolara": {"ticker": "DX-Y.NYB", "waga": -0.5, "opis": "Siła waluty rezerwowej."},
    "Rentowności 10Y": {"ticker": "^TNX", "waga": -0.5, "opis": "Koszt pieniądza."}
}
