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
import re

# Konfiguracja strony
st.set_page_config(page_title="AI Trading Copilot Pro", layout="wide", page_icon="📈")

st.title("🤖 AI Trading & Investment Copilot")
st.caption("Wsparcie decyzji inwestycyjnych: Wall Street, GPW, Surowce, CFD (XTB)")

# Predefiniowana baza aktywów
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

# --- FUNKCJE DZIENNIKA TRANSAKCJI ---
PLIK_DZIENNIKA = "dziennik_transakcji.csv"

def wczytaj_dziennik():
    if os.path.exists(PLIK_DZIENNIKA):
        try:
            return pd.read_csv(PLIK_DZIENNIKA)
        except:
            pass
    return pd.DataFrame(columns=["Data", "Aktywo", "Kierunek", "Wolumen", "Cena Otwarcia", "Status", "Wynik (PLN)"])

def zapisz_w_dzienniku(nowy_wpis):
    df = wczytaj_dziennik()
    df = pd.concat([df, pd.DataFrame([nowy_wpis])], ignore_index=True)
    df.to_csv(PLIK_DZIENNIKA, index=False)

# --- PANEL BOCZNY (Sidebar) ---
st.sidebar.header("⚙️ Ustawienia analizy")
wybor_predefiniowany = st.sidebar.selectbox("Wybierz z listy:", ["Wpisz własny..."] + list(popularne_aktywa.keys()))

if wybor_predefiniowany == "Wpisz własny...":
    ticker = st.sidebar.text_input("Wpisz Ticker (np. TSLA, KGH.WA, GC=F):", value="GC=F").upper()
    search_query = ticker.replace(".WA", "") + " stock market news"
else:
    ticker = popularne_aktywa[wybor_predefiniowany]["ticker"]
    search_query = popularne_aktywa[wybor_predefiniowany]["search_term"]

okres = st.sidebar.selectbox("Zakres czasu:", ["1mo", "3mo", "6mo", "1y", "2y"], index=2)
interwal = st.sidebar.selectbox("Interwał:", ["1d", "1wk"], index=0)

st.sidebar.markdown("---")
st.sidebar.header("⚖️ Kalkulator Wielkości Pozycji (XTB)")
kapital = st.sidebar.number_input("Twój kapitał (PLN / USD):", min_value=100.0, value=10000.0, step=500.0)
ryzyko_proc = st.sidebar.slider("Dopuszczalne ryzyko transakcji (%):", min_value=0.5, max_value=5.0, value=1.5, step=0.5)

