import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
import feedparser
from textblob import TextBlob
from datetime import datetime
import os
import json

# ---------------------------------------------------------
# Konfiguracja strony
# ---------------------------------------------------------
st.set_page_config(
    page_title="AI Trading Copilot Pro",
    layout="wide",
    page_icon="📈"
)

st.title("🤖 AI Trading & Investment Copilot")
st.caption("Wsparcie decyzji inwestycyjnych: Wall Street, GPW, Surowce, CFD (XTB)")

# ---------------------------------------------------------
# Dynamiczna baza aktywów (JSON)
# ---------------------------------------------------------
PLIK_BAZY_AKTYWOW = "baza_aktywow.json"

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


popularne_aktywa = wczytaj_baze_aktywow()

# ---------------------------------------------------------
# Dziennik transakcji (CSV)
# ---------------------------------------------------------
PLIK_DZIENNIKA = "dziennik_transakcji.csv"


def wczytaj_dziennik() -> pd.DataFrame:
    if os.path.exists(PLIK_DZIENNIKA):
        try:
            return pd.read_csv(PLIK_DZIENNIKA)
        except Exception:
            pass
    return pd.DataFrame(
        columns=[
            "Data",
            "Aktywo",
            "Kierunek",
            "Wolumen",
            "Cena Otwarcia",
            "Status",
            "Wynik (PLN)"
        ]
    )


def zapisz_w_dzienniku(nowy_wpis: dict):
    df = wczytaj_dziennik()
    df = pd.concat([df, pd.DataFrame([nowy_wpis])], ignore_index=True)
    df.to_csv(PLIK_DZIENNIKA, index=False)

# ---------------------------------------------------------
# Funkcje wskaźników technicznych
# ---------------------------------------------------------


