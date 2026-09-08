import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
import feedparser
from textblob import TextBlob
from datetime import datetime
import sqlite3

# Poprawny import modułu z podfolderu modules
from modules import indicators

# --- KONFIGURACJA BAZY DANYCH (WSPÓLNA DLA BOTA TRADING212) ---
DB_NAME = "trading_history.db"

def inicjalizuj_baze():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transakcje (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT,
            nazwa TEXT,
            quantity INTEGER,
            entry_price REAL,
            sl REAL,
            tp REAL,
            entry_date TEXT,
            status TEXT,
            exit_price REAL,
            pnl REAL
        )
    ''')
    conn.commit()
    conn.close()

def pobierz_dziennik_z_bazy():
    """
    Pobiera pełny dziennik transakcji z SQLite (transakcje bota + wpisy ręczne).
    """
    inicjalizuj_baze()
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query(
        "SELECT id, ticker, nazwa, quantity, entry_price, sl, tp, "
        "entry_date, status, exit_price, pnl "
        "FROM transakcje ORDER BY entry_date",
        conn
    )
    conn.close()
    return df

def dodaj_transakcje_reczna(
    ticker: str,
    nazwa: str,
    quantity: float,
    entry_price: float,
    status: str,
    exit_price: float | None,
    pnl: float | None
):
    """
    Dodaje ręcznie wprowadzoną transakcję do tej samej bazy SQLite, co bot Trading212.
    """
    inicjalizuj_baze()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    entry_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if status == "Otwarte":
        status_db = "OPEN"
        pnl_db = 0.0 if pnl is None else float(pnl)
        exit_price_db = None
    else:
        status_db = "CLOSED"
        pnl_db = 0.0 if pnl is None else float(pnl)
        exit_price_db = None if exit_price is None else float(exit_price)

    cursor.execute('''
        INSERT INTO transakcje (
            ticker, nazwa, quantity, entry_price, sl, tp,
            entry_date, status, exit_price, pnl
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        ticker.upper(),
        nazwa,
        quantity,
        entry_price,
        0.0,
        0.0,
        entry_date,
        status_db,
        exit_price_db,
        pnl_db
    ))
    conn.commit()
    conn.close()

def policz_sharpe_z_pnl(pnls: pd.Series) -> float:
    """
    Uproszczony Sharpe: średni PnL na transakcję / odchylenie standardowe PnL (zamknięte).[web:75]
    """
    if pnls is None or len(pnls) < 2:
        return 0.0
    pnls_clean = pd.to_numeric(pnls, errors="coerce").dropna()
    if len(pnls_clean) < 2:
        return 0.0
    mean_pnl = pnls_clean.mean()
    std_pnl = pnls_clean.std()
    return float(mean_pnl / std_pnl) if std_pnl > 0 else 0.0

# --- PROSTE FUNKCJE BACKTESTU (SMA/RSI/MACD) ---
def download_data(symbol: str, period: str = "2y", interval: str = "1d") -> pd.DataFrame:
    """
    Dane z yfinance + wskaźniki z modules.indicators.[web:102][web:103]
    """
    df = yf.download(symbol, period=period, interval=interval, progress=False)
    if df is None or df.empty:
        raise ValueError(f"Nie udało się pobrać danych dla symbolu {symbol}")

    # Jeśli dane mają MultiIndex kolumn, spłaszczamy
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # Dodanie wskaźników: SMA, RSI, MACD, ATR itd.
    df = indicators.dodaj_zaawansowane_wskazniki(df)

    # Upewniamy się, że mamy podstawowe kolumny
    required_cols = ["Close", "SMA50", "RSI", "MACD", "MACD_Signal", "ATR"]
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Brakuje kolumny {col} w danych po dodaniu wskaźników")

    # Usunięcie wierszy z brakami w kluczowych kolumnach
    df = df.dropna(subset=required_cols).copy()
    return df