# --- FUNKCJE DANYCH I ZAAWANSOWANYCH WSKAŹNIKÓW ---
@st.cache_data(ttl=180)
def pobierz_dane(symbol, period, interval):
    try:
        dane = yf.download(symbol, period=period, interval=interval, progress=False)
        if dane is not None and not dane.empty:
            if isinstance(dane.columns, pd.MultiIndex):
                dane.columns = dane.columns.get_level_values(0)
            
            dane['SMA20'] = dane['Close'].rolling(window=20).mean()
            dane['SMA50'] = dane['Close'].rolling(window=50).mean()
            
            delta = dane['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            dane['RSI'] = 100 - (100 / (1 + rs))
            
            std20 = dane['Close'].rolling(window=20).std()
            dane['BB_Upper'] = dane['SMA20'] + (std20 * 2)
            dane['BB_Lower'] = dane['SMA20'] - (std20 * 2)
            
            ema12 = dane['Close'].ewm(span=12, adjust=False).mean()
            ema26 = dane['Close'].ewm(span=26, adjust=False).mean()
            dane['MACD'] = ema12 - ema26
            dane['MACD_Signal'] = dane['MACD'].ewm(span=9, adjust=False).mean()
            dane['MACD_Hist'] = dane['MACD'] - dane['MACD_Signal']
            
            tr1 = dane['High'] - dane['Low']
            tr2 = (dane['High'] - dane['Close'].shift()).abs()
            tr3 = (dane['Low'] - dane['Close'].shift()).abs()
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            dane['ATR'] = tr.rolling(window=14).mean()
            
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
ostatnie_sma20 = float(df['SMA20'].iloc[-1]) if not pd.isna(df['SMA20'].iloc[-1]) else ostatnia_cena
ostatnie_sma50 = float(df['SMA50'].iloc[-1]) if not pd.isna(df['SMA50'].iloc[-1]) else ostatnia_cena
ostatni_macd = float(df['MACD'].iloc[-1]) if not pd.isna(df['MACD'].iloc[-1]) else 0.0
ostatni_macd_sig = float(df['MACD_Signal'].iloc[-1]) if not pd.isna(df['MACD_Signal'].iloc[-1]) else 0.0
ostatni_atr = float(df['ATR'].iloc[-1]) if not pd.isna(df['ATR'].iloc[-1]) else (ostatnia_cena * 0.02)

# --- MODUŁ POBIERANIA WIADOMOŚCI ---
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
        rss_url = f"https://news.google.com/rss/search?q={clean_q}+when:7d&hl={lang}&gl={gl}&ceid={ceid}"
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

# --- ROZBUDOWANY SILNIK DECYZYJNY ---
punkty_bycze = 0
punkty_niedzwiedzie = 0

if ostatnia_cena > ostatnie_sma50:
    punkty_bycze += 1
    trend_opis = "Trend wzrostowy (Cena > SMA50)"
else:
    punkty_niedzwiedzie += 1
    trend_opis = "Trend spadkowy (Cena < SMA50)"

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
    macd_opis = "MACD < Sygnał (Porspadkowo)"

if avg_sent > 0.05:
    punkty_bycze += 1
    sent_opis = "Pozytywny / Byczy"
elif avg_sent < -0.05:
    punkty_niedzwiedzie += 1
    sent_opis = "Negatywny / Niedźwiedzi"
else:
    sent_opis = "Neutralny"

if punkty_bycze >= 3:
    werdykt_status = "MOCNY KANDYDAT NA LONGA (KUPNO)"
    werdykt_kolor = "success"
    werdykt_komentarz = "Przewaga sygnałów prowzrostowych (Trend, MACD, Sentyment). Szukaj wejścia."
elif punkty_niedzwiedzie >= 3:
    werdykt_status = "OSTRZEŻENIE / KANDYDAT NA SHORTA"
    werdykt_kolor = "error"
    werdykt_komentarz = "Przewaga sygnałów prospadkowych lub silnego przegrzania rynku."
else:
    werdykt_status = "NEUTRALNY / OBSERWACJA"
    werdykt_kolor = "info"
    werdykt_komentarz = "Rynek w konsolidacji lub sygnały są sprzeczne. Wstrzymaj się z decyzją."

# --- GŁÓWNY PANEL GÓRNY ---
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Ticker", ticker)
c2.metric("Kurs", f"{ostatnia_cena:.2f}", f"{zmiana_proc:+.2f}%")
c3.metric("RSI (14)", f"{ostatni_rsi:.1f}", rsi_opis)
c4.metric("MACD Status", f"{ostatni_macd:.2f}", macd_opis)
c5.metric("Zmienność ATR (14)", f"{ostatni_atr:.2f}", "Średni zasięg świecy")

komunikat_werdyktu = f"🎯 **WERDYKT AI COPILOTA: {werdykt_status}**\n\n- {trend_opis} | {rsi_opis} | {macd_opis} | Sentyment: {sent_opis}\n- *{werdykt_komentarz}*"
if werdykt_kolor == "success":
    st.success(komunikat_werdyktu)
elif werdykt_kolor == "error":
    st.error(komunikat_werdyktu)
else:
    st.info(komunikat_werdyktu)

# --- ZAKŁADKI GŁÓWNE ---
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📈 Zaawansowany Wykres (Wstęgi + MACD)", 
    "🤖 Analiza Sentymentu (AI)", 
    "⚖️ Kalkulator Pozycji & ATR",
    "🔍 Skaner Rynku (GPW & USA)",
    "📓 Dziennik Transakcji"
])

with tab1:
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.04, row_heights=[0.7, 0.3])
    
    fig.add_trace(go.Candlestick(
        x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
        name="Świece"
    ), row=1, col=1)
    
    fig.add_trace(go.Scatter(x=df.index, y=df['SMA20'], line=dict(color='orange', width=1.2), name="SMA 20"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['SMA50'], line=dict(color='deepskyblue', width=1.5), name="SMA 50"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['BB_Upper'], line=dict(color='gray', width=1, dash='dot'), name="Górna Wstęga"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['BB_Lower'], line=dict(color='gray', width=1, dash='dot'), name="Dolna Wstęga"), row=1, col=1)
    
    colors_hist = ['green' if val >= 0 else 'red' for val in df['MACD_Hist']]
    fig.add_trace(go.Bar(x=df.index, y=df['MACD_Hist'], name="MACD Hist", marker_color=colors_hist), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['MACD'], line=dict(color='cyan', width=1.5), name="MACD"), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['MACD_Signal'], line=dict(color='yellow', width=1.2), name="Sygnał MACD"), row=2, col=1)
    
    fig.update_layout(
        title=f"Analiza techniczna: {ticker}",
        xaxis_rangeslider_
