# modules/optimizer.py
import pandas as pd
import numpy as np
import json
import os
import streamlit as st
from modules.data_loader import pobierz_dane, pobierz_dane_multi
from modules.correlations import pobierz_drivery_dla_waloru

PLIK_WAG = "dynamic_weights.json"

def optymalizuj_wagi(ticker: str):
    """
    Sprawdza wstecznie (6 miesięcy), które wskaźniki miały największą korelację
    z faktycznym ruchem ceny i na tej podstawie wyznacza dynamiczne wagi.
    """
    df = pobierz_dane(ticker, "6mo", "1d")
    if df is None or df.empty:
        return None

    # Obliczamy przyszły jednodniowy zwrot z ceny (shift -1) do zbadania korelacji
    df['Zwrot'] = df['Close'].pct_change().shift(-1)
    
    # Korelacja RSI i MACD z przyszłym ruchem ceny
    corr_rsi = df['RSI'].corr(df['Zwrot'])
    corr_macd = df['MACD'].corr(df['Zwrot'])
    
    # Skalowanie wagi (bazowa waga to 1.0). Im wyższa korelacja, tym wyższa waga.
    w_rsi = min(max(abs(corr_rsi) * 5, 0.1), 2.0) if not np.isnan(corr_rsi) else 1.0
    w_macd = min(max(abs(corr_macd) * 5, 0.1), 2.0) if not np.isnan(corr_macd) else 1.0

    # Badanie wpływu czynników Makro (skorelowanych driverów)
    drivery = pobierz_drivery_dla_waloru(ticker)
    macro_tickers = [v["ticker"] for v in drivery.values()]
    dane_macro = pobierz_dane_multi(macro_tickers, period="6mo", interval="1d")
    
    w_macro = 1.0
    if dane_macro:
        df_macro = pd.DataFrame()
        df_macro['Zwrot_Glownego'] = df['Zwrot']
        for nazwa, v in drivery.items():
            mac_t = v["ticker"]
            if mac_t in dane_macro and not dane_macro[mac_t].empty:
                df_macro[mac_t] = dane_macro[mac_t]["Close"].pct_change()
        
        korelacje_makro = df_macro.corr()['Zwrot_Glownego'].drop('Zwrot_Glownego', errors='ignore')
        srednia_kor = korelacje_makro.abs().mean()
        if not np.isnan(srednia_kor):
            w_macro = min(max(srednia_kor * 8, 0.5), 3.0)

    # Fundamenty i LLM mają wyższą wagę domyślnie, ponieważ są nadrzędne
    wagi = {
        "w_trend": 1.0,
        "w_rsi": round(w_rsi, 2),
        "w_macd": round(w_macd, 2),
        "w_macro": round(w_macro, 2),
        "w_sentyment": 2.0,
        "w_fundament": 2.5
    }

    # Zapis wag do pliku konfiguracyjnego JSON
    if os.path.exists(PLIK_WAG):
        try:
            with open(PLIK_WAG, "r", encoding="utf-8") as f:
                baza_wag = json.load(f)
        except:
            baza_wag = {}
    else:
        baza_wag = {}

    baza_wag[ticker] = wagi
    with open(PLIK_WAG, "w", encoding="utf-8") as f:
        json.dump(baza_wag, f, indent=4)

    return wagi

def wczytaj_wagi(ticker: str):
    """Wczytuje zoptymalizowane wagi z pliku lub zwraca domyślne."""
    if os.path.exists(PLIK_WAG):
        try:
            with open(PLIK_WAG, "r", encoding="utf-8") as f:
                baza = json.load(f)
                if ticker in baza:
                    return baza[ticker]
        except:
            pass
    # Wartości domyślne, jeśli walor nie był jeszcze optymalizowany
    return {"w_trend": 1.0, "w_rsi": 1.0, "w_macd": 1.0, "w_macro": 1.0, "w_sentyment": 2.0, "w_fundament": 2.5}
