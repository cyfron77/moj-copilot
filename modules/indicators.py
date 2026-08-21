# modules/indicators.py
import pandas as pd
import numpy as np


def dodaj_wskazniki(dane: pd.DataFrame) -> pd.DataFrame:
    """Dodaje SMA, Bollinger Bands, RSI, MACD, ATR, ADX oraz wskaźniki wolumenu."""
    if dane is None or dane.empty:
        return dane

    df = dane.copy()

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    potrzebne = {"Open", "High", "Low", "Close"}
    if not potrzebne.issubset(df.columns):
        rename_map = {}
        for c in df.columns:
            lc = c.lower()
            if "open" in lc:
                rename_map[c] = "Open"
            elif "high" in lc:
                rename_map[c] = "High"
            elif "low" in lc:
                rename_map[c] = "Low"
            elif "close" in lc and "adj" not in lc:
                rename_map[c] = "Close"
            elif "volume" in lc:
                rename_map[c] = "Volume"
        df.rename(columns=rename_map, inplace=True)

    # Średnie kroczące
    df["SMA20"] = df["Close"].rolling(window=20).mean()
    df["SMA50"] = df["Close"].rolling(window=50).mean()
    df["SMA200"] = df["Close"].rolling(window=200).mean()

    # RSI (14)
    delta = df["Close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df["RSI"] = 100 - (100 / (1 + rs))

    # Wstęgi Bollingera
    std20 = df["Close"].rolling(window=20).std()
    df["BB_Upper"] = df["SMA20"] + (std20 * 2)
    df["BB_Lower"] = df["SMA20"] - (std20 * 2)

    # MACD
    ema12 = df["Close"].ewm(span=12, adjust=False).mean()
    ema26 = df["Close"].ewm(span=26, adjust=False).mean()
    df["MACD"] = ema12 - ema26
    df["MACD_Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["MACD_Hist"] = df["MACD"] - df["MACD_Signal"]

    # ATR (14)
    tr1 = df["High"] - df["Low"]
    tr2 = (df["High"] - df["Close"].shift()).abs()
    tr3 = (df["Low"] - df["Close"].shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df["ATR"] = tr.rolling(window=14).mean()

    # ADX (14)
    up_move = df["High"] - df["High"].shift(1)
    down_move = df["Low"].shift(1) - df["Low"]
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    tr_rolling = tr.rolling(window=14).sum()
    plus_di = 100 * pd.Series(plus_dm).rolling(14).sum() / tr_rolling
    minus_di = 100 * pd.Series(minus_dm).rolling(14).sum() / tr_rolling
    dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
    df["ADX"] = dx.rolling(window=14).mean()

    # Wolumen
    if "Volume" in df.columns:
        df["Vol_MA20"] = df["Volume"].rolling(window=20).mean()
        df["Vol_Ratio"] = df["Volume"] / df["Vol_MA20"]
    else:
        df["Vol_MA20"] = np.nan
        df["Vol_Ratio"] = np.nan

    return df