def run_backtest(
    df: pd.DataFrame,
    start_cash: float = 10000.0,
    risk_pct: float = 0.015,
    atr_mult: float = 2.0,
) -> dict:
    """
    Prosty backtest long-only:
      - wejście LONG gdy: Close > SMA50, RSI < 35, MACD > MACD_Signal,
      - SL/TP oparte na ATR,
      - wyjście przy SL/TP lub przy odwróceniu sygnału.
    """
    equity = start_cash
    cash = start_cash
    position_qty = 0
    entry_price = None
    sl_price = None
    tp_price = None
    entry_date = None

    equity_curve = []
    trades = []

    for idx, row in df.iterrows():
        close = float(row["Close"])
        sma50 = float(row["SMA50"])
        rsi = float(row["RSI"])
        macd = float(row["MACD"])
        macd_sig = float(row["MACD_Signal"])
        atr = float(row["ATR"])

        # aktualizacja equity przy otwartej pozycji
        if position_qty > 0 and entry_price is not None:
            equity = cash + position_qty * close
        equity_curve.append({"date": idx, "equity": equity})

        # wyjście z pozycji
        if position_qty > 0:
            exit_reason = None
            exit_price = None

            if close <= sl_price:
                exit_reason = "SL"
                exit_price = close
            elif close >= tp_price:
                exit_reason = "TP"
                exit_price = close
            elif (macd < macd_sig) or (close < sma50):
                exit_reason = "SignalExit"
                exit_price = close

            if exit_reason is not None and exit_price is not None:
                pnl = (exit_price - entry_price) * position_qty
                cash += position_qty * exit_price
                equity = cash
                trades.append({
                    "entry_date": entry_date,
                    "exit_date": idx,
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "qty": position_qty,
                    "pnl": pnl,
                    "reason": exit_reason,
                })
                position_qty = 0
                entry_price = None
                sl_price = None
                tp_price = None
                entry_date = None
                continue

        # wejście w pozycję
        if position_qty == 0:
            punkty_bycze = 0
            if close > sma50:
                punkty_bycze += 1
            if rsi < 35:
                punkty_bycze += 1
            if macd > macd_sig:
                punkty_bycze += 1

            if punkty_bycze >= 3:
                sl = close - atr * atr_mult
                tp = close + atr * atr_mult * 2.0
                if sl >= close:
                    continue

                ryzyko_max_kwota = equity * risk_pct
                risk_per_share = close - sl
                qty = int(ryzyko_max_kwota / risk_per_share) if risk_per_share > 0 else 0
                if qty < 1:
                    continue

                koszt_pozycji = qty * close
                if koszt_pozycji > cash:
                    continue

                position_qty = qty
                entry_price = close
                sl_price = sl
                tp_price = tp
                entry_date = idx

                cash -= koszt_pozycji
                equity = cash + position_qty * close

    # zamknięcie pozycji na końcu danych
    if position_qty > 0 and entry_price is not None:
        last_idx = df.index[-1]
        last_close = float(df["Close"].iloc[-1])
        pnl = (last_close - entry_price) * position_qty
        cash += position_qty * last_close
        equity = cash
        trades.append({
            "entry_date": entry_date,
            "exit_date": last_idx,
            "entry_price": entry_price,
            "exit_price": last_close,
            "qty": position_qty,
            "pnl": pnl,
            "reason": "EndOfData",
        })

    trades_df = pd.DataFrame(trades)
    equity_df = pd.DataFrame(equity_curve)

    total_pnl = trades_df["pnl"].sum() if not trades_df.empty else 0.0
    num_trades = len(trades_df)
    wins = len(trades_df[trades_df["pnl"] > 0]) if not trades_df.empty else 0
    losses = len(trades_df[trades_df["pnl"] <= 0]) if not trades_df.empty else 0
    win_rate = (wins / num_trades * 100.0) if num_trades > 0 else 0.0

    if num_trades > 1:
        mean_pnl = trades_df["pnl"].mean()
        std_pnl = trades_df["pnl"].std()
        sharpe = float(mean_pnl / std_pnl) if std_pnl > 0 else 0.0
    else:
        sharpe = 0.0

    equity_series = equity_df["equity"]
    running_max = equity_series.cummax()
    drawdown = (equity_series - running_max) / running_max
    max_dd = float(drawdown.min()) if len(drawdown) > 0 else 0.0

    result = {
        "start_cash": start_cash,
        "end_equity": float(equity_df["equity"].iloc[-1]) if not equity_df.empty else start_cash,
        "total_pnl": float(total_pnl),
        "num_trades": int(num_trades),
        "wins": int(wins),
        "losses": int(losses),
        "win_rate": float(win_rate),
        "sharpe": float(sharpe),
        "max_drawdown_pct": max_dd * 100.0,
        "trades_df": trades_df,
        "equity_df": equity_df,
    }
    return result

