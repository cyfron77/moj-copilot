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
PLIK_DZIENNIKA = "dziennik_transakcji_dev.csv"

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
    sent_opis = "Pozytywny"
elif avg_sent < -0.05:
    punkty_niedzwiedzie += 1
    sent_opis = "Negatywny"
else:
    sent_opis = "Neutralny"

if punkty_bycze >= 3:
    werdykt_status = "MOCNY KANDYDAT NA LONGA (KUPNO)"
    werdykt_kolor = "success"
    werdykt_komentarz = "Przewaga sygnałów prowzrostowych. Szukaj wejścia."
elif punkty_niedzwiedzie >= 3:
    werdykt_status = "OSTRZEŻENIE / KANDYDAT NA SHORTA"
    werdykt_kolor = "error"
    werdykt_komentarz = "Przewaga sygnałów spadkowych."
else:
    werdykt_status = "NEUTRALNY / OBSERWACJA"
    werdykt_kolor = "info"
    werdykt_komentarz = "Sygnały sprzeczne. Wstrzymaj się."

# --- GŁÓWNY PANEL GÓRNY ---
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Ticker", ticker)
c2.metric("Kurs", f"{ostatnia_cena:.2f}", f"{zmiana_proc:+.2f}%")
c3.metric("RSI (14)", f"{ostatni_rsi:.1f}", rsi_opis)
c4.metric("MACD Status", f"{ostatni_macd:.2f}", macd_opis)
c5.metric("Zmienność ATR", f"{ostatni_atr:.2f}", "Średni zasięg")

komunikat_werdyktu = f"🎯 **WERDYKT AI COPILOTA: {werdykt_status}**\n\n- {trend_opis} | {rsi_opis} | {macd_opis} | Sentyment: {sent_opis}\n- *{werdykt_komentarz}*"
if werdykt_kolor == "success":
    st.success(komunikat_werdyktu)
elif werdykt_kolor == "error":
    st.error(komunikat_werdyktu)
else:
    st.info(komunikat_werdyktu)

# --- ZAKŁADKI GŁÓWNE ---
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📈 Wykres", 
    "🤖 Sentyment", 
    "⚖️ Kalkulator & ATR",
    "🔍 Skaner",
    "📓 Dziennik Transakcji",
    "📊 Portfel Live (T212)"
])

with tab1:
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.04, row_heights=[0.7, 0.3])
    
    fig.add_trace(go.Candlestick(
        x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Świece"
    ), row=1, col=1)
    
    fig.add_trace(go.Scatter(x=df.index, y=df['SMA20'], line=dict(color='orange', width=1.2), name="SMA 20"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['SMA50'], line=dict(color='deepskyblue', width=1.5), name="SMA 50"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['BB_Upper'], line=dict(color='gray', width=1, dash='dot'), name="Górna Wstęga"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['BB_Lower'], line=dict(color='gray', width=1, dash='dot'), name="Dolna Wstęga"), row=1, col=1)
    
    colors_hist = ['green' if val >= 0 else 'red' for val in df['MACD_Hist']]
    fig.add_trace(go.Bar(x=df.index, y=df['MACD_Hist'], name="MACD Hist", marker_color=colors_hist), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['MACD'], line=dict(color='cyan', width=1.5), name="MACD"), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['MACD_Signal'], line=dict(color='yellow', width=1.2), name="Sygnał MACD"), row=2, col=1)
    
    fig.update_layout(title=f"Analiza techniczna: {ticker}", xaxis_rangeslider_visible=False, height=620, template="plotly_dark")
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.subheader("📰 Świeże wiadomości rynkowe")
    if news_items:
        for item in news_items:
            st.markdown(f"**[{item['tytul']}]({item['link']})**")
            st.caption(f"Sentyment: {item['status']} (`{item['score']:.2f}`) | Źródło: **{item['zrodlo']}** | Opublikowano: **{item['data']}**")
            st.write("---")
    else:
        st.warning("Brak najnowszych wiadomości.")

with tab3:
    st.subheader("⚖️ Kalkulator Pozycji i Ryzyka (ATR)")
    mnoznik_atr = st.slider("Mnożnik ATR dla Stop Lossa:", min_value=1.0, max_value=4.0, value=2.0, step=0.5)
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
            f"- Zalecana wielkość pozycji: **{rekomendowana_liczba}** sztuk\n"
            f"- Łączna wartość transakcji: **{wartosc_pozycji:,.2f}**\n"
            f"- Maksymalna strata: **{max_strata_kwota:,.2f}** ({ryzyko_proc}%)\n"
            f"- Stosunek Zysku do Ryzyka: **1 : {r_r:.2f}**"
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
                    trend = "🟢 Wzrostowy" if cena > sma50_val else "🔴 Spadkowy"
                    wyniki_skanera.append({
                        "Aktywo": nazwa, "Ticker": sym, "Cena": f"{cena:.2f}",
                        "RSI (14)": f"{rsi_val:.1f}", "Trend (SMA50)": trend
                    })
            st.dataframe(pd.DataFrame(wyniki_skanera), use_container_width=True)

