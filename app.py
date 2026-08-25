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
import requests

# Konfiguracja strony
st.set_page_config(page_title="AI Trading Copilot Pro (DEV)", layout="wide", page_icon="📈")

# --- POBIERANIE KLUCZY API Z SECRETS ---
try:
    T212_KEY = st.secrets["T212_API_KEY"]
    T212_SEC = st.secrets["T212_API_SECRET"]
except:
    T212_KEY = None
    T212_SEC = None
    
T212_BASE_URL = "https://demo.trading212.com/api/v0/equity"

st.title("🤖 AI Trading & Investment Copilot (DEV)")
st.caption("Wersja testowa z modułem automatycznego tradingu i podglądem Trading 212 Live")

# Predefiniowana baza aktywów
popularne_aktywa = {
    "NVIDIA (NVDA)": {"ticker": "NVDA", "search_term": "NVIDIA stock news"},
    "Apple (AAPL)": {"ticker": "AAPL", "search_term": "Apple stock market news"},
    "Microsoft (MSFT)": {"ticker": "MSFT", "search_term": "Microsoft stock news"},
    "Tesla (TSLA)": {"ticker": "TSLA", "search_term": "Tesla stock market news"},
    "Alphabet (Google)": {"ticker": "GOOGL", "search_term": "Google stock market news"},
    "Amazon (AMZN)": {"ticker": "AMZN", "search_term": "Amazon stock market news"},
    "Meta (META)": {"ticker": "META", "search_term": "Meta Facebook stock news"},
    "Coca-Cola (KO)": {"ticker": "KO", "search_term": "Coca Cola stock news"},
    "S&P 500 ETF (SPY)": {"ticker": "SPY", "search_term": "S&P 500 index market today"},
    "Nasdaq 100 ETF (QQQ)": {"ticker": "QQQ", "search_term": "Nasdaq 100 ETF market"}
}

# --- FUNKCJE DZIENNIKA TRANSAKCJI ---
PLIK_DZIENNIKA = "dziennik_transakcji.csv"

def wczytaj_dziennik():
    if os.path.exists(PLIK_DZIENNIKA):
        try:
            return pd.read_csv(PLIK_DZIENNIKA)
        except:
            pass
    return pd.DataFrame(columns=["Data", "Aktywo", "Kierunek", "Wolumen", "Cena Otwarcia", "Status", "Wynik"])

def zapisz_w_dzienniku(nowy_wpis):
    df = wczytaj_dziennik()
    df = pd.concat([df, pd.DataFrame([nowy_wpis])], ignore_index=True)
    df.to_csv(PLIK_DZIENNIKA, index=False)

# --- PANEL BOCZNY (Sidebar) ---
st.sidebar.header("⚙️ Ustawienia analizy")
wybor_predefiniowany = st.sidebar.selectbox("Wybierz z listy:", ["Wpisz własny..."] + list(popularne_aktywa.keys()))

if wybor_predefiniowany == "Wpisz własny...":
    ticker = st.sidebar.text_input("Wpisz Ticker (np. AAPL, TSLA):", value="NVDA").upper()
    search_query = ticker + " stock market news"
else:
    ticker = popularne_aktywa[wybor_predefiniowany]["ticker"]
    search_query = popularne_aktywa[wybor_predefiniowany]["search_term"]

okres = st.sidebar.selectbox("Zakres czasu:", ["1mo", "3mo", "6mo", "1y", "2y"], index=2)
interwal = st.sidebar.selectbox("Interwał:", ["1d", "1wk"], index=0)

st.sidebar.markdown("---")
st.sidebar.header("⚖️ Kalkulator Wielkości Pozycji")
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
        clean_q = query.replace(" ", "+")
        rss_url = f"https://news.google.com/rss/search?q={clean_q}+when:7d&hl=en-US&gl=US&ceid=US:en"
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
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📈 Wykres (Wstęgi + MACD)", 
    "🤖 Sentyment (AI)", 
    "⚖️ Kalkulator & ATR",
    "🔍 Skaner Rynku",
    "📓 Dziennik Transakcji",
    "📊 Portfel Live (T212)"
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
        xaxis_rangeslider_visible=False,
        height=620,
        template="plotly_dark",
        margin=dict(l=20, r=20, t=40, b=20)
    )
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.subheader("📰 Świeże wiadomości rynkowe (Real-Time)")
    if news_items:
        for item in news_items:
            st.markdown(f"**[{item['tytul']}]({item['link']})**")
            st.caption(f"Sentyment: {item['status']} (`{item['score']:.2f}`) | Źródło: **{item['zrodlo']}** | Opublikowano: **{item['data']}**")
            st.write("---")
    else:
        st.warning("Brak najnowszych wiadomości dla tego aktywa z ostatnich dni.")

