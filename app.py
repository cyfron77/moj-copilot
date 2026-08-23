# app.py
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json

from modules.data_loader import pobierz_dane, pobierz_dane_multi
from modules.ai_engine import oblicz_werdykt_quant
from modules.news_sentiment import pobierz_swieze_newsy, przetworz_sentyment
from modules.journal import wczytaj_baze_aktywow, zapisz_baze_aktywow, wczytaj_dziennik, zapisz_w_dzienniku
from modules.correlations import oblicz_korelacje_makro
from modules.earnings import wyswietl_kalendarz_wynikow, pobierz_wyniki_tekst
from modules.optimizer import optymalizuj_wagi, wczytaj_wagi
from modules.gemini_llm import pobierz_ocene_llm
from modules.fundamentals import pobierz_fundamenty_tekst

# ---------------------------------------------------------
# Konfiguracja
# ---------------------------------------------------------
st.set_page_config(page_title="Quant Model Copilot", layout="wide", page_icon="📈")
st.title("🤖 Quant Model & LLM Copilot")

popularne_aktywa = wczytaj_baze_aktywow()

if "llm_results" not in st.session_state:
    st.session_state.llm_results = {}

# ---------------------------------------------------------
# Sidebar
# ---------------------------------------------------------
st.sidebar.header("⚙️ Konfiguracja")
fraza_szukania = st.sidebar.text_input("🔍 Wyszukaj po nazwie:")
pasujace_aktywa = {k: v for k, v in popularne_aktywa.items() if fraza_szukania.lower() in k.lower()} if fraza_szukania.strip() else popularne_aktywa

if len(pasujace_aktywa) > 0:
    wybor_predefiniowany = st.sidebar.selectbox("⭐ Wybierz aktywo:", list(pasujace_aktywa.keys()))
    ticker = pasujace_aktywa[wybor_predefiniowany]["ticker"]
    search_query = pasujace_aktywa[wybor_predefiniowany]["search_term"]
else:
    st.sidebar.warning("Brak dopasowań.")
    wybor_predefiniowany = list(popularne_aktywa.keys())[0]
    ticker = popularne_aktywa[wybor_predefiniowany]["ticker"]
    search_query = popularne_aktywa[wybor_predefiniowany]["search_term"]

with st.sidebar.expander("🛠️ Edytor listy walorów"):
    nowa_nazwa = st.text_input("Nazwa:", key="add_name")
    nowy_ticker = st.text_input("Ticker:", key="add_ticker")
    if st.button("➕ Dodaj do listy") and nowa_nazwa and nowy_ticker:
        t_clean = nowy_ticker.upper().strip()
        popularne_aktywa[nowa_nazwa] = {"ticker": t_clean, "search_term": f"{t_clean} stock market news"}
        zapisz_baze_aktywow(popularne_aktywa)
        st.success(f"Dodano: {nowa_nazwa}")
        st.rerun()

    walor_do_usuniecia = st.selectbox("Usuń walor:", list(popularne_aktywa.keys()), key="del_select")
    if st.button("🗑️ Usuń walor") and len(popularne_aktywa) > 1:
        del popularne_aktywa[walor_do_usuniecia]
        zapisz_baze_aktywow(popularne_aktywa)
        st.success(f"Usunięto: {walor_do_usuniecia}")
        st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader("🧠 Dynamiczne Wagi Modelu")
wagi = wczytaj_wagi(ticker)
st.sidebar.json(wagi)

if st.sidebar.button("🔄 Optymalizuj wagi na bazie historii"):
    with st.spinner("Badanie korelacji wstecznej (6 miesięcy)..."):
        nowe_wagi = optymalizuj_wagi(ticker)
        if nowe_wagi:
            st.sidebar.success("Zaktualizowano wagi!")
            st.rerun()
        else:
            st.sidebar.error("Zbyt mało danych do optymalizacji.")

st.sidebar.markdown("---")
okres = st.sidebar.selectbox("Zakres czasu wykresu:", ["5d", "1mo", "3mo", "6mo", "1y", "2y"], index=2)
interwal = st.sidebar.selectbox("Interwał świec:", ["1h", "1d", "1wk"], index=1)

st.sidebar.markdown("---")
st.sidebar.header("⚖️ Parametry Kapitału")
kapital = st.sidebar.number_input("Twój kapitał:", min_value=100.0, value=10000.0, step=500.0)
ryzyko_proc = st.sidebar.slider("Ryzyko (%):", min_value=0.5, max_value=5.0, value=1.5, step=0.5)

# ---------------------------------------------------------
# Pobranie danych wykresu i wskaźników
# ---------------------------------------------------------
df = pobierz_dane(ticker, okres, interwal)
if df is None or df.empty:
    st.error(f"Brak danych dla **{ticker}**.")
    st.stop()

ostatnia_cena = float(df["Close"].iloc[-1])
ostatnie_sma50 = float(df["SMA50"].iloc[-1]) if not pd.isna(df["SMA50"].iloc[-1]) else ostatnia_cena
ostatnie_sma200 = float(df["SMA200"].iloc[-1]) if not pd.isna(df["SMA200"].iloc[-1]) else np.nan
ostatni_rsi = float(df["RSI"].iloc[-1]) if not pd.isna(df["RSI"].iloc[-1]) else 50.0
ostatni_macd = float(df["MACD"].iloc[-1]) if not pd.isna(df["MACD"].iloc[-1]) else 0.0
ostatni_macd_sig = float(df["MACD_Signal"].iloc[-1]) if not pd.isna(df["MACD_Signal"].iloc[-1]) else 0.0
ostatni_atr = float(df["ATR"].iloc[-1]) if not pd.isna(df["ATR"].iloc[-1]) else (ostatnia_cena * 0.02)

# Pobranie newsów na potrzeby UI oraz Gemini
raw_news = pobierz_swieze_newsy(ticker, search_query)
news_items, avg_sent = przetworz_sentyment(raw_news, ticker)

# ---------------------------------------------------------
# Analiza LLM (Gemini)
# ---------------------------------------------------------
st.markdown("### 🧠 Głęboka analiza AI (Sentyment & Fundamenty)")
llm_data = st.session_state.llm_results.get(ticker, {"sentyment_score": 0.0, "fundament_score": 0.0, "uzasadnienie": "Oczekuje na wykonanie analizy..."})

if st.button("🚀 Wykonaj Analizę Gemini dla tego waloru (Zrozumienie newsów i fundamentów)"):
    with st.spinner("Gemini analizuje wiadomości i raporty finansowe..."):
        newsy_tekst = "\n".join([f"- [{n['data']}] {n['tytul']} ({n['zrodlo']})" for n in raw_news])
        
        fundamenty_tekst = pobierz_fundamenty_tekst(ticker)
        wyniki_tekst = pobierz_wyniki_tekst(ticker)
        
        dane_fund = (
            f"--- BIEŻĄCA WYCENA I KONDYCJA ---\n{fundamenty_tekst}\n\n"
            f"--- WERYFIKACJA CELÓW I WYNIKI (EPS) ---\n{wyniki_tekst}\n\n"
            f"Dodatkowe informacje techniczne: Obecna cena to {ostatnia_cena}, RSI: {ostatni_rsi:.2f}. "
            "Na podstawie tych wszystkich informacji, oceń stabilność i potencjał wzrostu spółki."
        )
        
        wynik_llm = pobierz_ocene_llm(ticker, newsy_tekst, dane_fund)
        st.session_state.llm_results[ticker] = wynik_llm
        llm_data = wynik_llm
        
        st.info("Dane sentymentu i fundamentów zostały wygenerowane na bazie wskaźników finansowych przez model Gemini.")

# ---------------------------------------------------------
# WERDYKT QUANT
# ---------------------------------------------------------
makro_kierunek = 0.5 if ostatnia_cena > ostatnie_sma50 else -0.5 

werdykt = oblicz_werdykt_quant(
    cena=ostatnia_cena, sma50=ostatnie_sma50, sma200=ostatnie_sma200, rsi=ostatni_rsi,
    macd=ostatni_macd, macd_sig=ostatni_macd_sig, 
    llm_sentyment=llm_data["sentyment_score"], 
    llm_fundament=llm_data["fundament_score"], 
    makro_kierunek=makro_kierunek,
    wagi=wagi
)

st.markdown("---")
c_swing, c_invest = st.columns(2)

with c_swing:
    st.subheader("⚡ Model Krótkoterminowy (Swing/Day)")
    st.caption("Wskaźniki Techniczne + Aktualny Sentyment Newsów")
    if werdykt["swing_kolor"] == "success": st.success(f"Wynik: {werdykt['swing_status']} (Score: {werdykt['swing_score']:.2f})")
    elif werdykt["swing_kolor"] == "error": st.error(f"Wynik: {werdykt['swing_status']} (Score: {werdykt['swing_score']:.2f})")
    else: st.warning(f"Wynik: {werdykt['swing_status']} (Score: {werdykt['swing_score']:.2f})")

with c_invest:
    st.subheader("🏛️ Model Długoterminowy (Invest)")
    st.caption("Ocena Fundamentalna + Długi Trend + Makro")
    if werdykt["long_kolor"] == "success": st.success(f"Wynik: {werdykt['long_status']} (Score: {werdykt['long_score']:.2f})")
    elif werdykt["long_kolor"] == "error": st.error(f"Wynik: {werdykt['long_status']} (Score: {werdykt['long_score']:.2f})")
    else: st.warning(f"Wynik: {werdykt['long_status']} (Score: {werdykt['long_score']:.2f})")

st.info(f"**Uzasadnienie AI (Gemini):** {llm_data['uzasadnienie']}")

# ---------------------------------------------------------
# Zakładki Główne
# ---------------------------------------------------------
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📈 Wykres Zaawansowany", 
    "📰 Sentyment i Newsy", 
    "🌐 Czynniki Makro", 
    "📅 Wyniki EPS", 
    "⚖️ Kalkulator Pozycji",
    "📓 Dziennik Transakcji"
])

with tab1:
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.55, 0.25, 0.2])
    fig.add_trace(go.Candlestick(x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"], name="Świece"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["SMA20"], line=dict(color="orange", width=1.2), name="SMA 20"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["SMA50"], line=dict(color="deepskyblue", width=1.5), name="SMA 50"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["SMA200"], line=dict(color="magenta", width=1.5), name="SMA 200"), row=1, col=1)
    fig.add_trace(go.Bar(x=df.index, y=df["MACD_Hist"], name="MACD Hist"), row=2, col=1)
    if "Volume" in df.columns: fig.add_trace(go.Bar(x=df.index, y=df["Volume"], name="Wolumen"), row=3, col=1)
    fig.update_layout(title=f"{ticker} - Analiza", xaxis_rangeslider_visible=False, height=600, template="plotly_dark")
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.subheader("📰 Świeże wiadomości rynkowe (do 30 dni)")
    if news_items:
        for item in news_items:
            st.markdown(f"**[{item['tytul']}]({item['link']})**")
            st.caption(f"Sentyment klasyczny: {item['status']} | Źródło: {item['zrodlo']} | {item['data']}")
            st.write("---")
    else:
        st.warning("Brak wiadomości dla tego aktywa.")

with tab3: 
    oblicz_korelacje_makro(ticker, df, okres, interwal)

with tab4: 
    wyswietl_kalendarz_wynikow(ticker)

with tab5:
    st.subheader("⚖️ Inteligentny Kalkulator Pozycji (Sterowany Quant Modelem)")
    st.caption("Kalkulator automatycznie dostosowuje kierunek zagrania (Long/Short) i odległość parametrów SL/TP do werdyktu modelu i zmienności rynku.")

    # Wyciągamy kierunek z modelu swing (krótkoterminowego)
    kierunek_long = werdykt["swing_score"] >= 0
    
    if kierunek_long:
        st.markdown("### Kierunek transakcji: **KUPNO (LONG) 🟢**")
    else:
        st.markdown("### Kierunek transakcji: **SPRZEDAŻ (SHORT) 🔴**")

    mnoznik_atr = st.slider("Mnożnik ATR dla Stop Loss (Zalecane: 1.5x - 2.5x):", 1.0, 4.0, 2.0, 0.5)
    
    # Logika odwróconych poziomów dla Long vs Short
    if kierunek_long:
        sugerowany_sl = float(round(ostatnia_cena - (ostatni_atr * mnoznik_atr), 2))
        sugerowany_tp = float(round(ostatnia_cena + (ostatni_atr * mnoznik_atr * 2.0), 2))
    else:
        sugerowany_sl = float(round(ostatnia_cena + (ostatni_atr * mnoznik_atr), 2))
        sugerowany_tp = float(round(ostatnia_cena - (ostatni_atr * mnoznik_atr * 2.0), 2))

    c_sl, c_tp = st.columns(2)
    sl = c_sl.number_input("Poziom Stop Loss (SL):", value=sugerowany_sl)
    tp = c_tp.number_input("Poziom Take Profit (TP):", value=sugerowany_tp)
    
    roznica = abs(ostatnia_cena - sl)

    if roznica > 0:
        max_strata = kapital * (ryzyko_proc / 100)
        pozycja = int(max_strata / roznica) if roznica > 0 else 0
        wartosc_pozycji = pozycja * ostatnia_cena
        zysk_na_akcje = abs(tp - ostatnia_cena)
        rr_ratio = zysk_na_akcje / roznica if roznica > 0 else 0

        st.success(
            f"🎯 **Zoptymalizowane parametry zlecenia:**\n\n"
            f"- Zalecany Wolumen (liczba sztuk): **{pozycja}**\n"
            f"- Łączna ekspozycja transakcji: **{wartosc_pozycji:,.2f}**\n"
            f"- Ryzyko kapitałowe (Max strata na zleceniu): **{max_strata:,.2f}** (Zgodnie z Twoim limitem {ryzyko_proc}%)\n"
            f"- Stosunek Zysku do Ryzyka (R:R) = **1 : {rr_ratio:.2f}**\n"
            f"- Bieżący bufor zmienności ATR: **{ostatni_atr:.2f}**"
        )
    else:
        st.warning("Stop Loss nie może być równy bieżącej cenie.")

with tab6:
    st.subheader("📓 Dziennik Transakcji")
    df_dz = wczytaj_dziennik()
    if not df_dz.empty:
        st.dataframe(df_dz, use_container_width=True)
    else:
        st.info("Twój dziennik jest na razie pusty.")
