# app.py
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime

from modules.data_loader import pobierz_dane, pobierz_dane_multi
from modules.ai_engine import AI_PROFILES, oblicz_ai_werdykt
from modules.news_sentiment import pobierz_swieze_newsy, przetworz_sentyment
from modules.journal import wczytaj_baze_aktywow, zapisz_baze_aktywow, wczytaj_dziennik, zapisz_w_dzienniku
from modules.correlations import oblicz_korelacje_makro

# ---------------------------------------------------------
# Konfiguracja strony
# ---------------------------------------------------------
st.set_page_config(page_title="AI Trading Copilot Pro", layout="wide", page_icon="📈")
st.title("🤖 AI Trading & Investment Copilot")
st.caption("Wsparcie decyzji inwestycyjnych: Wall Street, GPW, Surowce, CFD (XTB)")

popularne_aktywa = wczytaj_baze_aktywow()

# ---------------------------------------------------------
# Sidebar
# ---------------------------------------------------------
st.sidebar.header("⚙️ Ustawienia analizy")
fraza_szukania = st.sidebar.text_input("🔍 Wyszukaj po nazwie:", value="")

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

okres = st.sidebar.selectbox("Zakres czasu wykresu:", ["1mo", "3mo", "6mo", "1y", "2y"], index=2)
interwal = st.sidebar.selectbox("Interwał świec:", ["1d", "1wk"], index=0)

st.sidebar.markdown("---")
st.sidebar.header("⚖️ Kalkulator Wielkości Pozycji (XTB)")
kapital = st.sidebar.number_input("Twój kapitał:", min_value=100.0, value=10000.0, step=500.0)
ryzyko_proc = st.sidebar.slider("Ryzyko (%):", min_value=0.5, max_value=5.0, value=1.5, step=0.5)
instrument_typ = st.sidebar.selectbox("Typ:", ["Akcje / ETF", "CFD XTB"], index=0)

leverage = 1.0
contract_multiplier = 1.0
if instrument_typ == "CFD XTB":
    leverage = st.sidebar.number_input("Dźwignia:", min_value=1.0, value=5.0, step=1.0)
    contract_multiplier = st.sidebar.number_input("Wartość 1 kontraktu:", min_value=0.01, value=1.0, step=0.01)

profil_ai = st.sidebar.selectbox("Profil AI werdyktu:", list(AI_PROFILES.keys()), index=0)
wagi = AI_PROFILES[profil_ai]

# ---------------------------------------------------------
# Pobranie danych i wyliczenia
# ---------------------------------------------------------
df = pobierz_dane(ticker, okres, interwal)
if df is None or df.empty:
    st.error(f"Nie udało się pobrać danych dla **{ticker}**.")
    st.stop()

ostatnia_cena = float(df["Close"].iloc[-1])
poprzednia_cena = float(df["Close"].iloc[-2]) if len(df) > 1 else ostatnia_cena
zmiana_proc = ((ostatnia_cena - poprzednia_cena) / poprzednia_cena) * 100 if poprzednia_cena != 0 else 0.0

ostatni_rsi = float(df["RSI"].iloc[-1]) if not pd.isna(df["RSI"].iloc[-1]) else 50.0
ostatnie_sma50 = float(df["SMA50"].iloc[-1]) if not pd.isna(df["SMA50"].iloc[-1]) else ostatnia_cena
ostatnie_sma200 = float(df["SMA200"].iloc[-1]) if not pd.isna(df["SMA200"].iloc[-1]) else np.nan
ostatni_macd = float(df["MACD"].iloc[-1]) if not pd.isna(df["MACD"].iloc[-1]) else 0.0
ostatni_macd_sig = float(df["MACD_Signal"].iloc[-1]) if not pd.isna(df["MACD_Signal"].iloc[-1]) else 0.0
ostatni_atr = float(df["ATR"].iloc[-1]) if not pd.isna(df["ATR"].iloc[-1]) else (ostatnia_cena * 0.02)
ostatni_adx = float(df["ADX"].iloc[-1]) if not pd.isna(df["ADX"].iloc[-1]) else np.nan
ostatni_vol_ratio = float(df["Vol_Ratio"].iloc[-1]) if "Vol_Ratio" in df.columns and not pd.isna(df["Vol_Ratio"].iloc[-1]) else np.nan

raw_news = pobierz_swieze_newsy(ticker, search_query)
news_items, avg_sent = przetworz_sentyment(raw_news, ticker)

werdykt = oblicz_ai_werdykt(
    cena=ostatnia_cena, sma50=ostatnie_sma50, sma200=ostatnie_sma200, rsi=ostatni_rsi,
    macd=ostatni_macd, macd_sig=ostatni_macd_sig, avg_sent=avg_sent, atr=ostatni_atr,
    adx=ostatni_adx, vol_ratio=ostatni_vol_ratio, data_len=len(df), **wagi
)

# Panel metryk
c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
c1.metric("Ticker", ticker)
c2.metric("Kurs", f"{ostatnia_cena:.2f}", f"{zmiana_proc:+.2f}%")
c3.metric("RSI (14)", f"{ostatni_rsi:.1f}", werdykt["rsi_opis"])
c4.metric("MACD Status", f"{ostatni_macd:.2f}", werdykt["macd_opis"])
c5.metric("ATR (14)", f"{ostatni_atr:.2f}", "Zasięg świecy")
c6.metric("ADX (14)", f"{ostatni_adx:.1f}" if not np.isnan(ostatni_adx) else "n/a", "Siła trendu")
c7.metric("Volume Ratio", f"{ostatni_vol_ratio:.2f}" if not np.isnan(ostatni_vol_ratio) else "n/a", werdykt["vol_opis"])

jakosc_txt = ("\n\n- " + "\n- ".join(werdykt["jakosc_flags"])) if werdykt["jakosc_flags"] else ""
komunikat = (
    f"🎯 **WERDYKT AI ({profil_ai}): {werdykt['status']}**\n\n"
    f"- {werdykt['trend_opis']} | {werdykt['rsi_opis']} | {werdykt['macd_opis']} | Sentyment: {werdykt['sent_opis']}\n"
    f"- Łączny AI Score: **{werdykt['score']:.2f}**{jakosc_txt}"
)
if werdykt["kolor"] == "success": st.success(komunikat)
elif werdykt["kolor"] == "error": st.error(komunikat)
else: st.info(komunikat)

# ---------------------------------------------------------
# Zakładki
# ---------------------------------------------------------
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📈 Wykres Zaawansowany",
    "🤖 Sentyment i Newsy",
    "⚖️ Kalkulator Pozycji",
    "🔍 Skaner Rynku",
    "📓 Dziennik Transakcji",
    "🌐 Dedykowane Czynniki & Korelacje"
])

with tab1:
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.55, 0.25, 0.2])
    fig.add_trace(go.Candlestick(x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"], name="Świece"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["SMA20"], line=dict(color="orange", width=1.2), name="SMA 20"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["SMA50"], line=dict(color="deepskyblue", width=1.5), name="SMA 50"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["SMA200"], line=dict(color="magenta", width=1.5), name="SMA 200"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["BB_Upper"], line=dict(color="gray", width=1, dash="dot"), name="BB Upper"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["BB_Lower"], line=dict(color="gray", width=1, dash="dot"), name="BB Lower"), row=1, col=1)

    colors_hist = ["green" if val >= 0 else "red" for val in df["MACD_Hist"]]
    fig.add_trace(go.Bar(x=df.index, y=df["MACD_Hist"], name="MACD Hist", marker_color=colors_hist), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["MACD"], line=dict(color="cyan", width=1.5), name="MACD"), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["MACD_Signal"], line=dict(color="yellow", width=1.2), name="Signal"), row=2, col=1)

    if "Volume" in df.columns:
        fig.add_trace(go.Bar(x=df.index, y=df["Volume"], name="Wolumen", marker_color="lightblue"), row=3, col=1)
    fig.update_layout(title=f"Analiza techniczna: {ticker}", xaxis_rangeslider_visible=False, height=720, template="plotly_dark")
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.subheader("📰 Świeże wiadomości rynkowe")
    if news_items:
        for item in news_items:
            st.markdown(f"**[{item['tytul']}]({item['link']})**")
            st.caption(f"Sentyment: {item['status']} | Źródło: {item['zrodlo']} | {item['data']}")
            st.write("---")
    else:
        st.warning("Brak wiadomości dla tego aktywa.")

with tab3:
    st.subheader("⚖️ Kalkulator Pozycji i Ryzyka")
    mnoznik_atr = st.slider("Mnożnik ATR:", 1.0, 4.0, 2.0, 0.5)
    sugerowany_sl = float(round(ostatnia_cena - (ostatni_atr * mnoznik_atr), 2))
    sugerowany_tp = float(round(ostatnia_cena + (ostatni_atr * mnoznik_atr * 2.0), 2))

    c_sl, c_tp = st.columns(2)
    sl = c_sl.number_input("Stop Loss:", value=sugerowany_sl)
    tp = c_tp.number_input("Take Profit:", value=sugerowany_tp)
    roznica = abs(ostatnia_cena - sl)

    if roznica > 0:
        max_strata = kapital * (ryzyko_proc / 100)
        pozycja = int(max_strata / roznica)
        st.success(f"Zalecana wielkość pozycji: **{pozycja}** sztuk | Wartość: **{pozycja*ostatnia_cena:,.2f}** | R:R = **1 : {(abs(tp-ostatnia_cena)/roznica):.2f}**")

with tab4:
    st.subheader("🔍 Skaner Okazji Rynkowych")
    if st.button("🚀 Uruchom skanowanie"):
        with st.spinner("Skanowanie..."):
            syms = [v["ticker"] for v in popularne_aktywa.values()]
            d_multi = pobierz_dane_multi(syms, period=okres, interval=interwal)
            wyniki = []
            for nazwa, v in popularne_aktywa.items():
                s = v["ticker"]
                d = d_multi.get(s)
                if d is None or d.empty: continue
                c = float(d["Close"].iloc[-1])
                rsi = float(d["RSI"].iloc[-1]) if not pd.isna(d["RSI"].iloc[-1]) else 50.0
                sma50 = float(d["SMA50"].iloc[-1]) if not pd.isna(d["SMA50"].iloc[-1]) else c
                wer = oblicz_ai_werdykt(c, sma50, np.nan, rsi, 0, 0, 0, 0, np.nan, np.nan, len(d), **wagi)
                wyniki.append({"Aktywo": nazwa, "Ticker": s, "Cena": f"{c:.2f}", "RSI": f"{rsi:.1f}", "Score": round(wer["score"], 2), "Werdykt": wer["status"]})
            st.dataframe(pd.DataFrame(wyniki).sort_values("Score", ascending=False), use_container_width=True)

with tab5:
    st.subheader("📓 Dziennik Transakcji")
    df_dz = wczytaj_dziennik()
    if not df_dz.empty:
        st.dataframe(df_dz, use_container_width=True)
    else:
        st.info("Dziennik jest pusty.")

# TAB 6 – ZMODYFIKOWANY POD DEDYKOWANĄ MATRYCĘ
with tab6:
    st.subheader(f"🌐 Głębokiej Analiza Sektorowa i Makro dla: {ticker}")
    oblicz_korelacje_makro(ticker, df, okres, interwal)