with tab3:
    st.subheader("⚖️ Inteligentny Kalkulator Pozycji i Ryzyka (Zmienność ATR)")
    
    mnoznik_atr = st.slider("Mnożnik ATR dla Stop Lossa (Zalecane: 1.5x - 2.5x):", min_value=1.0, max_value=4.0, value=2.0, step=0.5)
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
                    cena = float(d_skan['Close'].iloc[-1])
                    rsi_val = float(d_skan['RSI'].iloc[-1]) if not pd.isna(d_skan['RSI'].iloc[-1]) else 50.0
                    sma50_val = float(d_skan['SMA50'].iloc[-1]) if not pd.isna(d_skan['SMA50'].iloc[-1]) else cena
                    atr_val = float(d_skan['ATR'].iloc[-1]) if not pd.isna(d_skan['ATR'].iloc[-1]) else 0.0
                    trend = "🟢 Wzrostowy" if cena > sma50_val else "🔴 Spadkowy"
                    
                    if rsi_val < 35:
                        stan_rsi = "🔥 Wyprzedanie (<35)"
                    elif rsi_val > 70:
                        stan_rsi = "⚠️ Wykupienie (>70)"
                    else:
                        stan_rsi = "Neutralne"
                        
                    wyniki_skanera.append({
                        "Aktywo": nazwa,
                        "Ticker": sym,
                        "Cena": f"{cena:.2f}",
                        "RSI (14)": f"{rsi_val:.1f}",
                        "Stan RSI": stan_rsi,
                        "ATR": f"{atr_val:.2f}",
                        "Trend (SMA50)": trend
                    })
            
            df_skaner = pd.DataFrame(wyniki_skanera)
            st.dataframe(df_skaner, use_container_width=True)

with tab5:
    st.subheader("📓 Dziennik Transakcji (Trading Journal)")
    
    with st.form("szybki_dziennik_form"):
        st.markdown("### ⚡ Szybkie dodanie wyniku")
        c_q1, c_q2, c_q3 = st.columns(3)
        q_aktywo = c_q1.text_input("Aktywo / Ticker:", value=ticker)
        q_kierunek = c_q2.selectbox("Kierunek:", ["KUPNO (Long)", "SPRZEDAŻ (Short)"])
        q_pnl = c_q3.number_input("Wynik netto:", value=0.0, format="%.2f", step=10.0)
        
        submit_quick = st.form_submit_button("💾 Zapisz w dzienniku")
        
        if submit_quick:
            nowy_wpis = {
                "Data": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "Aktywo": q_aktywo.upper(),
                "Kierunek": q_kierunek,
                "Wolumen": 1.0,
                "Cena Otwarcia": ostatnia_cena,
                "Status": "Zamknięte",
                "Wynik": q_pnl
            }
            zapisz_w_dzienniku(nowy_wpis)
            st.success(f"✅ Dodano transakcję {q_aktywo.upper()} z wynikiem {q_pnl}!")
            st.rerun()
                
    st.markdown("---")
    st.markdown("### 📊 Zaawansowane Statystyki i Krzywa Kapitału")
    df_dziennik = wczytaj_dziennik()
    
    if not df_dziennik.empty:
        zamkniete = df_dziennik[df_dziennik['Status'] == 'Zamknięte'].copy()
        
        if not zamkniete.empty:
            zamkniete['Wynik'] = pd.to_numeric(zamkniete['Wynik'], errors='coerce')
            
            total_trades = len(zamkniete)
            zyskownych = len(zamkniete[zamkniete['Wynik'] > 0])
            stratnych = len(zamkniete[zamkniete['Wynik'] <= 0])
            win_rate = (zyskownych / total_trades) * 100 if total_trades > 0 else 0
            suma_wynikow = zamkniete['Wynik'].sum()
            
            c_s1, c_s2, c_s3, c_s4 = st.columns(4)
            c_s1.metric("Zamknięte pozycje", total_trades)
            c_s2.metric("Skuteczność (Win Rate)", f"{win_rate:.1f}%")
            c_s3.metric("Zysk / Strata", f"{zyskownych} / {stratnych}")
            c_s4.metric("Całkowity Wynik (PnL)", f"{suma_wynikow:.2f}")
            
            zamkniete['Krzywa Kapitału'] = zamkniete['Wynik'].cumsum()
            fig_eq = go.Figure()
            fig_eq.add_trace(go.Scatter(
                x=zamkniete['Data'], 
                y=zamkniete['Krzywa Kapitału'], 
                mode='lines+markers', 
                name='Krzywa PnL', 
                line=dict(color='lime' if suma_wynikow >= 0 else 'red', width=3)
            ))
            fig_eq.update_layout(
                title="Krzywa Zysków i Strat", 
                template="plotly_dark", 
                height=350,
                margin=dict(l=20, r=20, t=40, b=20)
            )
            st.plotly_chart(fig_eq, use_container_width=True)
            
        st.markdown("### 📝 Pełna historia operacji")
        st.dataframe(df_dziennik, use_container_width=True)

