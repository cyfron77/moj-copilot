import pandas as pd
import numpy as np

def dodaj_zaawansowane_wskazniki(df: pd.DataFrame) -> pd.DataFrame:
    """
    Oblicza dodatkowe wskaźniki: SMA50, SMA200, Bollinger Bands oraz OBV.
    Wymaga DataFrame z kolumnami: 'Close' oraz 'Volume'.
    """
    # Zabezpieczenie przed brakami danych
    if len(df) < 20:
        return df

    # 1. Reżim Rynku (SMA50 i SMA200)
    df['SMA50'] = df['Close'].rolling(window=50).mean()
    df['SMA200'] = df['Close'].rolling(window=200).mean()

    # 2. Wstęgi Bollingera (BB) - standardowe ustawienia (okres 20, odchylenie standardowe x2)
    df['BB_Middle'] = df['Close'].rolling(window=20).mean()
    bb_std = df['Close'].rolling(window=20).std()
    
    df['BB_Upper'] = df['BB_Middle'] + (bb_std * 2)
    df['BB_Lower'] = df['BB_Middle'] - (bb_std * 2)

    # 3. OBV (On-Balance Volume)
    # Zmiana ceny: dodatnia -> dodajemy wolumen, ujemna -> odejmujemy wolumen
    price_change = df['Close'].diff()
    direction = np.where(price_change > 0, 1, np.where(price_change < 0, -1, 0))
    
    # Inicjalizacja pierwszej wartości wolumenu i kumulacja (cumsum)
    df['OBV'] = (direction * df['Volume']).cumsum()
    
    # Dodajemy linię sygnałową dla OBV (SMA z 20 okresów), by łapać trend wolumenu
    df['OBV_SMA'] = df['OBV'].rolling(window=20).mean()

    return df