# --- KONFIGURACJA STRONY STREAMLIT ---
st.set_page_config(page_title="AI Trading Copilot Pro", layout="wide", page_icon="📈")

st.title("🤖 AI Trading & Investment Copilot")
st.caption("Wsparcie decyzji inwestycyjnych: Wall Street, GPW, Surowce, ETF (Trading212)")

# Predefiniowana baza aktywów (używana też w backteście)
popularne_aktywa = {
    "Złoto CFD / Futures (GC=F)": {"ticker": "GC=F", "search_term": "Gold price commodity market"},
    "Ropa WTI (CL=F)": {"ticker": "CL=F", "search_term": "Crude oil price energy market"},
    "NVIDIA (NVDA)": {"ticker": "NVDA", "search_term": "NVIDIA stock news"},
    "Apple (AAPL)": {"ticker": "AAPL", "search_term": "Apple stock market news"},
    "Microsoft (MSFT)": {"ticker": "MSFT", "search_term": "Microsoft stock news"},
    "Tesla (TSLA)": {"ticker": "TSLA", "search_term": "Tesla stock market news"},
    "S&P 500 ETF (SPY)": {"ticker": "SPY", "search_term": "S&P 500 index market today"},
    "CD Projekt (CDR.WA)": {"ticker": "CDR.WA", "search_term": "CD Projekt gielda akcje"},
    "Orlen (PKN.WA)": {"ticker": "PKN.WA", "search_term": "PKN Orlen gielda GPW"},
    "PKO BP (PKO.WA)": {"ticker": "PKO.WA", "search_term": "PKO BP bank gielda GPW"},
    "KGHM (KGH.WA)": {"ticker": "KGH.WA", "search_term": "KGHM miedz gielda GPW"},
    "Dino Polska (DNP.WA)": {"ticker": "DNP.WA", "search_term": "Dino Polska gielda GPW"}
}

# --- PANEL BOCZNY (Sidebar) ---
st.sidebar.header("⚙️ Ustawienia analizy")
wybor_predefiniowany = st.sidebar.selectbox(
    "Wybierz z listy:",
    ["Wpisz własny..."] + list(popularne_aktywa.keys())
)

if wybor_predefiniowany == "Wpisz własny...":
    ticker = st.sidebar.text_input(
        "Wpisz Ticker (np. TSLA, KGH.WA, GC=F):",
        value="GC=F"
    ).upper()
    search_query = ticker.replace(".WA", "") + " stock market news"
else:
    ticker = popularne_aktywa[wybor_predefiniowany]["ticker"]
    search_query = popularne_aktywa[wybor_predefiniowany]["search_term"]

okres = st.sidebar.selectbox("Zakres czasu:", ["1mo", "3mo", "6mo", "1y", "2y"], index=4)
interwal = st.sidebar.selectbox("Interwał:", ["1d", "1wk"], index=0)

st.sidebar.markdown("---")
st.sidebar.header("⚖️ Kalkulator Wielkości Pozycji")
kapital = st.sidebar.number_input(
    "Twój kapitał (PLN / USD):",
    min_value=100.0,
    value=10000.0,
    step=500.0
)
ryzyko_proc = st.sidebar.slider(
    "Dopuszczalne ryzyko transakcji (%):",
    min_value=0.5,
    max_value=5.0,
    value=1.5,
    step=0.5
)

