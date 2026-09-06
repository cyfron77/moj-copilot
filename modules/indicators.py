import pandas as pd
import numpy as np

def dodaj_zaawansowane_wskazniki(df: pd.DataFrame) -> pd.DataFrame:
    """
    Kalkulator wskaźników technicznych z podfolderu modules.
    Oblicza: SMA20, SMA50, SMA200, Bollinger Bands, OBV, RSI, MACD oraz ATR.
    """
    if len(df) < 20:
        return df

    # 1. Średnie kroczące (Reżim rynku)
    df['SMA20'] = df['Close'].rolling(window=20).mean()
    df['SMA50'] = df['Close'].rolling(window=50).mean()
    df['SMA200'] = df['Close'].rolling(window=200).mean()

    # 2. Wstęgi Bollingera (Mean-Reversion)
    std20 = df['Close'].rolling(window=20).std()
    df['BB_Upper'] = df['SMA20'] + (std20 * 2)
    df['BB_Lower'] = df['SMA20'] - (std20 * 2)

    # 3. OBV (On-Balance Volume) - Analiza przepływu kapitału
    if 'Volume' in df.columns:
        price_change = df['Close'].diff()
        direction = np.where(price_change > 0, 1, np.where(price_change < 0, -1, 0))
        df['OBV'] = (direction * df['Volume']).cumsum()
        df['OBV_SMA'] = df['OBV'].rolling(window=20).mean()

    # 4. RSI (Wykupienie / Wyprzedanie)
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))

    # 5. MACD (Momentum)
    ema12 = df['Close'].ewm(span=12, adjust=False).mean()
    ema26 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = ema12 - ema26
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']

    # 6. ATR (Zmienność do Stop Lossa)
    tr1 = df['High'] - df['Low']
    tr2 = (df['High'] - df['Close'].shift()).abs()
    tr3 = (df['Low'] - df['Close'].shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df['ATR'] = tr.rolling(window=14).mean()

    return df
