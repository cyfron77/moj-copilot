# modules/data_loader.py
import yfinance as yf
import pandas as pd
import streamlit as st
from modules.indicators import dodaj_wskazniki


@st.cache_data(ttl=600, persist="disk")
def pobierz_dane(symbol: str, period: str, interval: str) -> pd.DataFrame:
    """Pobiera dane dla pojedynczego symbolu i dodaje wskaźniki."""
    try:
        dane = yf.download(
            symbol,
            period=period,
            interval=interval,
            auto_adjust=False,
            progress=False,
        )
        if dane is not None and not dane.empty:
            dane = dodaj_wskazniki(dane)
        return dane
    except Exception:
        return None


@st.cache_data(ttl=600)
def pobierz_dane_multi(lista_symboli: list, period: str, interval: str) -> dict:
    """Pobiera dane dla wielu tickerów naraz."""
    if not lista_symboli:
        return {}

    try:
        raw = yf.download(
            tickers=lista_symboli,
            period=period,
            interval=interval,
            group_by="ticker",
            auto_adjust=False,
            progress=False,
        )

        wyniki = {}
        if isinstance(raw.columns, pd.MultiIndex):
            for sym in lista_symboli:
                try:
                    sub = raw[sym].copy()
                    sub = dodaj_wskazniki(sub)
                    wyniki[sym] = sub
                except Exception:
                    continue
        else:
            for sym in lista_symboli:
                d = yf.download(
                    sym,
                    period=period,
                    interval=interval,
                    auto_adjust=False,
                    progress=False,
                )
                if d is not None and not d.empty:
                    d = dodaj_wskazniki(d)
                    wyniki[sym] = d

        return wyniki
    except Exception:
        return {}