# --- FUNKCJE DANYCH I WSKAŹNIKÓW ---
@st.cache_data(ttl=180)
def pobierz_dane(symbol, period, interval):
    try:
        dane = yf.download(symbol, period=period, interval=interval, progress=False)
        if dane is not None and not dane.empty:
            if isinstance(dane.columns, pd.MultiIndex):
                dane.columns = dane.columns.get_level_values(0)
            dane = indicators.dodaj_zaawansowane_wskazniki(dane)
        return dane
    except Exception:
        return None

df = pobierz_dane(ticker, okres, interwal)

if df is None or df.empty:
    st.error(f"Nie udało się pobrać danych dla symbolu: **{ticker}**. Sprawdź poprawność tickera.")
    st.stop()

ostatnia_cena = float(df['Close'].iloc[-1])
poprzednia_cena = float(df['Close'].iloc[-2])
zmiana_proc = ((ostatnia_cena - poprzednia_cena) / poprzednia_cena) * 100
ostatni_rsi = float(df['RSI'].iloc[-1]) if not pd.isna(df['RSI'].iloc[-1]) else 50.0
ostatnie_sma50 = float(df['SMA50'].iloc[-1]) if 'SMA50' in df.columns and not pd.isna(df['SMA50'].iloc[-1]) else ostatnia_cena
ostatnie_sma200 = float(df['SMA200'].iloc[-1]) if 'SMA200' in df.columns and not pd.isna(df['SMA200'].iloc[-1]) else ostatnie_sma50
bb_lower = float(df['BB_Lower'].iloc[-1]) if 'BB_Lower' in df.columns and not pd.isna(df['BB_Lower'].iloc[-1]) else ostatnia_cena
bb_upper = float(df['BB_Upper'].iloc[-1]) if 'BB_Upper' in df.columns and not pd.isna(df['BB_Upper'].iloc[-1]) else ostatnia_cena
obv = float(df['OBV'].iloc[-1]) if 'OBV' in df.columns and not pd.isna(df['OBV'].iloc[-1]) else 0.0
obv_sma = float(df['OBV_SMA'].iloc[-1]) if 'OBV_SMA' in df.columns and not pd.isna(df['OBV_SMA'].iloc[-1]) else 0.0
ostatni_macd = float(df['MACD'].iloc[-1]) if not pd.isna(df['MACD'].iloc[-1]) else 0.0
ostatni_macd_sig = float(df['MACD_Signal'].iloc[-1]) if not pd.isna(df['MACD_Signal'].iloc[-1]) else 0.0
ostatni_atr = float(df['ATR'].iloc[-1]) if not pd.isna(df['ATR'].iloc[-1]) else (ostatnia_cena * 0.02)

# --- NEWSY / SENTYMENT ---
@st.cache_data(ttl=300)
def pobierz_swieze_newsy(symbol, query):
    news_list = []
    try:
        yf_ticker = yf.Ticker(symbol)
        raw_news = yf_ticker.news
        if raw_news:
            for n in raw_news[:6]:
                tytul = n.get('title', '')
                link = n.get('link', '#')
                ts = n.get('providerPublishTime', None)
                data_str = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M') if ts else "Świeże"
                zrodlo = n.get('publisher', 'Yahoo Finance')
                if tytul:
                    news_list.append({"tytul": tytul, "link": link, "data": data_str, "zrodlo": zrodlo})
    except Exception:
        pass

    if len(news_list) < 2:
        is_pl = symbol.endswith(".WA")
        lang = "pl" if is_pl else "en-US"
        gl = "PL" if is_pl else "US"
        ceid = "PL:pl" if is_pl else "US:en"
        clean_q = query.replace(" ", "+")
        rss_url = f"https://news.google.com/rss/search?q={clean_q}+when:3d&hl={lang}&gl={gl}&ceid={ceid}"
        feed = feedparser.parse(rss_url)
        if feed.entries:
            for entry in feed.entries[:6]:
                news_list.append({
                    "tytul": entry.title,
                    "link": entry.link,
                    "data": entry.published if 'published' in entry else 'Ostatnie dni',
                    "zrodlo": "Google News / Portale"
                })
    return news_list