with tab5:
    st.subheader("📓 Dziennik Transakcji (DEV)")
    with st.form("dziennik_dev_form"):
        c1, c2, c3 = st.columns(3)
        t_ak = c1.text_input("Aktywo / Ticker:", value=ticker)
        t_kir = c2.selectbox("Kierunek:", ["KUPNO (Long)", "SPRZEDAŻ (Short)"])
        t_wol = c3.number_input("Wolumen:", value=1.0)
        
        c4, c5, c6 = st.columns(3)
        t_cen = c4.number_input("Cena Otwarcia:", value=ostatnia_cena, format="%.4f")
        t_sta = c5.selectbox("Status:", ["Zamknięte", "Otwarte"])
        t_pnl = c6.number_input("Wynik netto:", value=0.0, format="%.2f")
        
        if st.form_submit_button("Zapisz w dzienniku"):
            nowy = {
                "Data": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "Aktywo": t_ak.upper(), "Kierunek": t_kir, "Wolumen": t_wol,
                "Cena Otwarcia": t_cen, "Status": t_sta, "Wynik": t_pnl
            }
            zapisz_w_dzienniku(nowy)
            st.success("Zapisano!")
            st.rerun()
            
    df_d = wczytaj_dziennik()
    if not df_d.empty:
        # NOWA LOGIKA: Zawsze pokazujemy tabelę, nawet gdy nie ma statystyk!
        zamkniete = df_d[df_d['Status'] == 'Zamknięte'].copy()
        
        if not zamkniete.empty:
            zamkniete['Wynik'] = pd.to_numeric(zamkniete['Wynik'], errors='coerce').fillna(0)
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
                x=zamkniete['Data'], y=zamkniete['Krzywa Kapitału'], 
                mode='lines+markers', name='Krzywa PnL', 
                line=dict(color='lime' if suma_wynikow >= 0 else 'red', width=3)
            ))
            fig_eq.update_layout(title="Krzywa Zysków i Strat", template="plotly_dark", height=350)
            st.plotly_chart(fig_eq, use_container_width=True)
        else:
            st.info("Brak **zamkniętych** pozycji do wyliczenia statystyk i krzywej kapitału.")
            
        st.markdown("### 📝 Pełna historia operacji (Otwarte i Zamknięte)")
        st.dataframe(df_d, use_container_width=True)
    else:
        st.info("Twój dziennik jest na razie całkowicie pusty.")

with tab6:
    st.subheader("📊 Mój Portfel Live (Trading 212 Demo)")
    if not T212_KEY or not T212_SEC:
        st.warning("⚠️ Brak kluczy API w Streamlit Secrets!")
    else:
        if st.button("🔄 Odśwież dane portfela"):
            st.cache_data.clear()
            
        @st.cache_data(ttl=30)
        def pobierz_portfel_t212(k, s):
            try:
                c = requests.get(f"{T212_BASE_URL}/account/cash", auth=(k, s))
                p = requests.get(f"{T212_BASE_URL}/positions", auth=(k, s))
                if c.status_code == 200 and p.status_code == 200:
                    return c.json(), p.json()
            except:
                pass
            return None, None
            
        kasa, pozycje = pobierz_portfel_t212(T212_KEY, T212_SEC)
        
        if kasa is not None:
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Wycena Portfela", f"{kasa.get('total', 0):.2f}")
            col2.metric("Wolne Środki", f"{kasa.get('free', 0):.2f}")
            col3.metric("Zainwestowane", f"{kasa.get('invested', 0):.2f}")
            col4.metric("Wynik (PnL)", f"{kasa.get('ppl', 0):.2f}")
            
            st.markdown("### 📝 Aktualnie Otwarte Pozycje")
            if pozycje and isinstance(pozycje, list) and len(pozycje) > 0:
                lista = []
                for p in pozycje:
                    # Inteligentna siatka - wyłapuje różne nazwy kluczy
                    tckr = p.get('ticker') or p.get('instrument') or p.get('symbol') or p.get('code') or "Brak"
                    qty = p.get('quantity') or p.get('size') or 0.0
                    avg_p = p.get('averagePrice') or p.get('openPrice') or p.get('average_price') or 0.0
                    cur_p = p.get('currentPrice') or p.get('current_price') or 0.0
                    ppl = p.get('ppl') or p.get('profit') or p.get('unrealisedPnl') or p.get('unrealised_pnl') or 0.0
                    
                    lista.append({
                        "Aktywo (Ticker)": str(tckr),
                        "Kierunek": "LONG" if float(qty) > 0 else "SHORT",
                        "Wolumen": abs(float(qty)),
                        "Śr. Cena Wejścia": round(float(avg_p), 4),
                        "Obecna Cena": round(float(cur_p), 4),
                        "Zysk / Strata": round(float(ppl), 2)
                    })
                st.dataframe(pd.DataFrame(lista), use_container_width=True)
                
                # Ukryty moduł ratunkowy, jeśli tabela znów byłaby niekompletna
                with st.expander("🛠️ Pokaż surowe dane z API (Otwórz, jeśli brakuje danych)"):
                    st.info("Jeśli w tabeli wyżej wciąż widnieje 'Brak' lub '0' przy jakiejś wartości, rozwiń ten panel, zrób zrzut ekranu tych surowych kodów i wyślij mi go. Będę wiedział dokładnie, pod jaką nazwą schował to broker!")
                    st.json(pozycje)
            else:
                st.info("Brak otwartych pozycji na platformie Trading 212.")
        else:
            st.error("Błąd połączenia. Odśwież stronę lub sprawdź klucze API.")
