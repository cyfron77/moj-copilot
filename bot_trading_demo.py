import os
import time
import requests
import pandas as pd
import numpy as np
import yfinance as yf
import feedparser
from textblob import TextBlob

# Konfiguracja API Trading 212 (Środowisko Demo)
T212_API_KEY = os.getenv("T212_API_KEY")
T212_API_SECRET = os.getenv("T212_API_SECRET")
T212_BASE_URL = "https://demo.trading212.com/api/v0/equity"

# Mapa aktywów: Ticker dla API brokera -> Ticker dla Yahoo Finance
aktywa_do_handlu = {
    "NVIDIA": {"t212": "NVDA_US_EQ", "yf": "NVDA", "search": "NVIDIA stock news"},
    "Apple": {"t212": "AAPL_US_EQ", "yf": "AAPL", "search": "Apple stock market news"},
    "Microsoft": {"t212": "MSFT_US_EQ", "yf": "MSFT", "search": "Microsoft stock news"}
}

def pobierz_stan_konta():
    url = f"{T212_BASE_URL}/account/cash"
    try:
        response = requests.get(url, auth=(T212_API_KEY, T212_API_SECRET))
        if response.status_code == 200:
            data = response.json()
            return data.get("free", 0.0), data.get("total", 0.0)
    except Exception as e:
        print(f"Błąd konta: {e}")
    return 0.0, 0.0

def otwórz_pozycje_demo(ticker, quantity):
    url = f"{T212_BASE_URL}/orders/market"
    payload = {"quantity": quantity, "ticker": ticker}
    response = requests.post(url, json=payload, auth=(T212_API_KEY, T212_API_SECRET))
    return response.status_code == 200, response.json()

def analizuj_aktywo(nazwa, symbol_yf, query):
    """Pobiera dane z Yahoo, liczy wskaźniki i wydaje werdykt AI (Quant Model)"""
    # 1. Pobieranie danych historycznych
    df = yf.download(symbol_yf, period="3mo", interval="1d", progress=False)
    if df is None or df.empty:
        return False, 0.0, 0.0
        
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # 2. Obliczanie wskaźników (Zgodnie z naszym modelem z aplikacji)
    df['SMA50'] = df['Close'].rolling(window=50).mean()
    
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    ema12 = df['Close'].ewm(span=12, adjust=False).mean()
    ema26 = df['Close'].ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    macd_signal = macd.ewm(span=9, adjust=False).mean()
    
    # Obliczanie ATR do zarządzania ryzykiem
    tr1 = df['High'] - df['Low']
    tr2 = (df['High'] - df['Close'].shift()).abs()
    tr3 = (df['Low'] - df['Close'].shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=14).mean().iloc[-1]

    ostatnia_cena = float(df['Close'].iloc[-1])
    sma50 = float(df['SMA50'].iloc[-1])
    rsi = float(df['RSI'].iloc[-1])
    macd_val = float(macd.iloc[-1])
    macd_sig = float(macd_signal.iloc[-1])

    # 3. Analiza sentymentu
    clean_q = query.replace(" ", "+")
    rss_url = f"https://news.google.com/rss/search?q={clean_q}+when:7d&hl=en-US&gl=US&ceid=US:en"
    feed = feedparser.parse(rss_url)
    sentymenty = []
    if feed.entries:
        for entry in feed.entries[:5]:
            polaryzacja = TextBlob(entry.title).sentiment.polarity
            sentymenty.append(polaryzacja)
    avg_sent = sum(sentymenty) / len(sentymenty) if sentymenty else 0.0

    # 4. SILNIK DECYZYJNY (System Punktowy)
    punkty_bycze = 0
    
    if ostatnia_cena > sma50: punkty_bycze += 1
    if rsi < 35: punkty_bycze += 1  # Wyprzedanie = okazja
    if macd_val > macd_sig: punkty_bycze += 1
    if avg_sent > 0.05: punkty_bycze += 1

    print(f"[{nazwa}] Trend: {'UP' if ostatnia_cena>sma50 else 'DOWN'} | RSI: {rsi:.1f} | MACD: {'Byczy' if macd_val>macd_sig else 'Niedźwiedzi'} | Sentyment: {avg_sent:.2f}")
    
    # Wymagamy minimum 3 sygnałów "za", by uznać to za MOCNEGO LONGA
    if punkty_bycze >= 3:
        return True, ostatnia_cena, float(atr)
    return False, ostatnia_cena, float(atr)

def uruchom_automatyzacje():
    print("🛡️ Uruchamiam zaawansowanego bota (Quant Model + T212 API)...")
    free_cash, total_capital = pobierz_stan_konta()
    print(f"💰 Wolne środki: {free_cash:.2f} | Całkowity kapitał: {total_capital:.2f}")
    
    if free_cash < 200:
        print("❌ Brak wystarczających wolnych środków.")
        return

    for nazwa, info in aktywa_do_handlu.items():
        print(f"\nSkupiam się na: {nazwa}...")
        sygnal, cena, atr = analizuj_aktywo(nazwa, info["yf"], info["search"])
        
        if sygnal:
            print(f"🟢 MOCNY SYGNAŁ KUPNA DLA {nazwa}!")
            
            # Inteligentny kalkulator ryzyka (max 1.5% kapitału na transakcję)
            ryzyko_max_kwota = total_capital * 0.015
            roznica_sl = atr * 2.0  # Stop loss o szerokości 2 ATR
            
            # Liczymy ile sztuk możemy kupić
            wolumen = max(1, int(ryzyko_max_kwota / roznica_sl))
            szacowany_koszt = wolumen * cena
            
            if szacowany_koszt > free_cash:
                print(f"⛔ Blokada kapitału: Szacowany koszt ({szacowany_koszt:.2f}) przekracza gotówkę ({free_cash:.2f}).")
                continue
                
            print(f"✅ Zlecenie spełnia warunki ryzyka. Wysyłam zakup na {wolumen} sztuk.")
            sukces, wynik = otwórz_pozycje_demo(info["t212"], wolumen)
            if sukces:
                print(f"🚀 SUKCES: Wysłano zlecenie! Status z API: {wynik.get('status')}")
            else:
                print(f"❌ Odrzucono zlecenie: {wynik}")
        else:
            print(f"🟡 Brak idealnych warunków dla {nazwa}. Czekam.")

if __name__ == "__main__":
    uruchom_automatyzacje()