def dodaj_wskazniki(dane: pd.DataFrame) -> pd.DataFrame:
    """Dodaje SMA, Bollinger Bands, RSI, MACD, ATR, ADX oraz wskaźniki wolumenu."""
    if dane is None or dane.empty:
        return dane

    df = dane.copy()

    # Ujednolicenie nazw kolumn (przy MultiIndex / różnych formatach)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # Upewnij się, że mamy standardowe kolumny
    potrzebne = {"Open", "High", "Low", "Close"}
    if not potrzebne.issubset(df.columns):
        # próbujemy dopasować nazwy
        rename_map = {}
        for c in df.columns:
            lc = c.lower()
            if "open" in lc:
                rename_map[c] = "Open"
            elif "high" in lc:
                rename_map[c] = "High"
            elif "low" in lc:
                rename_map[c] = "Low"
            elif "close" in lc and "adj" not in lc:
                rename_map[c] = "Close"
            elif "volume" in lc:
                rename_map[c] = "Volume"
        df.rename(columns=rename_map, inplace=True)

    # Średnie kroczące
    df["SMA20"] = df["Close"].rolling(window=20).mean()
    df["SMA50"] = df["Close"].rolling(window=50).mean()
    df["SMA200"] = df["Close"].rolling(window=200).mean()

    # RSI (14)
    delta = df["Close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df["RSI"] = 100 - (100 / (1 + rs))

    # Wstęgi Bollingera
    std20 = df["Close"].rolling(window=20).std()
    df["BB_Upper"] = df["SMA20"] + (std20 * 2)
    df["BB_Lower"] = df["SMA20"] - (std20 * 2)

    # MACD
    ema12 = df["Close"].ewm(span=12, adjust=False).mean()
    ema26 = df["Close"].ewm(span=26, adjust=False).mean()
    df["MACD"] = ema12 - ema26
    df["MACD_Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["MACD_Hist"] = df["MACD"] - df["MACD_Signal"]

    # ATR (14) + True Range
    tr1 = df["High"] - df["Low"]
    tr2 = (df["High"] - df["Close"].shift()).abs()
    tr3 = (df["Low"] - df["Close"].shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df["ATR"] = tr.rolling(window=14).mean()

    # ADX (14) – siła trendu
    up_move = df["High"] - df["High"].shift(1)
    down_move = df["Low"].shift(1) - df["Low"]
    plus_dm = np.where(
        (up_move > down_move) & (up_move > 0),
        up_move,
        0.0,
    )
    minus_dm = np.where(
        (down_move > up_move) & (down_move > 0),
        down_move,
        0.0,
    )

    tr_rolling = tr.rolling(window=14).sum()
    plus_di = 100 * pd.Series(plus_dm).rolling(14).sum() / tr_rolling
    minus_di = 100 * pd.Series(minus_dm).rolling(14).sum() / tr_rolling
    dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
    df["ADX"] = dx.rolling(window=14).mean()

    # Wolumen – jeśli dostępny
    if "Volume" in df.columns:
        df["Vol_MA20"] = df["Volume"].rolling(window=20).mean()
        df["Vol_Ratio"] = df["Volume"] / df["Vol_MA20"]
    else:
        df["Vol_MA20"] = np.nan
        df["Vol_Ratio"] = np.nan

    return df

# ---------------------------------------------------------
# Pobieranie danych z yfinance (cache)
# ---------------------------------------------------------


@st.cache_data(ttl=600, persist="disk")
def pobierz_dane(symbol: str, period: str, interval: str) -> pd.DataFrame:
    """Pobiera dane dla pojedynczego symbolu i dodaje wskaźniki."""
    try:
        dane = yf.download(
            symbol,
            period=period,
            interval=interval,
            auto_adjust=False,
            progress=False,
        )
        if dane is not None and not dane.empty:
            dane = dodaj_wskazniki(dane)
        return dane
    except Exception:
        return None


@st.cache_data(ttl=600)
def pobierz_dane_multi(lista_symboli, period="3mo", interval="1d") -> dict:
    """Pobiera dane dla wielu tickerów naraz (używane w skanerze)."""
    if not lista_symboli:
        return {}

    try:
        raw = yf.download(
            tickers=lista_symboli,
            period=period,
            interval=interval,
            group_by="ticker",
            auto_adjust=False,
            progress=False,
        )

        wyniki = {}

        if isinstance(raw.columns, pd.MultiIndex):
            for sym in lista_symboli:
                try:
                    sub = raw[sym].copy()
                    sub = dodaj_wskazniki(sub)
                    wyniki[sym] = sub
                except Exception:
                    continue
        else:
            # Fallback: pojedyncze zapytania
            for sym in lista_symboli:
                d = pobierz_dane(sym, period, interval)
                if d is not None and not d.empty:
                    wyniki[sym] = d

        return wyniki
    except Exception:
        return {}

# ---------------------------------------------------------
# Predefiniowane profile AI (wagi sygnałów)
# ---------------------------------------------------------

AI_PROFILES = {
    "Zbalansowany": {
        "w_trend": 1.0,
        "w_rsi": 1.0,
        "w_macd": 1.0,
        "w_sent": 1.0,
        "w_vol": 1.0,
    },
    "Konserwatywny": {
        "w_trend": 1.5,
        "w_rsi": 1.0,
        "w_macd": 1.5,
        "w_sent": 0.5,
        "w_vol": 1.0,
    },
    "Agresywny": {
        "w_trend": 0.8,
        "w_rsi": 1.2,
        "w_macd": 1.2,
        "w_sent": 1.0,
        "w_vol": 0.8,
    },
}

# ---------------------------------------------------------
# AI silnik werdyktu (z SMA200, ADX i wolumenem)
# ---------------------------------------------------------


def oblicz_ai_werdykt(
    cena: float,
    sma50: float,
    sma200: float,
    rsi: float,
    macd: float,
    macd_sig: float,
    avg_sent: float,
    atr: float,
    adx: float,
    vol_ratio: float,
    data_len: int,
    w_trend: float,
    w_rsi: float,
    w_macd: float,
    w_sent: float,
    w_vol: float,
):
    jakosc_flags = []

    # Trend (SMA50)
    trend_signal = 1 if cena > sma50 else -1
    trend_opis = "Trend wzrostowy (Cena > SMA50)" if trend_signal == 1 else "Trend spadkowy (Cena < SMA50)"

    # RSI
    if rsi < 35:
        rsi_signal = 1
        rsi_opis = "Wyprzedanie (RSI < 35)"
    elif rsi > 70:
        rsi_signal = -1
        rsi_opis = "Wykupienie (RSI > 70)"
    else:
        rsi_signal = 0
        rsi_opis = "RSI neutralny (35–70)"

    # MACD
    if macd > macd_sig:
        macd_signal = 1
        macd_opis = "MACD > Sygnał (pro-wzrostowo)"
    else:
        macd_signal = -1
        macd_opis = "MACD < Sygnał (pro-spadkowo)"

    # Sentyment (news)
    if avg_sent > 0.05:
        sent_signal = 1
        sent_opis = "Pozytywny / byczy"
    elif avg_sent < -0.05:
        sent_signal = -1
        sent_opis = "Negatywny / niedźwiedzi"
    else:
        sent_signal = 0
        sent_opis = "Neutralny"

    # Wolumen – spike = potwierdzenie ruchu
    if not pd.isna(vol_ratio) and vol_ratio >= 1.3:
        vol_signal = 1
        vol_opis = "Wzmożony wolumen (>=130% średniej)"
    else:
        vol_signal = 0
        vol_opis = "Wolumen w normie / brak potwierdzenia"

    # Początkowy score (bez filtrów jakości)
    base_score = (
        w_trend * trend_signal
        + w_rsi * rsi_signal
        + w_macd * macd_signal
        + w_sent * sent_signal
        + w_vol * vol_signal
    )

    # Jakość danych i filtry

    atr_ratio = atr / cena if cena > 0 else 0.0

    # Mało danych
    if data_len < 50:
        base_score *= 0.7
        jakosc_flags.append("⚠️ Mało danych (mniej niż 50 świec) – score obniżony x0.7")

    # Zmienność
    if atr_ratio > 0.05:
        jakosc_flags.append("⚠️ Bardzo wysoka zmienność (ATR > 5% ceny)")
    elif atr_ratio < 0.01:
        jakosc_flags.append("ℹ️ Niska zmienność (ATR < 1% ceny)")

    # Długoterminowy trend (SMA200)
    if not pd.isna(sma200):
        if cena < sma200:
            base_score *= 0.7
            jakosc_flags.append("⚠️ Cena poniżej SMA200 – długoterminowy trend spadkowy (score x0.7)")
        elif cena > sma200 and trend_signal == 1:
            base_score *= 1.1
            jakosc_flags.append("✅ Cena powyżej SMA200 i SMA50 – silny uptrend (score x1.1)")

    # ADX – siła trendu
    if not pd.isna(adx):
        if adx < 20:
            base_score *= 0.8
            jakosc_flags.append("⚠️ Słaby trend (ADX < 20) – ogranicz zaufanie do sygnałów trendowych (score x0.8)")
        elif adx > 25:
            base_score *= 1.1
            jakosc_flags.append("✅ Silny trend (ADX > 25) – sygnały trendowe bardziej wiarygodne (score x1.1)")

    # Klasyfikacja
    if base_score >= 3:
        status = "MOCNY KANDYDAT NA LONGA (KUPNO)"
        kolor = "success"
        komentarz = "Przewaga sygnałów prowzrostowych przy akceptowalnej jakości warunków rynkowych."
    elif base_score <= -3:
        status = "KANDYDAT NA SHORTA / OSTRZEŻENIE"
        kolor = "error"
        komentarz = "Przewaga sygnałów prospadkowych lub przegrzania rynku – zachowaj ostrożność."
    else:
        status = "NEUTRALNY / OBSERWACJA"
        kolor = "info"
        komentarz = "Sygnały są mieszane lub rynek w konsolidacji – unikaj agresywnych wejść."

    return {
        "score": base_score,
        "status": status,
        "kolor": kolor,
        "komentarz": komentarz,
        "trend_opis": trend_opis,
        "rsi_opis": rsi_opis,
        "macd_opis": macd_opis,
        "sent_opis": sent_opis,
        "vol_opis": vol_opis,
        "jakosc_flags": jakosc_flags,
    }

# ---------------------------------------------------------
# Pobieranie newsów (Yahoo + Google News)
# ---------------------------------------------------------


@st.cache_data(ttl=300)
def pobierz_swieze_newsy(symbol: str, query: str):
    news_list = []
    # 1. Yahoo Finance
    try:
        yf_ticker = yf.Ticker(symbol)
        raw_news = yf_ticker.news
        if raw_news:
            for n in raw_news[:6]:
                tytul = n.get("title", "")
                link = n.get("link", "#")
                ts = n.get("providerPublishTime", None)
                data_str = (
                    datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
                    if ts
                    else "Świeże"
                )
                zrodlo = n.get("publisher", "Yahoo Finance")
                if tytul:
                    news_list.append(
                        {
                            "tytul": tytul,
                            "link": link,
                            "data": data_str,
                            "zrodlo": zrodlo,
                        }
                    )
    except Exception:
        pass

    # 2. Google News – fallback
    if len(news_list) < 2:
        is_pl = symbol.endswith(".WA")
        lang = "pl" if is_pl else "en-US"
        gl = "PL" if is_pl else "US"
        ceid = "PL:pl" if is_pl else "US:en"
        clean_q = query.replace(" ", "+")
        rss_url = (
            f"https://news.google.com/rss/search?q={clean_q}+when:7d"
            f"&hl={lang}&gl={gl}&ceid={ceid}"
        )
        feed = feedparser.parse(rss_url)
        if feed.entries:
            for entry in feed.entries[:6]:
                news_list.append(
                    {
                        "tytul": entry.title,
                        "link": entry.link,
                        "data": entry.published if "published" in entry else "Ostatnie dni",
                        "zrodlo": "Google News / Portale",
                    }
                )
    return news_list

# ---------------------------------------------------------
# Sidebar – wybór aktywa, filtr, edytor bazy
# ---------------------------------------------------------
st.sidebar.header("⚙️ Ustawienia analizy")

fraza_szukania = st.sidebar.text_input(
    "🔍 Wyszukaj po nazwie (np. 'ropa', 'bank', 'apple'):",
    value="",
)

if fraza_szukania.strip():
    pasujace_aktywa = {
        k: v for k, v in popularne_aktywa.items()
        if fraza_szukania.lower() in k.lower()
    }
else:
    pasujace_aktywa = popularne_aktywa

if len(pasujace_aktywa) > 0:
    wybor_predefiniowany = st.sidebar.selectbox(
        "⭐ Wybierz z pasujących:",
        list(pasujace_aktywa.keys()),
    )
    ticker = pasujace_aktywa[wybor_predefiniowany]["ticker"]
    search_query = pasujace_aktywa[wybor_predefiniowany]["search_term"]
else:
    st.sidebar.warning(
        "Brak dopasowań. Sprawdź pisownię lub dodaj walor w edytorze poniżej."
    )
    wybor_predefiniowany = list(popularne_aktywa.keys())[0]
    ticker = popularne_aktywa[wybor_predefiniowany]["ticker"]
    search_query = popularne_aktywa[wybor_predefiniowany]["search_term"]

with st.sidebar.expander("🛠️ Edytor listy walorów"):
    st.markdown("**Dodaj nowy walor:**")
    nowa_nazwa = st.text_input("Nazwa (np. 🍿 Netflix):", key="add_name")
    nowy_ticker = st.text_input("Ticker (np. NFLX):", key="add_ticker")
    if st.button("➕ Dodaj do listy"):
        if nowa_nazwa and nowy_ticker:
            t_clean = nowy_ticker.upper().strip()
            popularne_aktywa[nowa_nazwa] = {
                "ticker": t_clean,
                "search_term": f"{t_clean} stock market news",
            }
            zapisz_baze_aktywow(popularne_aktywa)
            st.success(f"Dodano: {nowa_nazwa}")
            st.rerun()
        else:
            st.error("Uzupełnij nazwę i ticker.")

    st.markdown("---")
    st.markdown("**Usuń walor z listy:**")
    walor_do_usuniecia = st.selectbox(
        "Wybierz do usunięcia:",
        list(popularne_aktywa.keys()),
        key="del_select",
    )
    if st.button("🗑️ Usuń walor"):
        if len(popularne_aktywa) > 1:
            del popularne_aktywa[walor_do_usuniecia]
            zapisz_baze_aktywow(popularne_aktywa)
            st.success(f"Usunięto: {walor_do_usuniecia}")
            st.rerun()
        else:
            st.warning("Lista nie może być pusta.")

# Zakres czasu i interwał
okres = st.sidebar.selectbox(
    "Zakres czasu wykresu:",
    ["1mo", "3mo", "6mo", "1y", "2y"],
    index=2,
)
interwal = st.sidebar.selectbox(
    "Interwał świec:",
    ["1d", "1wk"],
    index=0,
)

st.sidebar.markdown("---")

# Ustawienia kalkulatora pozycji + XTB / CFD
st.sidebar.header("⚖️ Kalkulator Wielkości Pozycji (XTB)")
kapital = st.sidebar.number_input(
    "Twój kapitał (PLN / USD):",
    min_value=100.0,
    value=10000.0,
    step=500.0,
)

ryzyko_proc = st.sidebar.slider(
    "Dopuszczalne ryzyko transakcji (%):",
    min_value=0.5,
    max_value=5.0,
    value=1.5,
    step=0.5,
)

instrument_typ = st.sidebar.selectbox(
    "Typ instrumentu:",
    ["Akcje / ETF", "CFD XTB"],
    index=0,
)

leverage = 1.0
contract_multiplier = 1.0

if instrument_typ == "CFD XTB":
    leverage = st.sidebar.number_input(
        "Dźwignia (np. 30 dla FX, 5 dla akcji CFD):",
        min_value=1.0,
        value=5.0,
        step=1.0,
    )
    contract_multiplier = st.sidebar.number_input(
        "Wartość 1 kontraktu (np. 1 dla akcji, 100 dla indeksów):",
        min_value=0.01,
        value=1.0,
        step=0.01,
    )

st.sidebar.markdown("---")

# Ustawienia AI werdyktu – profil zamiast suwaków
st.sidebar.header("🤖 Profil AI werdyktu")
profil_ai = st.sidebar.selectbox(
    "Wybierz profil sygnałów:",
    list(AI_PROFILES.keys()),
    index=0,
)
wagi = AI_PROFILES[profil_ai]

# ---------------------------------------------------------
# Pobranie danych dla wybranego tickera
# ---------------------------------------------------------
df = pobierz_dane(ticker, okres, interwal)

if df is None or df.empty:
    st.error(
        f"Nie udało się pobrać danych dla symbolu: **{ticker}**. "
        "Sprawdź poprawność tickera lub usuń ten walor."
    )
    st.stop()

ostatnia_cena = float(df["Close"].iloc[-1])
poprzednia_cena = float(df["Close"].iloc[-2]) if len(df) > 1 else ostatnia_cena
zmiana_proc = (
    ((ostatnia_cena - poprzednia_cena) / poprzednia_cena) * 100
    if poprzednia_cena != 0
    else 0.0
)

ostatni_rsi = float(df["RSI"].iloc[-1]) if not pd.isna(df["RSI"].iloc[-1]) else 50.0
ostatnie_sma20 = float(df["SMA20"].iloc[-1]) if not pd.isna(df["SMA20"].iloc[-1]) else ostatnia_cena
ostatnie_sma50 = float(df["SMA50"].iloc[-1]) if not pd.isna(df["SMA50"].iloc[-1]) else ostatnia_cena
ostatnie_sma200 = float(df["SMA200"].iloc[-1]) if not pd.isna(df["SMA200"].iloc[-1]) else np.nan
ostatni_macd = float(df["MACD"].iloc[-1]) if not pd.isna(df["MACD"].iloc[-1]) else 0.0
ostatni_macd_sig = float(df["MACD_Signal"].iloc[-1]) if not pd.isna(df["MACD_Signal"].iloc[-1]) else 0.0
ostatni_atr = float(df["ATR"].iloc[-1]) if not pd.isna(df["ATR"].iloc[-1]) else (ostatnia_cena * 0.02)
ostatni_adx = float(df["ADX"].iloc[-1]) if not pd.isna(df["ADX"].iloc[-1]) else np.nan
ostatni_vol_ratio = float(df["Vol_Ratio"].iloc[-1]) if "Vol_Ratio" in df.columns and not pd.isna(df["Vol_Ratio"].iloc[-1]) else np.nan

# ---------------------------------------------------------
# News + sentyment (zależnie od języka)
# ---------------------------------------------------------
surowe_newsy = pobierz_swieze_newsy(ticker, search_query)
sentymenty = []
news_items = []

is_pl_symbol = ticker.endswith(".WA")

for item in surowe_newsy:
    if is_pl_symbol:
        # TextBlob nie działa dobrze dla PL – traktujemy jako neutralne
        polaryzacja = 0.0
        kolor = "⚪ Neutralny (PL – brak analizy AI)"
    else:
        analiza = TextBlob(item["tytul"])
        polaryzacja = analiza.sentiment.polarity
        kolor = (
            "🟢 Pozytywny"
            if polaryzacja > 0.05
            else ("🔴 Negatywny" if polaryzacja < -0.05 else "⚪ Neutralny")
        )

    sentymenty.append(polaryzacja)
    news_items.append(
        {
            "tytul": item["tytul"],
            "score": polaryzacja,
            "status": kolor,
            "data": item["data"],
            "zrodlo": item["zrodlo"],
            "link": item["link"],
        }
    )

avg_sent = sum(sentymenty) / len(sentymenty) if sentymenty else 0.0

# ---------------------------------------------------------
# AI werdykt dla głównego waloru
# ---------------------------------------------------------
werdykt = oblicz_ai_werdykt(
    cena=ostatnia_cena,
    sma50=ostatnie_sma50,
    sma200=ostatnie_sma200,
    rsi=ostatni_rsi,
    macd=ostatni_macd,
    macd_sig=ostatni_macd_sig,
    avg_sent=avg_sent,
    atr=ostatni_atr,
    adx=ostatni_adx,
    vol_ratio=ostatni_vol_ratio,
    data_len=len(df),
    w_trend=wagi["w_trend"],
    w_rsi=wagi["w_rsi"],
    w_macd=wagi["w_macd"],
    w_sent=wagi["w_sent"],
    w_vol=wagi["w_vol"],
)

# ---------------------------------------------------------
# Górny panel metryk
# ---------------------------------------------------------
c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
c1.metric("Ticker", ticker)
c2.metric("Kurs", f"{ostatnia_cena:.2f}", f"{zmiana_proc:+.2f}%")
c3.metric("RSI (14)", f"{ostatni_rsi:.1f}", werdykt["rsi_opis"])
c4.metric("MACD Status", f"{ostatni_macd:.2f}", werdykt["macd_opis"])
c5.metric("ATR (14)", f"{ostatni_atr:.2f}", "Średni zasięg świecy")
c6.metric("ADX (14)", f"{ostatni_adx:.1f}" if not np.isnan(ostatni_adx) else "n/a", "Siła trendu")
c7.metric("Volume Ratio", f"{ostatni_vol_ratio:.2f}" if not np.isnan(ostatni_vol_ratio) else "n/a", werdykt["vol_opis"])

jakosc_txt = ""
if werdykt["jakosc_flags"]:
    jakosc_txt = "\n\n- " + "\n- ".join(werdykt["jakosc_flags"])

komunikat_werdyktu = (
    f"🎯 **WERDYKT AI COPILOTA ({profil_ai}): {werdykt['status']}**\n\n"
    f"- {werdykt['trend_opis']} | {werdykt['rsi_opis']} | {werdykt['macd_opis']} | "
    f"Sentyment: {werdykt['sent_opis']} | {werdykt['vol_opis']}\n"
    f"- *{werdykt['komentarz']}*\n"
    f"- Łączny AI Score: **{werdykt['score']:.2f}**"
    f"{jakosc_txt}"
)

if werdykt["kolor"] == "success":
    st.success(komunikat_werdyktu)
elif werdykt["kolor"] == "error":
    st.error(komunikat_werdyktu)
else:
    st.info(komunikat_werdyktu)

# ---------------------------------------------------------
# Zakładki główne
# ---------------------------------------------------------
tab1, tab2, tab3, tab4, tab5 = st.tabs(
    [
        "📈 Zaawansowany Wykres (Wstęgi + MACD + Volume)",
        "🤖 Analiza Sentymentu (AI)",
        "⚖️ Kalkulator Pozycji & ATR",
        "🔍 Skaner Rynku (GPW & USA)",
        "📓 Dziennik Transakcji",
    ]
)

# ---------------------------------------------------------
# Tab 1 – wykres techniczny + wolumen
# ---------------------------------------------------------
with tab1:
    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.55, 0.25, 0.2],
    )

    # Świece
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["Open"],
            high=df["High"],
            low=df["Low"],
            close=df["Close"],
            name="Świece",
        ),
        row=1,
        col=1,
    )

    # SMA i Bollinger
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["SMA20"],
            line=dict(color="orange", width=1.2),
            name="SMA 20",
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["SMA50"],
            line=dict(color="deepskyblue", width=1.5),
            name="SMA 50",
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["SMA200"],
            line=dict(color="magenta", width=1.5),
            name="SMA 200",
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["BB_Upper"],
            line=dict(color="gray", width=1, dash="dot"),
            name="Górna Wstęga",
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["BB_Lower"],
            line=dict(color="gray", width=1, dash="dot"),
            name="Dolna Wstęga",
        ),
        row=1,
        col=1,
    )

    # MACD
    colors_hist = ["green" if val >= 0 else "red" for val in df["MACD_Hist"]]
    fig.add_trace(
        go.Bar(
            x=df.index,
            y=df["MACD_Hist"],
            name="MACD Hist",
            marker_color=colors_hist,
        ),
        row=2,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["MACD"],
            line=dict(color="cyan", width=1.5),
            name="MACD",
        ),
        row=2,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["MACD_Signal"],
            line=dict(color="yellow", width=1.2),
            name="Sygnał MACD",
        ),
        row=2,
        col=1,
    )

    # Wolumen
    if "Volume" in df.columns:
        fig.add_trace(
            go.Bar(
                x=df.index,
                y=df["Volume"],
                name="Wolumen",
                marker_color="lightblue",
            ),
            row=3,
            col=1,
        )
        if "Vol_MA20" in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df["Vol_MA20"],
                    name="Średni wolumen (20)",
                    line=dict(color="orange", width=1.5),
                ),
                row=3,
                col=1,
            )

    fig.update_layout(
        title=f"Analiza techniczna: {ticker}",
        xaxis_rangeslider_visible=False,
        height=720,
        template="plotly_dark",
        margin=dict(l=20, r=20, t=40, b=20),
    )
    st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------
