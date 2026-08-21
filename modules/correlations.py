# modules/correlations.py
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from config_correlations import CORRELATION_MATRIX, DEFAULT_DRIVERS
from modules.data_loader import pobierz_dane_multi

def pobierz_drivery_dla_waloru(ticker: str) -> dict:
    if ticker in CORRELATION_MATRIX:
        return CORRELATION_MATRIX[ticker]["drivery"]
    return DEFAULT_DRIVERS

def oblicz_korelacje_makro(ticker: str, df_glowny: pd.DataFrame, period: str, interval: str):
    drivery = pobierz_drivery_dla_waloru(ticker)
    
    # Wyciągnięcie samych tickerów dla yfinance
    tickers_list = [v["ticker"] for v in drivery.values()]
    dane_macro = pobierz_dane_multi(tickers_list, period=period, interval=interval)

    df_corr = pd.DataFrame()
    df_corr[ticker] = df_glowny["Close"]

    for nazwa, dane_drivera in drivery.items():
        mac_ticker = dane_drivera["ticker"]
        if mac_ticker in dane_macro and not dane_macro[mac_ticker].empty:
            df_corr[nazwa] = dane_macro[mac_ticker]["Close"]

    df_corr.dropna(inplace=True)

    if len(df_corr) > 10:
        rzeczywiste_korelacje = df_corr.corr(method="pearson")[ticker].drop(ticker)
        
        # Wyświetlanie w UI
        cols = st.columns(len(rzeczywiste_korelacje))
        i = 0
        
        y_labels = []
        x_rzeczywiste = []
        x_teoretyczne = []
        
        for nazwa, rzeczywista_kor in rzeczywiste_korelacje.items():
            waga_teoret = drivery[nazwa]["waga"]
            opis_mechaniki = drivery[nazwa]["opis"]
            
            # Formatyka UI
            if rzeczywista_kor > 0.5: trend_ikona = "🟢 Silna +"
            elif rzeczywista_kor > 0.15: trend_ikona = "↗️ Słaba +"
            elif rzeczywista_kor < -0.5: trend_ikona = "🔴 Silna -"
            elif rzeczywista_kor < -0.15: trend_ikona = "↘️ Słaba -"
            else: trend_ikona = "⚪ Brak"

            zgodnosc = "✅ Zgodnie z logiką" if (rzeczywista_kor * waga_teoret) > 0 else "⚠️ Anomalia rynkowa"

            cols[i].metric(nazwa, f"{rzeczywista_kor:.2f}", trend_ikona)
            cols[i].markdown(f"**Oczekiwana: {waga_teoret}** ({zgodnosc})")
            cols[i].caption(opis_mechaniki)
            
            y_labels.append(nazwa)
            x_rzeczywiste.append(rzeczywista_kor)
            x_teoretyczne.append(waga_teoret)
            i += 1

        # Wykres porównawczy: Oczekiwana siła vs Aktualna rynkowa
        fig = go.Figure()
        fig.add_trace(go.Bar(
            y=y_labels, x=x_teoretyczne, orientation='h', 
            name='Teoretyczna waga', marker_color='rgba(128, 128, 128, 0.4)'
        ))
        fig.add_trace(go.Bar(
            y=y_labels, x=x_rzeczywiste, orientation='h', 
            name='Obecna korelacja rynkowa (Aktualna)', 
            marker_color=["lime" if val > 0 else "crimson" for val in x_rzeczywiste]
        ))

        fig.update_layout(
            title=f"Weryfikacja logiki rynkowej: {ticker}",
            barmode='overlay',
            xaxis=dict(range=[-1.1, 1.1]),
            template="plotly_dark",
            height=350,
            margin=dict(l=20, r=20, t=40, b=20)
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Zbyt mało danych wspólnych do wyliczenia korelacji w tym interwale.")
