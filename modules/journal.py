# modules/journal.py
import os
import json
import pandas as pd

PLIK_BAZY_AKTYWOW = "baza_aktywow.json"
PLIK_DZIENNIKA = "dziennik_transakcji.csv"

DOMYSLNE_AKTYWA = {
    "🟡 Złoto (GC=F)": {"ticker": "GC=F", "search_term": "Gold price commodity market"},
    "🛢️ Ropa WTI (CL=F)": {"ticker": "CL=F", "search_term": "Crude oil price energy market"},
    "🛢️ Ropa Brent (BZ=F)": {"ticker": "BZ=F", "search_term": "Brent oil price energy market"},
    "⚪ Srebro (SI=F)": {"ticker": "SI=F", "search_term": "Silver price commodity market"},
    "⛽ Gaz Ziemny (NG=F)": {"ticker": "NG=F", "search_term": "Natural gas price energy"},
    "₿ Bitcoin (BTC-USD)": {"ticker": "BTC-USD", "search_term": "Bitcoin crypto market news"},
    "Ξ Ethereum (ETH-USD)": {"ticker": "ETH-USD", "search_term": "Ethereum crypto news"},
    "🪙 Solana (SOL-USD)": {"ticker": "SOL-USD", "search_term": "Solana crypto news"},
    "💻 NVIDIA (NVDA)": {"ticker": "NVDA", "search_term": "NVIDIA stock news"},
    "🍏 Apple (AAPL)": {"ticker": "AAPL", "search_term": "Apple stock market news"},
    "🪟 Microsoft (MSFT)": {"ticker": "MSFT", "search_term": "Microsoft stock news"},
    "🚗 Tesla (TSLA)": {"ticker": "TSLA", "search_term": "Tesla stock market news"},
    "📦 Amazon (AMZN)": {"ticker": "AMZN", "search_term": "Amazon stock market news"},
    "🌐 Google / Alphabet (GOOGL)": {"ticker": "GOOGL", "search_term": "Google stock market news"},
    "🥤 Coca-Cola (KO)": {"ticker": "KO", "search_term": "Coca Cola stock news"},
    "🇺🇸 S&P 500 ETF (SPY)": {"ticker": "SPY", "search_term": "S&P 500 index market today"},
    "🚀 Nasdaq 100 ETF (QQQ)": {"ticker": "QQQ", "search_term": "Nasdaq 100 ETF market"},
    "🌍 Vanguard All-World ETF (VWCE.DE)": {"ticker": "VWCE.DE", "search_term": "VWCE ETF market news"},
    "🎮 CD Projekt (CDR.WA)": {"ticker": "CDR.WA", "search_term": "CD Projekt gielda akcje"},
    "⛽ Orlen (PKN.WA)": {"ticker": "PKN.WA", "search_term": "PKN Orlen gielda GPW"},
    "🏦 PKO BP (PKO.WA)": {"ticker": "PKO.WA", "search_term": "PKO BP bank gielda GPW"},
    "⛏️ KGHM (KGH.WA)": {"ticker": "KGH.WA", "search_term": "KGHM miedz gielda GPW"},
    "🛒 Dino Polska (DNP.WA)": {"ticker": "DNP.WA", "search_term": "Dino Polska gielda GPW"},
    "🛍️ Allegro (ALR.WA)": {"ticker": "ALR.WA", "search_term": "Allegro gielda GPW"},
    "⚡ PGE (PGE.WA)": {"ticker": "PGE.WA", "search_term": "PGE gielda GPW"},
    "🏦 Bank Pekao (PEO.WA)": {"ticker": "PEO.WA", "search_term": "Bank Pekao gielda GPW"},
    "🏗️ JSW (JSW.WA)": {"ticker": "JSW.WA", "search_term": "JSW gielda wegiel"}
}


def wczytaj_baze_aktywow():
    if os.path.exists(PLIK_BAZY_AKTYWOW):
        try:
            with open(PLIK_BAZY_AKTYWOW, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return DOMYSLNE_AKTYWA.copy()


def zapisz_baze_aktywow(baza: dict):
    with open(PLIK_BAZY_AKTYWOW, "w", encoding="utf-8") as f:
        json.dump(baza, f, ensure_ascii=False, indent=4)


def wczytaj_dziennik() -> pd.DataFrame:
    if os.path.exists(PLIK_DZIENNIKA):
        try:
            return pd.read_csv(PLIK_DZIENNIKA)
        except Exception:
            pass
    return pd.DataFrame(columns=["Data", "Aktywo", "Kierunek", "Wolumen", "Cena Otwarcia", "Status", "Wynik (PLN)"])


def zapisz_w_dzienniku(nowy_wpis: dict):
    df = wczytaj_dziennik()
    df = pd.concat([df, pd.DataFrame([nowy_wpis])], ignore_index=True)
    df.to_csv(PLIK_DZIENNIKA, index=False)