# Tab 2 – newsy i sentyment
# ---------------------------------------------------------
with tab2:
    st.subheader("📰 Świeże wiadomości rynkowe (Real-Time)")
    if news_items:
        for item in news_items:
            st.markdown(f"**[{item['tytul']}]({item['link']})**")
            st.caption(
                f"Sentyment: {item['status']} (`{item['score']:.2f}`) | "
                f"Źródło: **{item['zrodlo']}** | Opublikowano: **{item['data']}**"
            )
            st.write("---")
    else:
        st.warning("Brak najnowszych wiadomości dla tego aktywa z ostatnich dni.")

# ---------------------------------------------------------
# Tab 3 – kalkulator pozycji i ryzyka
# ---------------------------------------------------------
with tab3:
    st.subheader("⚖️ Inteligentny Kalkulator Pozycji i Ryzyka (Zmienność ATR)")
    st.caption(
        "Kalkulator automatycznie dopasowuje odległość Stop Lossa do rzeczywistej dynamiki rynku (ATR)."
    )

    mnoznik_atr = st.slider(
        "Mnożnik ATR dla Stop Lossa (Zalecane: 1.5x - 2.5x):",
        min_value=1.0,
        max_value=4.0,
        value=2.0,
        step=0.5,
    )
    sugerowany_sl_long = float(
        round(ostatnia_cena - (ostatni_atr * mnoznik_atr), 2)
    )
    sugerowany_tp_long = float(
        round(ostatnia_cena + (ostatni_atr * mnoznik_atr * 2.0), 2)
    )

    c_sl, c_tp = st.columns(2)
    with c_sl:
        stop_loss = st.number_input(
            "Poziom Stop Loss (SL):",
            value=sugerowany_sl_long,
        )
    with c_tp:
        take_profit = st.number_input(
            "Poziom Take Profit (TP):",
            value=sugerowany_tp_long,
        )

    roznica_sl = abs(ostatnia_cena - stop_loss)

    if roznica_sl > 0:
        max_strata_kwota = kapital * (ryzyko_proc / 100)
        rekomendowana_liczba = int(max_strata_kwota / roznica_sl)

        if instrument_typ == "CFD XTB":
            wartosc_pozycji = rekomendowana_liczba * ostatnia_cena * contract_multiplier
            margin_needed = wartosc_pozycji / leverage
            ryzyko_na_sl = roznica_sl * contract_multiplier * rekomendowana_liczba
        else:
            wartosc_pozycji = rekomendowana_liczba * ostatnia_cena
            margin_needed = wartosc_pozycji
            ryzyko_na_sl = roznica_sl * rekomendowana_liczba

        r_r = (
            abs(take_profit - ostatnia_cena) / roznica_sl
            if roznica_sl != 0
            else 0.0
        )

        st.success(
            "🎯 Parametry zlecenia:\n\n"
            f"- Typ instrumentu: **{instrument_typ}**\n"
            f"- Zalecana wielkość pozycji: **{rekomendowana_liczba}** sztuk / kontraktów\n"
            f"- Łączna wartość transakcji (notional): **{wartosc_pozycji:,.2f}**\n"
            f"- Szacowana strata przy SL: **{ryzyko_na_sl:,.2f}**\n"
            f"- Ryzyko kapitałowe (Max strata wg {ryzyko_proc}%): **{max_strata_kwota:,.2f}**\n"
            f"- Wymagany depozyt/margin: **{margin_needed:,.2f}**\n"
            f"- Stosunek Zysku do Ryzyka (Risk/Reward): **1 : {r_r:.2f}**\n"
            f"- Bieżąca zmienność ATR (14): **{ostatni_atr:.2f}**"
        )

        # Prosta wizualizacja SL/TP
        fig_rr = go.Figure()
        fig_rr.add_trace(
            go.Scatter(
                x=["SL", "Cena", "TP"],
                y=[stop_loss, ostatnia_cena, take_profit],
                mode="lines+markers",
                name="Poziomy SL / TP",
                line=dict(color="lime", width=3),
            )
        )
        fig_rr.update_layout(
            title="Poziomy SL / TP względem bieżącej ceny",
            template="plotly_dark",
            height=300,
        )
        st.plotly_chart(fig_rr, use_container_width=True)
    else:
        st.warning("Stop Loss nie może być równy bieżącej cenie.")

