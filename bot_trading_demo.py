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

# Konfiguracja Telegrama dla środowiska DEV
TG_TOKEN = os.getenv("TG_TOKEN_DEV")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")

def wyslij_telegram(wiadomosc):
    if not TG_TOKEN or not TG_CHAT_ID:
        print("⚠️ Brak skonfigurowanych kluczy Telegram dla DEV.")
        return False
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_CHAT_ID,
        "text": wiadomosc,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload)
        return response.status_code == 200
    except Exception as e:
        print(f"Błąd wysyłania Telegrama: {e}")
        return False

# Mapa aktywów: Ticker dla API brokera -> Ticker dla Yahoo Finance
aktywa_do_handlu = {
    "NVIDIA": {"t212": "NVDA_US_EQ", "yf": "NVDA", "search": "NVIDIA stock news"},
    "Apple": {"t212": "AAPL_US_EQ", "yf": "AAPL", "search": "Apple stock market news"},
    "Microsoft": {"t212": "MSFT_US_EQ", "yf": "MSFT", "search": "Microsoft stock news"},
    "Tesla": {"t212": "TSLA_US_EQ", "yf": "TSLA", "search": "Tesla stock market news"},
    "Alphabet (Google)": {"t212": "GOOGL_US_EQ", "yf": "GOOGL", "search": "Google stock market news"},
    "Amazon": {"t212": "AMZN_US_EQ", "yf": "AMZN", "search": "Amazon stock market news"},
    "Meta (Facebook)": {"t212": "META_US_EQ", "yf": "META", "search": "Meta Facebook stock news"},
    "JPMorgan": {"t212": "JPM_US_EQ", "yf": "JPM", "search": "JPMorgan stock market news"},
    "Visa": {"t212": "V_US_EQ", "yf": "V", "search": "Visa stock market news"},
    "Coca-Cola": {"t212": "KO_US_EQ", "yf": "KO", "search": "Coca Cola stock news"},
    "Disney": {"t212": "DIS_US_EQ", "yf": "DIS", "search": "Disney stock news"},
    "S&P 500 ETF": {"t212": "SPY_US_EQ", "yf": "SPY", "search": "S&P 500 index market today"},
    "Nasdaq 100 ETF": {"t212": "QQQ_US_EQ", "yf": "QQQ", "search": "Nasdaq 100 ETF market"}
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

def pobierz_otwarte_pozycje():
    url = f"{T212_BASE_URL}/positions"
    try:
        response = requests.get(url, auth=(T212_API_KEY, T212_API_SECRET))
        if response.status_code == 200:
            pozycje = response.json()
            otwarte_tickery = []
            if isinstance(pozycje, list):
                for p in pozycje:
                    tckr = p.get('ticker') or p.get('instrument', {}).get('ticker')
                    if tckr:
                        otwarte_tickery.append(tckr)
            return otwarte_tickery
    except Exception as e:
        print(f"Błąd pobierania pozycji: {e}")
    return []

# --- NOWOŚĆ: Funkcja zlecenia przyjmuje teraz ceny Stop Loss i Take Profit ---
def otwórz_pozycje_demo(ticker, quantity, sl_price, tp_price):
    url = f"{T212_BASE_URL}/orders/market"
    payload = {
        "quantity": quantity, 
        "ticker": ticker,
        "stopLoss": round(sl_price, 2),
        "takeProfit": round(tp_price, 2)
    }
    response = requests.post(url, json=payload, auth=(T212_API_KEY, T212_API_SECRET))
    return response.status_code == 200, response.json()

def analizuj_aktywo(nazwa, symbol_yf, query):
    df = yf.download(symbol_yf, period="3mo", interval="1d", progress=False)
    if df is None or df.empty:
        return False, 0.0, 0.0
        
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

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

    clean_q = query.replace(" ", "+")
    rss_url = f"https://news.google.com/rss/search?q={clean_q}+when:7d&hl=en-US&gl=US&ceid=US:en"
    feed = feedparser.parse(rss_url)
    sentymenty = []
    if feed.entries:
        for entry in feed.entries[:5]:
            polaryzacja = TextBlob(entry.title).sentiment.polarity
            sentymenty.append(polaryzacja)
    avg_sent = sum(sentymenty) / len(sentymenty) if sentymenty else 0.0

    punkty_bycze = 0
    if ostatnia_cena > sma50: punkty_bycze += 1
    if rsi < 35: punkty_bycze += 1
    if macd_val > macd_sig: punkty_bycze += 1
    if avg_sent > 0.05: punkty_bycze += 1

    print(f"[{nazwa}] Trend: {'UP' if ostatnia_cena>sma50 else 'DOWN'} | RSI: {rsi:.1f} | MACD: {'Byczy' if macd_val>macd_sig else 'Niedźwiedzi'} | Sentyment: {avg_sent:.2f}")
    
    if punkty_bycze >= 3:
        return True, ostatnia_cena, float(atr)
    return False, ostatnia_cena, float(atr)

def uruchom_automatyzacje():
    print("🛡️ Uruchamiam zaawansowanego bota (Quant Model + T212 API)...")
    free_cash, total_capital = pobierz_stan_konta()
    print(f"💰 Wolne środki: {free_cash:.2f} PLN | Całkowity kapitał: {total_capital:.2f} PLN")
    
    if free_cash < 200:
        print("❌ Brak wystarczających wolnych środków.")
        return

    try:
        df_usd = yf.download("USDPLN=X", period="1d", progress=False)
        if isinstance(df_usd.columns, pd.MultiIndex):
            df_usd.columns = df_usd.columns.get_level_values(0)
        kurs_usd_pln = float(df_usd['Close'].iloc[-1])
    except:
        kurs_usd_pln = 4.0
        
    print(f"💱 Aktualny kurs USD/PLN pobrany przez bota: {kurs_usd_pln:.4f}")

    posiadane_aktywa = pobierz_otwarte_pozycje()
    print(f"📂 Aktualnie posiadane tickery w portfelu: {posiadane_aktywa}")

    for nazwa, info in aktywa_do_handlu.items():
        print(f"\nSkupiam się na: {nazwa}...")
        
        if info["t212"] in posiadane_aktywa:
            print(f"🟡 POMINIĘCIE: Masz już otwartą pozycję na {nazwa} ({info['t212']}). Szukam dalej.")
            continue
            
        sygnal, cena_usd, atr_usd = analizuj_aktywo(nazwa, info["yf"], info["search"])
        
        if sygnal:
            print(f"🟢 MOCNY SYGNAŁ KUPNA DLA {nazwa}!")
            
            # Limity i wielkość pozycji
            ryzyko_max_pln = total_capital * 0.015
            ryzyko_max_usd = ryzyko_max_pln / kurs_usd_pln
            roznica_sl_usd = atr_usd * 2.0
            liczba_z_ryzyka = int(ryzyko_max_usd / roznica_sl_usd) if roznica_sl_usd > 0 else 0
            
            max_kapital_na_pozycje_pln = total_capital * 0.10
            max_kapital_na_pozycje_usd = max_kapital_na_pozycje_pln / kurs_usd_pln
            liczba_z_kapitalu = int(max_kapital_na_pozycje_usd / cena_usd) if cena_usd > 0 else 0
            
            wolumen = min(liczba_z_ryzyka, liczba_z_kapitalu)
            
            if wolumen < 1:
                print(f"🟡 Pomięcie {nazwa}: Akcja zbyt droga na bezpieczne wejście.")
                continue
            
            szacowany_koszt_usd = wolumen * cena_usd
            szacowany_koszt_pln = szacowany_koszt_usd * kurs_usd_pln
            
            if szacowany_koszt_pln > free_cash:
                print(f"⛔ Blokada kapitału: Szacowany koszt ({szacowany_koszt_pln:.2f} PLN) przewyższa wolne środki.")
                continue
            
            # --- NOWOŚĆ: Wyliczanie absolutnych poziomów SL i TP ---
            poziom_sl = cena_usd - roznica_sl_usd
            poziom_tp = cena_usd + (roznica_sl_usd * 2.0) # Take Profit 2x większy niż ryzyko (R:R 1:2)
                
            print(f"✅ Zlecenie: {wolumen} sztuk | SL: {poziom_sl:.2f}$ | TP: {poziom_tp:.2f}$")
            
            # Wysłanie zlecenia powiązanego do Trading 212
            sukces, wynik = otwórz_pozycje_demo(info["t212"], wolumen, poziom_sl, poziom_tp)
            
            if sukces:
                print(f"🚀 SUKCES: Wysłano zlecenie z ochroną SL/TP! Status: {wynik.get('status')}")
                
                notatka_blokady = ""
                if wolumen == liczba_z_kapitalu and liczba_z_kapitalu < liczba_z_ryzyka:
                    notatka_blokady = "\n⚠️ _Zadziałała blokada 10% kapitału_"
                
                wiada = (
                    f"🤖 *Copilot DEV (Trading 212)*\n\n"
                    f"✅ *Otwarto nową pozycję (AUTO SL/TP)!*\n"
                    f"- Aktywo: *{nazwa}*\n"
                    f"- Wolumen: `{wolumen}` szt.\n"
                    f"- Koszt: ok. `{szacowany_koszt_usd:.2f} USD`\n"
                    f"- 🛑 Stop Loss: `{poziom_sl:.2f} USD`\n"
                    f"- 🎯 Take Profit: `{poziom_tp:.2f} USD`"
                    f"{notatka_blokady}"
                )
                wyslij_telegram(wiada)
            else:
                print(f"❌ Odrzucono zlecenie: {wynik}")
        else:
            print(f"🟡 Brak idealnych warunków dla {nazwa}. Czekam.")

if __name__ == "__main__":
    uruchom_automatyzacje()
