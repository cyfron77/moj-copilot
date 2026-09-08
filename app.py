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
    cursor.execute(
        """
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
        """
    )
    conn.commit()
    conn.close()


def pobierz_dziennik_z_bazy() -> pd.DataFrame:
    """
    Pobiera pełny dziennik transakcji z SQLite (transakcje bota + wpisy ręczne).
    """
    inicjalizuj_baze()
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query(
        """
        SELECT
            id,
            ticker,
            nazwa,
            quantity,
            entry_price,
            sl,
            tp,
            entry_date,
            status,
            exit_price,
            pnl
        FROM transakcje
        ORDER BY entry_date
        """,
        conn,
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
    pnl: float | None,
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

    cursor.execute(
        """
        INSERT INTO transakcje (
            ticker,
            nazwa,
            quantity,
            entry_price,
            sl,
            tp,
            entry_date,
            status,
            exit_price,
            pnl
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            ticker.upper(),
            nazwa,
            quantity,
            entry_price,
            0.0,
            0.0,
            entry_date,
            status_db,
            exit_price_db,
            pnl_db,
        ),
    )
    conn.commit()
    conn.close()


def policz_sharpe_z_pnl(pnls: pd.Series) -> float:
    """
    Uproszczony Sharpe: średni PnL na transakcję / odchylenie standardowe PnL (zamknięte).
    """
    if pnls is None or len(pnls) < 2:
        return 0.0
    pnls_clean = pd.to_numeric(pnls, errors="coerce").dropna()
    if len(pnls_clean) < 2:
        return 0.0
    mean_pnl = pnls_clean.mean()
    std_pnl = pnls_clean.std()
    return float(mean_pnl / std_pnl) if std_pnl > 0 else 0.0


# --- PROSTE FUNKCJE BACKTESTU (SMA50 / SMA200) ---
def download_data(symbol: str, period: str = "5y", interval: str = "1d") -> pd.DataFrame:
    """
    Dane z yfinance (domyślnie 5 lat, D1) + wskaźniki z modules.indicators.
    """
    df = yf.download(symbol, period=period, interval=interval, progress=False)
    if df is None or df.empty:
        raise ValueError(f"Nie udało się pobrać danych dla symbolu {symbol}")

    # Jeśli dane mają MultiIndex kolumn, spłaszczamy
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # Dodanie wskaźników: SMA, RSI, MACD, ATR, Bollinger, OBV itd.
    df = indicators.dodaj_zaawansowane_wskazniki(df)

    # Upewniamy się, że mamy podstawowe kolumny
    required_cols = ["Close", "SMA50", "SMA200"]
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Brakuje kolumny {col} w danych po dodaniu wskaźników")

    df = df.dropna(subset=required_cols).copy()
    return df


def run_backtest_sma_crossover(
    df: pd.DataFrame,
    start_cash: float = 10000.0,
) -> dict:
    """
    Prosty backtest 50/200 SMA (tzw. golden cross / death cross):
      - Kupno (long) przy golden cross:
        SMA50 przecina SMA200 od dołu (wcześniej <=, teraz >).
      - Wyjście do gotówki przy death cross:
        SMA50 przecina SMA200 od góry (wcześniej >=, teraz <).
      - Brak shortów, zawsze tylko: long albo gotówka.[web:189][web:193]
      - Pozycja = cały dostępny kapitał (buy & hold w okresach HOSSY wg SMA).
    """
    close = df["Close"]
    sma50 = df["SMA50"]
    sma200 = df["SMA200"]

    cash = start_cash
    position_qty = 0
    entry_price = None
    entry_date = None

    equity_curve = []
    trades = []

    entry_signals = 0
    entries_opened = 0

    for i in range(1, len(df)):
        price_prev = close.iloc[i - 1]
        price_now = close.iloc[i]
        sma50_prev = sma50.iloc[i - 1]
        sma200_prev = sma200.iloc[i - 1]
        sma50_now = sma50.iloc[i]
        sma200_now = sma200.iloc[i]
        dt = df.index[i]

        # aktualny equity (dla krzywej kapitału)
        if position_qty > 0 and entry_price is not None:
            equity = cash + position_qty * price_now
        else:
            equity = cash
        equity_curve.append({"date": dt, "equity": equity})

        # sygnał wyjścia (death cross)
        if position_qty > 0:
            if sma50_prev >= sma200_prev and sma50_now < sma200_now:
                exit_price = price_now
                pnl = (exit_price - entry_price) * position_qty
                cash += position_qty * exit_price
                trades.append(
                    {
                        "entry_date": entry_date,
                        "exit_date": dt,
                        "entry_price": entry_price,
                        "exit_price": exit_price,
                        "qty": position_qty,
                        "pnl": pnl,
                        "reason": "DeathCross",
                    }
                )
                position_qty = 0
                entry_price = None
                entry_date = None
                continue

        # sygnał wejścia (golden cross)
        if position_qty == 0:
            if sma50_prev <= sma200_prev and sma50_now > sma200_now:
                entry_signals += 1
                # kupujemy za cały kapitał
                qty = int(cash // price_now)
                if qty > 0:
                    position_qty = qty
                    entry_price = price_now
                    entry_date = dt
                    cash -= qty * price_now
                    entries_opened += 1

    # zamknięcie pozycji na końcu danych (jeśli coś zostało)
    if position_qty > 0 and entry_price is not None:
        last_price = close.iloc[-1]
        last_dt = df.index[-1]
        pnl = (last_price - entry_price) * position_qty
        cash += position_qty * last_price
        trades.append(
            {
                "entry_date": entry_date,
                "exit_date": last_dt,
                "entry_price": entry_price,
                "exit_price": last_price,
                "qty": position_qty,
                "pnl": pnl,
                "reason": "EndOfData",
            }
        )
        equity = cash
        equity_curve.append({"date": last_dt, "equity": equity})
    else:
        equity = cash

    trades_df = pd.DataFrame(trades)
    equity_df = pd.DataFrame(equity_curve).drop_duplicates(subset=["date"])

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

    if not equity_df.empty:
        equity_series = equity_df["equity"]
        running_max = equity_series.cummax()
        drawdown = (equity_series - running_max) / running_max
        max_dd = float(drawdown.min()) * 100.0
        end_equity = float(equity_series.iloc[-1])
    else:
        max_dd = 0.0
        end_equity = start_cash

    result = {
        "start_cash": start_cash,
        "end_equity": end_equity,
        "total_pnl": float(total_pnl),
        "num_trades": int(num_trades),
        "wins": int(wins),
        "losses": int(losses),
        "win_rate": float(win_rate),
        "sharpe": float(sharpe),
        "max_drawdown_pct": max_dd,
        "entry_signals": int(entry_signals),
        "entries_opened": int(entries_opened),
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
    "Dino Polska (DNP.WA)": {"ticker": "DNP.WA", "search_term": "Dino Polska gielda GPW"},
}

# --- PANEL BOCZNY (Sidebar) ---
st.sidebar.header("⚙️ Ustawienia analizy")
wybor_predefiniowany = st.sidebar.selectbox(
    "Wybierz z listy:",
    ["Wpisz własny..."] + list(popularne_aktywa.keys()),
)

if wybor_predefiniowany == "Wpisz własny...":
    ticker = st.sidebar.text_input(
        "Wpisz Ticker (np. TSLA, KGH.WA, GC=F):",
        value="GC=F",
    ).upper()
    search_query = ticker.replace(".WA", "") + " stock market news"
else:
    ticker = popularne_aktywa[wybor_predefiniowany]["ticker"]
    search_query = popularne_aktywa[wybor_predefiniowany]["search_term"]

okres = st.sidebar.selectbox("Zakres czasu:", ["1mo", "3mo", "6mo", "1y", "2y", "5y"], index=5)
interwal = st.sidebar.selectbox("Interwał:", ["1d", "1wk"], index=0)

st.sidebar.markdown("---")
st.sidebar.header("⚖️ Kalkulator Wielkości Pozycji")
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

ostatnia_cena = float(df["Close"].iloc[-1])
poprzednia_cena = float(df["Close"].iloc[-2])
zmiana_proc = ((ostatnia_cena - poprzednia_cena) / poprzednia_cena) * 100
ostatni_rsi = float(df["RSI"].iloc[-1]) if "RSI" in df.columns and not pd.isna(df["RSI"].iloc[-1]) else 50.0
ostatnie_sma50 = (
    float(df["SMA50"].iloc[-1]) if "SMA50" in df.columns and not pd.isna(df["SMA50"].iloc[-1]) else ostatnia_cena
)
ostatnie_sma200 = (
    float(df["SMA200"].iloc[-1]) if "SMA200" in df.columns and not pd.isna(df["SMA200"].iloc[-1]) else ostatnie_sma50
)
bb_lower = (
    float(df["BB_Lower"].iloc[-1]) if "BB_Lower" in df.columns and not pd.isna(df["BB_Lower"].iloc[-1]) else ostatnia_cena
)
bb_upper = (
    float(df["BB_Upper"].iloc[-1]) if "BB_Upper" in df.columns and not pd.isna(df["BB_Upper"].iloc[-1]) else ostatnia_cena
)
obv = float(df["OBV"].iloc[-1]) if "OBV" in df.columns and not pd.isna(df["OBV"].iloc[-1]) else 0.0
obv_sma = float(df["OBV_SMA"].iloc[-1]) if "OBV_SMA" in df.columns and not pd.isna(df["OBV_SMA"].iloc[-1]) else 0.0
ostatni_macd = float(df["MACD"].iloc[-1]) if "MACD" in df.columns and not pd.isna(df["MACD"].iloc[-1]) else 0.0
ostatni_macd_sig = (
    float(df["MACD_Signal"].iloc[-1]) if "MACD_Signal" in df.columns and not pd.isna(df["MACD_Signal"].iloc[-1]) else 0.0
)
ostatni_atr = float(df["ATR"].iloc[-1]) if "ATR" in df.columns and not pd.isna(df["ATR"].iloc[-1]) else (ostatnia_cena * 0.02)

# --- NEWSY / SENTYMENT ---
@st.cache_data(ttl=300)
def pobierz_swieze_newsy(symbol, query):
    news_list = []
    try:
        yf_ticker = yf.Ticker(symbol)
        raw_news = yf_ticker.news
        if raw_news:
            for n in raw_news[:6]:
                tytul = n.get("title", "")
                link = n.get("link", "#")
                ts = n.get("providerPublishTime", None)
                data_str = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M") if ts else "Świeże"
                zrodlo = n.get("publisher", "Yahoo Finance")
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
                news_list.append(
                    {
                        "tytul": entry.title,
                        "link": entry.link,
                        "data": entry.published if "published" in entry else "Ostatnie dni",
                        "zrodlo": "Google News / Portale",
                    }
                )
    return news_list


surowe_newsy = pobierz_swieze_newsy(ticker, search_query)
sentymenty = []
news_items = []

for item in surowe_newsy:
    analiza = TextBlob(item["tytul"])
    polaryzacja = analiza.sentiment.polarity
    sentymenty.append(polaryzacja)
    kolor = "🟢 Pozytywny" if polaryzacja > 0.05 else ("🔴 Negatywny" if polaryzacja < -0.05 else "⚪ Neutralny")
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

# --- GŁÓWNY PANEL GÓRNY ---
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Ticker", ticker)
c2.metric("Kurs", f"{ostatnia_cena:.2f}", f"{zmiana_proc:+.2f}%")
c3.metric("Reżim Rynku", trend_opis)
c4.metric("RSI (14)", f"{ostatni_rsi:.1f}", rsi_opis)
c5.metric("Zmienność ATR (14)", f"{ostatni_atr:.2f}", "Średni zasięg świecy")

flagi_tekst = "\n- ".join(jakosc_flags)
komunikat_werdyktu = (
    f"🎯 **WERDYKT AI COPILOTA: {werdykt_status}**\n\n"
    f"**Wykryte flagi systemowe:**\n- {flagi_tekst}\n\n"
    f"*{werdykt_komentarz}*"
)
if werdykt_kolor == "success":
    st.success(komunikat_werdyktu)
elif werdykt_kolor == "error":
    st.error(komunikat_werdyktu)
else:
    st.info(komunikat_werdyktu)

# --- ZAKŁADKI ---
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
    [
        "📈 Wykres (Wstęgi + SMA200 + MACD)",
        "🤖 Analiza Sentymentu (AI)",
        "⚖️ Kalkulator Pozycji & ATR",
        "🔍 Skaner Rynku (GPW & USA)",
        "📓 Dziennik Transakcji (SQLite)",
        "🔁 Backtest SMA50/200",
    ]
)

with tab1:
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        row_heights=[0.7, 0.3],
    )

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
    if "SMA200" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["SMA200"],
                line=dict(color="purple", width=2),
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

    fig.update_layout(
        title=f"Analiza techniczna: {ticker}",
        xaxis_rangeslider_visible=False,
        height=620,
        template="plotly_dark",
        margin=dict(l=20, r=20, t=40, b=20),
    )
    st.plotly_chart(fig, use_container_width=True)

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

with tab3:
    st.subheader("⚖️ Inteligentny Kalkulator Pozycji i Ryzyka (Zmienność ATR)")

    mnoznik_atr = st.slider(
        "Mnożnik ATR dla Stop Lossa (Zalecane: 1.5x - 2.5x):",
        min_value=1.0,
        max_value=4.0,
        value=2.0,
        step=0.5,
    )
    sugerowany_sl_long = float(round(ostatnia_cena - (ostatni_atr * mnoznik_atr), 2))
    sugerowany_tp_long = float(round(ostatnia_cena + (ostatni_atr * mnoznik_atr * 2.0), 2))

    c_sl, c_tp = st.columns(2)
    with c_sl:
        stop_loss = st.number_input("Poziom Stop Loss (SL):", value=sugerowany_sl_long)
    with c_tp:
        take_profit = st.number_input("Poziom Take Profit (TP):", value=sugerowany_tp_long)

    roznica_sl = abs(ostatnia_cena - stop_loss)
    if roznica_sl > 0:
        max_strata_kwota = kapital * (ryzyko_proc / 100)
        rekomendowana_liczba = int(max_strata_kwota / roznica_sl)
        wartosc_pozycji = rekomendowana_liczba * ostatnia_cena
        r_r = abs(take_profit - ostatnia_cena) / roznica_sl

        st.success(
            f"🎯 Parametry zlecenia:\n\n"
            f"- Zalecana wielkość pozycji: **{rekomendowana_liczba}** sztuk / kontraktów\n"
            f"- Łączna wartość transakcji: **{wartosc_pozycji:,.2f}**\n"
            f"- Ryzyko kapitałowe (Max strata): **{max_strata_kwota:,.2f}** ({ryzyko_proc}%)\n"
            f"- Stosunek Zysku do Ryzyka (Risk/Reward): **1 : {r_r:.2f}**"
        )
    else:
        st.warning("Stop Loss nie może być równy bieżącej cenie.")

with tab4:
    st.subheader("🔍 Skaner Okazji Rynkowych")
    if st.button("🚀 Uruchom skanowanie rynku"):
        with st.spinner("Skanowanie w toku..."):
            wyniki_skanera = []
            for nazwa, dane_aktyw in popularne_aktywa.items():
                sym = dane_aktyw["ticker"]
                d_skan = pobierz_dane(sym, "3mo", "1d")
                if d_skan is not None and not d_skan.empty:
                    cena = float(d_skan["Close"].iloc[-1])
                    rsi_val = float(d_skan["RSI"].iloc[-1]) if "RSI" in d_skan.columns and not pd.isna(d_skan["RSI"].iloc[-1]) else 50.0
                    sma50_val = float(d_skan["SMA50"].iloc[-1]) if "SMA50" in d_skan.columns and not pd.isna(d_skan["SMA50"].iloc[-1]) else cena
                    atr_val = float(d_skan["ATR"].iloc[-1]) if "ATR" in d_skan.columns and not pd.isna(d_skan["ATR"].iloc[-1]) else 0.0
                    trend = "🟢 Wzrostowy" if cena > sma50_val else "🔴 Spadkowy"

                    if rsi_val < 35:
                        stan_rsi = "🔥 Wyprzedanie (<35)"
                    elif rsi_val > 70:
                        stan_rsi = "⚠️ Wykupienie (>70)"
                    else:
                        stan_rsi = "Neutralne"

                    wyniki_skanera.append(
                        {
                            "Aktywo": nazwa,
                            "Ticker": sym,
                            "Cena": f"{cena:.2f}",
                            "RSI (14)": f"{rsi_val:.1f}",
                            "Stan RSI": stan_rsi,
                            "ATR": f"{atr_val:.2f}",
                            "Trend (SMA50)": trend,
                        }
                    )

            df_skaner = pd.DataFrame(wyniki_skanera)
            st.dataframe(df_skaner, use_container_width=True)

with tab5:
    st.subheader("📓 Dziennik Transakcji (Wspólna baza SQLite)")

    st.markdown(
        "Ten dziennik korzysta z tej samej bazy `trading_history.db`, której używa bot "
        "Trading212 – tutaj widzisz jednocześnie transakcje automatyczne i ręczne."
    )

    with st.expander("➕ Dodaj nową transakcję ręcznie do SQLite", expanded=False):
        with st.form("nowa_transakcja_form"):
            c_f1, c_f2, c_f3 = st.columns(3)
            t_aktywo = c_f1.text_input("Ticker (np. TSLA, CDR.WA):", value=ticker)
            t_nazwa = c_f2.text_input(
                "Nazwa aktywa (opis):",
                value=wybor_predefiniowany if wybor_predefiniowany != "Wpisz własny..." else t_aktywo,
            )
            t_wolumen = c_f3.number_input("Wolumen:", min_value=0.01, value=1.0, step=0.1)

            c_f4, c_f5, c_f6 = st.columns(3)
            t_cena = c_f4.number_input("Cena Otwarcia:", value=ostatnia_cena, format="%.4f")
            t_status = c_f5.selectbox("Status:", ["Otwarte", "Zamknięte"])
            t_pnl = c_f6.number_input("Wynik netto (PLN, dla Zamkniętej):", value=0.0, format="%.2f")

            submit_trade = st.form_submit_button("Zapisz w bazie SQLite")

            if submit_trade:
                try:
                    dodaj_transakcje_reczna(
                        ticker=t_aktywo,
                        nazwa=t_nazwa,
                        quantity=t_wolumen,
                        entry_price=t_cena,
                        status=t_status,
                        exit_price=None,
                        pnl=t_pnl,
                    )
                    st.success("✅ Dodano transakcję do bazy SQLite!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Błąd zapisu do bazy SQLite: {e}")

    st.markdown("---")
    st.markdown("### 📊 Statystyki, filtry i krzywa kapitału (z bazy SQLite)")

    df_dziennik = pobierz_dziennik_z_bazy()

    if not df_dziennik.empty:
        df_dziennik["entry_date"] = pd.to_datetime(df_dziennik["entry_date"], errors="coerce")

        c_flt1, c_flt2, c_flt3 = st.columns(3)
        unikalne_tickery = sorted(df_dziennik["ticker"].dropna().unique().tolist())
        filtr_ticker = c_flt1.multiselect(
            "Filtr: Ticker",
            options=unikalne_tickery,
            default=unikalne_tickery,
        )

        filtr_status = c_flt2.multiselect(
            "Filtr: Status",
            options=["OPEN", "CLOSED"],
            default=["OPEN", "CLOSED"],
        )

        min_date = df_dziennik["entry_date"].min()
        max_date = df_dziennik["entry_date"].max()
        if pd.isna(min_date) or pd.isna(max_date):
            min_date = datetime.now()
            max_date = datetime.now()
        filtr_data_od = c_flt3.date_input("Data od:", value=min_date.date())
        filtr_data_do = c_flt3.date_input("Data do:", value=max_date.date())

        df_filt = df_dziennik.copy()
        if filtr_ticker:
            df_filt = df_filt[df_filt["ticker"].isin(filtr_ticker)]
        if filtr_status:
            df_filt = df_filt[df_filt["status"].isin(filtr_status)]
        if filtr_data_od and filtr_data_do:
            df_filt = df_filt[
                (df_filt["entry_date"].dt.date >= filtr_data_od)
                & (df_filt["entry_date"].dt.date <= filtr_data_do)
            ]

        zamkniete = df_filt[df_filt["status"] == "CLOSED"].copy()

        if not zamkniete.empty:
            zamkniete["pnl"] = pd.to_numeric(zamkniete["pnl"], errors="coerce")

            total_trades = len(zamkniete)
            zyskownych = len(zamkniete[zamkniete["pnl"] > 0])
            stratnych = len(zamkniete[zamkniete["pnl"] <= 0])
            win_rate = (zyskownych / total_trades) * 100 if total_trades > 0 else 0
            suma_wynikow = zamkniete["pnl"].sum()
            sharpe = policz_sharpe_z_pnl(zamkniete["pnl"])

            c_s1, c_s2, c_s3, c_s4, c_s5 = st.columns(5)
            c_s1.metric("Zamknięte pozycje (filtr)", total_trades)
            c_s2.metric("Skuteczność (Win Rate)", f"{win_rate:.1f}%")
            c_s3.metric("Zysk / Strata", f"{zyskownych} / {stratnych}")
            c_s4.metric("Całkowity PnL (filtr)", f"{suma_wynikow:.2f} PLN")
            c_s5.metric("Sharpe (filtr)", f"{sharpe:.2f}")

            zamkniete_sorted = zamkniete.sort_values("entry_date").copy()
            zamkniete_sorted["Krzywa Kapitału"] = zamkniete_sorted["pnl"].cumsum()
            fig_eq = go.Figure()
            fig_eq.add_trace(
                go.Scatter(
                    x=zamkniete_sorted["entry_date"],
                    y=zamkniete_sorted["Krzywa Kapitału"],
                    mode="lines+markers",
                    name="Krzywa PnL",
                    line=dict(color="lime" if suma_wynikow >= 0 else "red", width=3),
                )
            )
            fig_eq.update_layout(
                title="Krzywa Zysków i Strat (SQLite, po filtrach)",
                template="plotly_dark",
                height=350,
                margin=dict(l=20, r=20, t=40, b=20),
            )
            st.plotly_chart(fig_eq, use_container_width=True)
        else:
            st.info("Brak zamkniętych transakcji w przefiltrowanym zakresie.")

        st.markdown("### 📤 Eksport przefiltrowanego dziennika")
        csv_bytes = df_filt.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Pobierz jako CSV",
            data=csv_bytes,
            file_name="dziennik_transakcji_filtrowany.csv",
            mime="text/csv",
        )

        st.markdown("### 📝 Pełna historia operacji (po filtrach)")
        st.dataframe(df_filt, use_container_width=True)
    else:
        st.info("Baza `transakcje` jest obecnie pusta – brak danych do wyświetlenia.")

with tab6:
    st.subheader("🔁 Backtest strategii SMA50/SMA200 (golden/death cross)")

    st.info(
        "Strategia: kupno przy golden cross (SMA50 przecina SMA200 od dołu), "
        "wyjście do gotówki przy death cross (SMA50 przecina SMA200 od góry). "
        "Brak shortów – tylko long lub cash.[web:189][web:193]"
    )

    if st.button("🚀 Uruchom backtest dla wszystkich walorów", type="primary"):
        wyniki = []
        with st.spinner("Uruchamiam backtesty..."):
            for nazwa, dane_aktyw in popularne_aktywa.items():
                symbol = dane_aktyw["ticker"]
                st.write(f"➡️ Backtest dla: {nazwa} ({symbol})...")
                try:
                    df_bt = download_data(symbol, period="5y", interval="1d")
                    res = run_backtest_sma_crossover(df_bt)

                    wyniki.append(
                        {
                            "Aktywo": nazwa,
                            "Ticker": symbol,
                            "End Equity": res["end_equity"],
                            "Total PnL": res["total_pnl"],
                            "Trades": res["num_trades"],
                            "WinRate%": res["win_rate"],
                            "Sharpe": res["sharpe"],
                            "MaxDrawdown%": res["max_drawdown_pct"],
                            "EntrySignals": res["entry_signals"],
                            "EntriesOpened": res["entries_opened"],
                        }
                    )
                except Exception as e:
                    wyniki.append(
                        {
                            "Aktywo": nazwa,
                            "Ticker": symbol,
                            "End Equity": None,
                            "Total PnL": None,
                            "Trades": None,
                            "WinRate%": None,
                            "Sharpe": None,
                            "MaxDrawdown%": None,
                            "EntrySignals": None,
                            "EntriesOpened": None,
                            "Error": str(e),
                        }
                    )

        df_wyniki = pd.DataFrame(wyniki)
        st.markdown("### 📊 Zbiorcze wyniki backtestu SMA50/200")
        st.dataframe(df_wyniki, use_container_width=True)

        csv_data = df_wyniki.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Pobierz wyniki jako CSV",
            data=csv_data,
            file_name="backtest_sma50_200_all_symbols.csv",
            mime="text/csv",
        )