# ---------------------------------------------------------
# Tab 4 – skaner rynku z AI score (z ADX i wolumenem)
# ---------------------------------------------------------
with tab4:
    st.subheader("🔍 Skaner Okazji Rynkowych (Szybki przegląd rynku)")

    if st.button("🚀 Uruchom skanowanie rynku"):
        with st.spinner("Skanowanie w toku..."):
            lista_symboli = [v["ticker"] for v in popularne_aktywa.values()]
            dane_multi = pobierz_dane_multi(lista_symboli, period="3mo", interval="1d")

            wyniki_skanera = []
            for nazwa, dane_aktyw in popularne_aktywa.items():
                sym = dane_aktyw["ticker"]
                d_skan = dane_multi.get(sym)
                if d_skan is None or d_skan.empty:
                    continue

                cena = float(d_skan["Close"].iloc[-1])
                rsi_val = (
                    float(d_skan["RSI"].iloc[-1])
                    if "RSI" in d_skan.columns and not pd.isna(d_skan["RSI"].iloc[-1])
                    else 50.0
                )
                sma50_val = (
                    float(d_skan["SMA50"].iloc[-1])
                    if "SMA50" in d_skan.columns and not pd.isna(d_skan["SMA50"].iloc[-1])
                    else cena
                )
                sma200_val = (
                    float(d_skan["SMA200"].iloc[-1])
                    if "SMA200" in d_skan.columns and not pd.isna(d_skan["SMA200"].iloc[-1])
                    else np.nan
                )
                atr_val = (
                    float(d_skan["ATR"].iloc[-1])
                    if "ATR" in d_skan.columns and not pd.isna(d_skan["ATR"].iloc[-1])
                    else 0.0
                )
                macd_val = (
                    float(d_skan["MACD"].iloc[-1])
                    if "MACD" in d_skan.columns and not pd.isna(d_skan["MACD"].iloc[-1])
                    else 0.0
                )
                macd_sig_val = (
                    float(d_skan["MACD_Signal"].iloc[-1])
                    if "MACD_Signal" in d_skan.columns and not pd.isna(d_skan["MACD_Signal"].iloc[-1])
                    else 0.0
                )
                adx_val = (
                    float(d_skan["ADX"].iloc[-1])
                    if "ADX" in d_skan.columns and not pd.isna(d_skan["ADX"].iloc[-1])
                    else np.nan
                )
                vol_ratio_val = (
                    float(d_skan["Vol_Ratio"].iloc[-1])
                    if "Vol_Ratio" in d_skan.columns and not pd.isna(d_skan["Vol_Ratio"].iloc[-1])
                    else np.nan
                )

                trend = "🟢 Wzrostowy" if cena > sma50_val else "🔴 Spadkowy"

                if rsi_val < 35:
                    stan_rsi = "🔥 Wyprzedanie (<35)"
                elif rsi_val > 70:
                    stan_rsi = "⚠️ Wykupienie (>70)"
                else:
                    stan_rsi = "Neutralne"

                werdykt_skan = oblicz_ai_werdykt(
                    cena=cena,
                    sma50=sma50_val,
                    sma200=sma200_val,
                    rsi=rsi_val,
                    macd=macd_val,
                    macd_sig=macd_sig_val,
                    avg_sent=0.0,  # brak sentymentu w skanerze – neutralny
                    atr=atr_val,
                    adx=adx_val,
                    vol_ratio=vol_ratio_val,
                    data_len=len(d_skan),
                    w_trend=wagi["w_trend"],
                    w_rsi=wagi["w_rsi"],
                    w_macd=wagi["w_macd"],
                    w_sent=wagi["w_sent"],
                    w_vol=wagi["w_vol"],
                )

                wyniki_skanera.append(
                    {
                        "Aktywo": nazwa,
                        "Ticker": sym,
                        "Cena": f"{cena:.2f}",
                        "RSI (14)": f"{rsi_val:.1f}",
                        "Stan RSI": stan_rsi,
                        "ATR": f"{atr_val:.2f}",
                        "Trend (SMA50)": trend,
                        "ADX (14)": f"{adx_val:.1f}" if not np.isnan(adx_val) else "n/a",
                        "Volume Ratio": f"{vol_ratio_val:.2f}" if not np.isnan(vol_ratio_val) else "n/a",
                        "AI Score": round(werdykt_skan["score"], 2),
                        "AI Werdykt": werdykt_skan["status"],
                    }
                )

            df_skaner = pd.DataFrame(wyniki_skanera)

            # Proste filtry
            if not df_skaner.empty:
                rsi_filter = st.selectbox(
                    "Filtr RSI:",
                    ["(Wszystkie)", "Wyprzedane (<35)", "Wykupione (>70)"],
                )
                trend_filter = st.selectbox(
                    "Filtr trendu:",
                    ["(Wszystkie)", "Trend wzrostowy", "Trend spadkowy"],
                )

                df_view = df_skaner.copy()

                if rsi_filter == "Wyprzedane (<35)":
                    df_view = df_view[df_view["Stan RSI"].str.contains("Wyprzedanie")]
                elif rsi_filter == "Wykupione (>70)":
                    df_view = df_view[df_view["Stan RSI"].str.contains("Wykupienie")]

                if trend_filter == "Trend wzrostowy":
                    df_view = df_view[df_view["Trend (SMA50)"].str.contains("Wzrostowy")]
                elif trend_filter == "Trend spadkowy":
                    df_view = df_view[df_view["Trend (SMA50)"].str.contains("Spadkowy")]

                # Sortowanie po AI Score
                df_view = df_view.sort_values("AI Score", ascending=False)

                st.dataframe(df_view, use_container_width=True)
            else:
                st.info("Brak wyników skanera – sprawdź połączenie z Internetem lub tickery.")