surowe_newsy = pobierz_swieze_newsy(ticker, search_query)
sentymenty = []
news_items = []

for item in surowe_newsy:
    analiza = TextBlob(item["tytul"])
    polaryzacja = analiza.sentiment.polarity
    sentymenty.append(polaryzacja)
    kolor = "🟢 Pozytywny" if polaryzacja > 0.05 else ("🔴 Negatywny" if polaryzacja < -0.05 else "⚪ Neutralny")
    news_items.append({
        "tytul": item["tytul"],
        "score": polaryzacja,
        "status": kolor,
        "data": item["data"],
        "zrodlo": item["zrodlo"],
        "link": item["link"]
    })

avg_sent = sum(sentymenty) / len(sentymenty) if sentymenty else 0.0

# --- SILNIK DECYZYJNY ---
punkty_bycze = 0
punkty_niedzwiedzie = 0
jakosc_flags = []

if ostatnie_sma50 > ostatnie_sma200:
    punkty_bycze += 1
    trend_opis = "HOSSA (SMA50 > SMA200)"
    jakosc_flags.append("✅ Reżim rynkowy: Hossa")
else:
    punkty_niedzwiedzie += 1
    trend_opis = "BESSA / KONSOLIDACJA (SMA50 < SMA200)"
    jakosc_flags.append("⚠️ Reżim rynkowy: Ostrożnie (Bessa/Konsolidacja)")

if ostatnia_cena <= bb_lower:
    punkty_bycze += 2
    jakosc_flags.append("🟢 Ekstremalne wyprzedanie (Dolna wstęga Bollingera)")
elif ostatnia_cena >= bb_upper:
    punkty_niedzwiedzie += 2
    jakosc_flags.append("🔴 Ekstremalne wykupienie (Górna wstęga Bollingera)")

if obv > obv_sma:
    punkty_bycze += 1
    jakosc_flags.append("📈 Wolumen wspiera ruch (OBV > SMA)")
else:
    punkty_niedzwiedzie += 1
    jakosc_flags.append("📉 Brak wsparcia wolumenowego (OBV < SMA)")

if ostatni_rsi < 35:
    punkty_bycze += 1
    rsi_opis = "Wyprzedanie (RSI < 35)"
elif ostatni_rsi > 70:
    punkty_niedzwiedzie += 1
    rsi_opis = "Wykupienie (RSI > 70)"
else:
    rsi_opis = "RSI Neutralny"

if ostatni_macd > ostatni_macd_sig:
    punkty_bycze += 1
    macd_opis = "MACD > Sygnał (Prowzrostowo)"
else:
    punkty_niedzwiedzie += 1
    macd_opis = "MACD < Sygnał (Prospadkowo)"

if avg_sent > 0.05:
    punkty_bycze += 1
    sent_opis = "Pozytywny / Byczy"
elif avg_sent < -0.05:
    punkty_niedzwiedzie += 1
    sent_opis = "Negatywny / Niedźwiedzi"
else:
    sent_opis = "Neutralny"

if punkty_bycze >= 4:
    werdykt_status = "MOCNY KANDYDAT NA LONGA (KUPNO)"
    werdykt_kolor = "success"
    werdykt_komentarz = "Przewaga sygnałów prowzrostowych w połączeniu z reżimem rynkowym."
elif punkty_niedzwiedzie >= 4:
    werdykt_status = "OSTRZEŻENIE / KANDYDAT NA SHORTA"
    werdykt_kolor = "error"
    werdykt_komentarz = "Przewaga sygnałów prospadkowych lub silnego przegrzania."
else:
    werdykt_status = "NEUTRALNY / OBSERWACJA"
    werdykt_kolor = "info"
    werdykt_komentarz = "Rynek w konsolidacji lub sygnały są sprzeczne. Wstrzymaj się."