with tab6:
    st.subheader("📊 Mój Portfel Live (Trading 212 Demo)")
    st.caption("Podgląd Twojego wirtualnego konta i otwartych pozycji w czasie rzeczywistym.")
    
    if not T212_KEY or not T212_SEC:
        st.warning("⚠️ Brak kluczy API! Przejdź do ustawień aplikacji na Streamlit Cloud (Settings -> Secrets) i upewnij się, że dodałeś oba klucze.")
    else:
        if st.button("🔄 Odśwież dane portfela"):
            st.cache_data.clear()
            
        @st.cache_data(ttl=60)
        def pobierz_portfel(k, s):
            try:
                c = requests.get(f"{T212_BASE_URL}/account/cash", auth=(k, s))
                p = requests.get(f"{T212_BASE_URL}/positions", auth=(k, s))
                if c.status_code == 200 and p.status_code == 200:
                    return c.json(), p.json()
            except Exception as e:
                return None, None
            return None, None
            
        with st.spinner("Łączenie z serwerami Trading 212..."):
            kasa, pozycje = pobierz_portfel(T212_KEY, T212_SEC)
            
        if kasa is not None:
            wolne = kasa.get("free", 0.0)
            zainwestowane = kasa.get("invested", 0.0)
            wynik = kasa.get("ppl", 0.0)
            total = kasa.get("total", 0.0)
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Wycena Portfela", f"{total:.2f}")
            col2.metric("Wolne Środki", f"{wolne:.2f}")
            col3.metric("Zainwestowane", f"{zainwestowane:.2f}")
            col4.metric("Niezrealizowany Wynik (PnL)", f"{wynik:.2f}", f"{wynik:+.2f}")
            
            st.markdown("### 📝 Aktualnie Otwarte Pozycje przez Bota")
            if pozycje and len(pozycje) > 0:
                lista_pozycji = []
                for p in pozycje:
                    lista_pozycji.append({
                        "Aktywo (Ticker)": p.get("ticker", ""),
                        "Kierunek": "LONG" if p.get("quantity", 0) > 0 else "SHORT",
                        "Wolumen": p.get("quantity", 0),
                        "Śr. Cena Wejścia": round(p.get("averagePrice", 0), 4),
                        "Obecna Cena": round(p.get("currentPrice", 0), 4),
                        "Zysk / Strata": round(p.get("ppl", 0), 2)
                    })
                df_poz = pd.DataFrame(lista_pozycji)
                st.dataframe(df_poz, use_container_width=True)
            else:
                st.info("Brak otwartych pozycji na koncie Demo Trading 212.")
        else:
            st.error("❌ Nie udało się pobrać danych z Trading 212. Upewnij się, że klucze są wklejone poprawnie i należą do konta INVEST.")