# ---------------------------------------------------------
# Tab 5 – dziennik transakcji + metryki
# ---------------------------------------------------------
with tab5:
    st.subheader("📓 Dziennik Transakcji (Trading Journal)")
    st.caption("Notuj swoje wejścia na rynek, aby budować statystykę zysków i strat.")

    with st.expander("➕ Dodaj nową transakcję", expanded=True):
        with st.form("nowa_transakcja_form"):
            c_f1, c_f2, c_f3 = st.columns(3)
            t_aktywo = c_f1.text_input("Ticker / Aktywo:", value=ticker)
            t_kierunek = c_f2.selectbox("Kierunek:", ["KUPNO (Long)", "SPRZEDAŻ (Short)"])
            t_wolumen = c_f3.number_input(
                "Wolumen / Sztuki:",
                min_value=0.01,
                value=1.0,
                step=0.1,
            )

            c_f4, c_f5, c_f6 = st.columns(3)
            t_cena = c_f4.number_input(
                "Cena Otwarcia:",
                value=ostatnia_cena,
                format="%.4f",
            )
            t_status = c_f5.selectbox("Status:", ["Otwarte", "Zamknięte"])
            t_pnl = c_f6.number_input(
                "Wynik netto (bazowa waluta konta):",
                value=0.0,
                format="%.2f",
            )

            submit_trade = st.form_submit_button("Zapisz w dzienniku")

            if submit_trade:
                nowy_wpis = {
                    "Data": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "Aktywo": t_aktywo.upper(),
                    "Kierunek": t_kierunek,
                    "Wolumen": t_wolumen,
                    "Cena Otwarcia": t_cena,
                    "Status": t_status,
                    "Wynik (PLN)": t_pnl,
                }
                zapisz_w_dzienniku(nowy_wpis)
                st.success("✅ Dodano nową transakcję do dziennika!")
                st.rerun()

    st.markdown("---")
    st.markdown("### 📊 Zaawansowane Statystyki i Krzywa Kapitału")

    df_dziennik = wczytaj_dziennik()

    if not df_dziennik.empty:
        zamkniete = df_dziennik[df_dziennik["Status"] == "Zamknięte"].copy()

        if not zamkniete.empty:
            zamkniete["Wynik (PLN)"] = pd.to_numeric(
                zamkniete["Wynik (PLN)"], errors="coerce"
            )

            # Filtr po tickerze
            unikalne_tickers = sorted(zamkniete["Aktywo"].unique())
            ticker_filter = st.selectbox(
                "Filtruj statystyki po tickerze:",
                ["(Wszystkie)"] + unikalne_tickers,
            )

            zamkniete_view = zamkniete.copy()
            if ticker_filter != "(Wszystkie)":
                zamkniete_view = zamkniete_view[
                    zamkniete_view["Aktywo"] == ticker_filter
                ]

            total_trades = len(zamkniete_view)
            zyskownych = len(zamkniete_view[zamkniete_view["Wynik (PLN)"] > 0])
            stratnych = len(zamkniete_view[zamkniete_view["Wynik (PLN)"] <= 0])
            win_rate = (
                (zyskownych / total_trades) * 100 if total_trades > 0 else 0
            )
            suma_wynikow = zamkniete_view["Wynik (PLN)"].sum()

            # Dodatkowe metryki
            zyski = zamkniete_view[zamkniete_view["Wynik (PLN)"] > 0]["Wynik (PLN)"]
            straty = zamkniete_view[zamkniete_view["Wynik (PLN)"] < 0]["Wynik (PLN)"]

            avg_win = zyski.mean() if not zyski.empty else 0.0
            avg_loss = straty.mean() if not straty.empty else 0.0
            sum_wins = zyski.sum() if not zyski.empty else 0.0
            sum_losses = straty.sum() if not straty.empty else 0.0
            profit_factor = (
                sum_wins / abs(sum_losses) if sum_losses < 0 else np.nan
            )

            zamkniete_view["Krzywa Kapitału"] = zamkniete_view["Wynik (PLN)"].cumsum()
            rolling_max = zamkniete_view["Krzywa Kapitału"].cummax()
            drawdown = zamkniete_view["Krzywa Kapitału"] - rolling_max
            max_drawdown = drawdown.min() if not drawdown.empty else 0.0

            c_s1, c_s2, c_s3, c_s4 = st.columns(4)
            c_s1.metric("Zamknięte pozycje", total_trades)
            c_s2.metric("Skuteczność (Win Rate)", f"{win_rate:.1f}%")
            c_s3.metric("Zysk / Strata", f"{zyskownych} / {stratnych}")
            c_s4.metric("Całkowity Wynik (PnL)", f"{suma_wynikow:.2f}")

            c_s5, c_s6, c_s7, c_s8 = st.columns(4)
            c_s5.metric("Średni zysk", f"{avg_win:.2f}")
            c_s6.metric("Średnia strata", f"{avg_loss:.2f}")
            c_s7.metric("Profit Factor", f"{profit_factor:.2f}" if not np.isnan(profit_factor) else "n/a")
            c_s8.metric("Max Drawdown", f"{max_drawdown:.2f}")

            fig_eq = go.Figure()
            fig_eq.add_trace(
                go.Scatter(
                    x=zamkniete_view["Data"],
                    y=zamkniete_view["Krzywa Kapitału"],
                    mode="lines+markers",
                    name="Krzywa PnL",
                    line=dict(
                        color="lime" if suma_wynikow >= 0 else "red",
                        width=3,
                    ),
                )
            )
            fig_eq.update_layout(
                title="Krzywa Zysków i Strat",
                template="plotly_dark",
                height=350,
                margin=dict(l=20, r=20, t=40, b=20),
            )
            st.plotly_chart(fig_eq, use_container_width=True)

        st.markdown("### 📝 Pełna historia operacji")
        st.dataframe(df_dziennik, use_container_width=True)
    else:
        st.info(
            "Twój dziennik jest na razie pusty. Użyj formularza powyżej, aby dodać pierwsze zagranie."
        )
