# modules/correlations.py
import pandas as pd
from config_correlations import CORRELATION_MATRIX, DEFAULT_DRIVERS
from modules.data_loader import pobierz_dane_multi


def pobierz_drivery_dla_waloru(ticker: str) -> tuple[dict, str]:
    """Zwraca słownik driverów oraz opis dla danego tickera."""
    if ticker in CORRELATION_MATRIX:
        return CORRELATION_MATRIX[ticker]["drivery"], CORRELATION_MATRIX[ticker]["opis"]
    return DEFAULT_DRIVERS, "Zestaw ogólny (brak dedykowanej matrycy dla tego waloru w config_correlations.py)."


def oblicz_korelacje_makro(ticker: str, df_glowny: pd.DataFrame, period: str, interval: str) -> tuple[pd.Series, str]:
    """Wylicza korelacje Pearsona pomiędzy głównym walorem a jego dedykowanymi driverami."""
    drivery, opis = pobierz_drivery_dla_waloru(ticker)
    tickers_list = list(drivery.values())

    dane_macro = pobierz_dane_multi(tickers_list, period=period, interval=interval)

    df_corr = pd.DataFrame()
    df_corr[ticker] = df_glowny["Close"]

    for nazwa, mac_ticker in drivery.items():
        if mac_ticker in dane_macro and not dane_macro[mac_ticker].empty:
            df_corr[nazwa] = dane_macro[mac_ticker]["Close"]

    df_corr.dropna(inplace=True)

    if len(df_corr) > 10:
        korelacje = df_corr.corr(method="pearson")[ticker].drop(ticker)
        return korelacje, opis
    return pd.Series(), opis
