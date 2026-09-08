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
    cursor.execute('''
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
    ''')
    conn.commit()
    conn.close()

def pobierz_dziennik_z_bazy():
    """
    Pobiera pełny dziennik transakcji z SQLite (transakcje bota + wpisy ręczne).
    """
    inicjalizuj_baze()
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query(
        "SELECT id, ticker, nazwa, quantity, entry_price, sl, tp, "
        "entry_date, status, exit_price, pnl "
        "FROM transakcje ORDER BY entry_date",
        conn
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
    pnl: float | None
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

    cursor.execute('''
        INSERT INTO transakcje (
            ticker, nazwa, quantity, entry_price, sl, tp,
            entry_date, status, exit_price, pnl
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        ticker.upper(),
        nazwa,
        quantity,
        entry_price,
        0.0,
        0.0,
        entry_date,
        status_db,
        exit_price_db,
        pnl_db
    ))
    conn.commit()
    conn.close()

def policz_sharpe_z_pnl(pnls: pd.Series) -> float:
    """
    Uproszczony Sharpe: średni PnL na transakcję / odchylenie std z PnL (zamknięte).[web:75]
    """
    if pnls is None or len(pnls) < 2:
        return 0.0
    pnls_clean = pd.to_numeric(pnls, errors="coerce").dropna()
    if len(pnls_clean) < 2:
        return 0.0
    mean_pnl = pnls_clean.mean()
    std_pnl = pnls_clean.std()
    return float(mean_pnl / std_pnl) if std_pnl > 0 else 0.0

# --- PROSTE FUNKCJE BACKTESTU (SMA/RSI/MACD) ---
def download_data(symbol: str, period: str = "2y", interval: str = "1d") -> pd.DataFrame:
    """
    Dane z yfinance + wskaźniki z modules.indicators.[web:102][web:103]
    """
    df = yf.download(symbol, period=period, interval=interval, progress=False)
    if df is None or df.empty:
        raise ValueError(f"Nie udało się pobrać danych dla symbolu {symbol}")

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = indicators.dodaj_zaawansowane_wskazniki(df)

    required_cols = ["Close", "SMA50", "RSI", "MACD", "MACD_Signal", "ATR"]
    for col in required_cols:
