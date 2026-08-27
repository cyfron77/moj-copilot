import os
import time
import requests
import pandas as pd
import numpy as np
import yfinance as yf
import feedparser
from textblob import TextBlob
import re

# Konfiguracja API Trading 212 (Środowisko Demo)
T212_API_KEY = os.getenv("T212_API_KEY")
T212_API_SECRET = os.getenv("T212_API_SECRET")
T212_BASE_URL = "https://demo.trading212.com/api/v0/equity"

# Konfiguracja Telegrama dla środowiska DEV
TG_TOKEN = os.getenv("TG_TOKEN_DEV")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")

# Konfiguracja Hugging Face (FinBERT & Bielik)
HF_TOKEN = os.getenv("HF_API_TOKEN")

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

# --- SILNIK 1: FINBERT (DLA WALL STREET / USA) ---
def analizuj_sentyment_finbert(tytuly, token):
    if not tytuly:
        return [], "Brak newsów 📭"
    if not token:
        return [0.0] * len(tytuly), "Brak klucza HF"
    
    url = "https://router.huggingface.co/hf-inference/models/ProsusAI/finbert"
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.post(url, headers=headers, json={"inputs": tytuly}, timeout=20)
        if response.status_code == 200:
            wyniki = response.json()
            scores = []
            for res in wyniki:
                najlepszy = max(res, key=lambda x: x['score'])
                if najlepszy['label'] == 'positive':
                    scores.append(najlepszy['score'])
                elif najlepszy['label'] == 'negative':
                    scores.append(-najlepszy['score'])
                else:
                    scores.append(0.0)
            return scores, "FinBERT 🧠"
        elif response.status_code == 503:
            return [0.0] * len(tytuly), "FinBERT (Wybudzanie ⏳)"
        else:
            return [0.0] * len(tytuly), f"FinBERT (Błąd {response.status_code})"
    except Exception:
        return [0.0] * len(tytuly), "FinBERT (Błąd połączenia)"

# --- SILNIK 2: BIELIK LLM (DLA GPW / POLSKA) ---
def analizuj_sentyment_bielik(tytuly, token):
    if not tytuly:
        return 0.0, "Brak newsów 📭"
    if not token:
        return 0.0, "Brak klucza HF"
        
    # Stabilny adres API (router) współdzielony z FinBERTem
    url = "https://router.huggingface.co/hf-inference/models/speakleash/Bielik-7B-Instruct-v0.1"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    tekst_newsow = "\n".join([f"- {t}" for t in tytuly])
    prompt = (
        "Jesteś profesjonalnym analitykiem Giełdy Papierów Wartościowych w Warszawie. "
        "Oceń ogólny sentyment poniższych nagłówków wiadomości. "
        "Zwróć TYLKO I WYŁĄCZNIE jedną liczbę z przedziału od -1.0 (bardzo negatywny) do 1.0 (bardzo pozytywny). "
        "Zero oznacza neutralny. Nie pisz żadnych słów, tylko samą liczbę.\n\n"
        f"Wiadomości:\n{tekst_newsow}\n\nOcena:"
    )
    
    # Skonfigurowany, rygorystyczny payload z komendą wymuszającą oczekiwanie na model
    payload = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": 10,
            "return_full_text": False,
            "do_sample": False
        },
        "options": {
            "wait_for_model": True
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=70)
        
        if response.status_code == 200:
            wynik = response.json()
            # Bezpieczne wyciąganie tekstu z różnych struktur odpowiedzi
            if isinstance(wynik, list) and len(wynik) > 0:
                wygenerowany_tekst = wynik[0].get("generated_text", "").strip()
            elif isinstance(wynik, dict):
                wygenerowany_tekst = wynik.get("generated_text", "").strip()
            else:
                wygenerowany_tekst = str(wynik)
                
            dopasowanie = re.search(r"-?\d+\.\d+|-?\d+", wygenerowany_tekst)
            if dopasowanie:
                score = float(dopasowanie.group())
                score = max(-1.0, min(1.0, score))
                return score, "Bielik 🦅"
            else:
                return 0.0, "Bielik 🦅 (Zły format)"
        elif response.status_code == 503:
            return 0.0, "Bielik 🦅 (Wybudzanie ⏳)"
        else:
            return 0.0, f"Bielik (Błąd: {response.status_code})"
            
    except requests.exceptions.Timeout:
        return 0.0, "Bielik (Timeout ⏳)"
    except Exception as e:
        # Pokażemy krótką nazwę błędu (np. ConnectionError) zamiast długiego łańcucha
        error_msg = type(e).__name__ 
        return 0.0, f"Bielik (Błąd: {error_msg})"

# Mapa aktywów
aktywa_do_handlu = {
    "Apple": {"t212": "AAPL_US_EQ", "yf": "AAPL", "search": "Apple stock market news"},
    "Microsoft": {"t212": "MSFT_US_EQ", "yf": "MSFT", "search": "Microsoft stock news"},
    "NVIDIA": {"t212": "NVDA_US_EQ", "yf": "NVDA", "search": "NVIDIA stock news"},
    "Alphabet (Google)": {"t212": "GOOGL_US_EQ", "yf": "GOOGL", "search": "Google stock market news"},
    "Amazon": {"t212": "AMZN_US_EQ", "yf": "AMZN", "search": "Amazon stock market news"},
    "Meta (Facebook)": {"t212": "META_US_EQ", "yf": "META", "search": "Meta Facebook stock news"},
    "Tesla": {"t212": "TSLA_US_EQ", "yf": "TSLA", "search": "Tesla stock market news"},
    "Broadcom": {"t212": "AVGO_US_EQ", "yf": "AVGO", "search": "Broadcom stock news"},
    "JPMorgan": {"t212": "JPM_US_EQ", "yf": "JPM", "search": "JPMorgan stock market news"},
    "Visa": {"t212": "V_US_EQ", "yf": "V", "search": "Visa stock market news"},
    "Walmart": {"t212": "WMT_US_EQ", "yf": "WMT", "search": "Walmart stock news"},

    "PKO BP": {"t212": "PKO_PL_EQ", "yf": "PKO.WA", "search": "PKO BP bank gielda GPW"},
    "Orlen": {"t212": "ORL_PL_EQ", "yf": "ORL.WA", "search": "Orlen gielda GPW"},
    "CD Projekt": {"t212": "CDR_PL_EQ", "yf": "CDR.WA", "search": "CD Projekt gielda akcje"},
    "PZU": {"t212": "PZU_PL_EQ", "yf": "PZU.WA", "search": "PZU gielda GPW"},
    "Dino Polska": {"t212": "DNP_PL_EQ", "yf": "DNP.WA", "search": "Dino Polska gielda GPW"},
    "KGHM": {"t212": "KGH_PL_EQ", "yf": "KGH.WA", "search": "KGHM miedz gielda GPW"},
    "Allegro": {"t212": "ALE_PL_EQ", "yf": "ALE.WA", "search": "Allegro gielda GPW"},
    "LPP": {"t212": "LPP_PL_EQ", "yf": "LPP.WA", "search": "LPP gielda GPW"},
    "Bank Pekao": {"t212": "PEO_PL_EQ", "yf": "PEO.WA", "search": "Bank Pekao gielda GPW"},
    "mBank": {"t212": "MBK_PL_EQ", "yf": "MBK.WA", "search": "mBank gielda GPW"},

    "S&P 500 ETF (SPY)": {"t212": "SPY_US_EQ", "yf": "SPY", "search": "S&P 500 ETF news"},
    "Nasdaq 100 ETF (QQQ)": {"t212": "QQQ_US_EQ", "yf": "QQQ", "search": "Nasdaq 100 ETF news"},
    "Vanguard Total World (VT)": {"t212": "VT_US_EQ", "yf": "VT", "search": "Vanguard Total World Stock ETF"},
    "Vanguard All-World (VWCE)": {"t212": "VWCE_DE_EQ", "yf": "VWCE.DE", "search": "VWCE ETF market news"},
    "Emerging Markets ETF (VWO)": {"t212": "VWO_US_EQ", "yf": "VWO", "search": "Emerging markets ETF news"},
    "Dividend ETF (SCHD)": {"t212": "SCHD_US_EQ", "yf": "SCHD", "search": "Schwab Dividend ETF news"},
    "Gold Trust ETF (GLD)": {"t212": "GLD_US_EQ", "yf": "GLD", "search": "SPDR Gold Trust ETF news"},
    "20+ Year Treasury Bonds (TLT)": {"t212": "TLT_US_EQ", "yf": "TLT", "search": "iShares 20+ Year Treasury Bond ETF"},
    "Real Estate REITs (VNQ)": {"t212": "VNQ_US_EQ", "yf": "VNQ", "search": "Vanguard Real Estate ETF"},
    "ARK Innovation (ARKK)": {"t212": "ARKK_US_EQ", "yf": "ARKK", "search": "ARK Innovation ETF news"}
}

def pobierz_stan_konta():
    url = f"{T212_BASE_URL}/account/cash"
    try:
        response = requests.get(url, auth=(T212_API_KEY, T212_API_SECRET))
        if response.status_code == 200:
            data = response.json()
            return data.get("free", 0.0), data.get("total", 0.0)
    except:
        return 0.0, 0.0

def pobierz_otwarte_pozycje_szczegoly():
    url = f"{T212_BASE_URL}/positions"
    try:
        response = requests.get(url, auth=(T212_API_KEY, T212_API_SECRET))
        if response.status_code == 200:
            return response.json()
    except:
        return []

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

def analizuj_szeroki_rynek():
    df = yf.download("SPY", period="3mo", interval="1d", progress=False)
    if df is None or df.empty: return True, 0.0, 0.0
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    df['SMA50'] = df['Close'].rolling(window=50).mean()
    ostatnia_cena = float(df['Close'].iloc[-1])
    sma50 = float(df['SMA50'].iloc[-1])
    return ostatnia_cena > sma50, ostatnia_cena, sma50

def analizuj_aktywo(nazwa, symbol_yf, query):
    df_wk = yf.download(symbol_yf, period="2y", interval="1wk", progress=False)
    trend_tygodniowy_rosnacy = True 
    if df_wk is not None and not df_wk.empty:
        if isinstance(df_wk.columns, pd.MultiIndex): df_wk.columns = df_wk.columns.get_level_values(0)
        df_wk['SMA50'] = df_wk['Close'].rolling(window=50).mean()
        if not pd.isna(df_wk['SMA50'].iloc[-1]):
            trend_tygodniowy_rosnacy = float(df_wk['Close'].iloc[-1]) > float(df_wk['SMA50'].iloc[-1])

    df = yf.download(symbol_yf, period="3mo", interval="1d", progress=False)
    if df is None or df.empty: return False, 0.0, 0.0, "", ""
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)

    df['SMA50'] = df['Close'].rolling(window=50).mean()
    df['Vol_SMA20'] = df['Volume'].rolling(window=20).mean()
    ostatni_wolumen = float(df['Volume'].iloc[-1])
    wolumen_sma = float(df['Vol_SMA20'].iloc[-1])
    
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
    
    # --- HYBRYDOWY MÓZG (ROUTING AI) ---
    if symbol_yf.endswith(".WA") or "VWCE" in symbol_yf:
        rss_url = f"https://news.google.com/rss/search?q={clean_q}+when:7d&hl=pl&gl=PL&ceid=PL:pl"
        feed = feedparser.parse(rss_url)
        tytuly_newsow = [entry.title for entry in feed.entries[:5]] if feed.entries else []
        avg_sent, silnik = analizuj_sentyment_bielik(tytuly_newsow, HF_TOKEN)
    else:
        rss_url = f"https://news.google.com/rss/search?q={clean_q}+when:7d&hl=en-US&gl=US&ceid=US:en"
        feed = feedparser.parse(rss_url)
        tytuly_newsow = [entry.title for entry in feed.entries[:5]] if feed.entries else []
        sentymenty_wartosci, silnik = analizuj_sentyment_finbert(tytuly_newsow, HF_TOKEN)
        sentymenty = [float(val) for val in sentymenty_wartosci]
        avg_sent = sum(sentymenty) / len(sentymenty) if sentymenty else 0.0

    punkty_bycze = 0
    if ostatnia_cena > sma50: punkty_bycze += 1
    if rsi < 35: punkty_bycze += 1
    if macd_val > macd_sig: punkty_bycze += 1
    if avg_sent > 0.05: punkty_bycze += 1

    trend_1w_status = 'UP' if trend_tygodniowy_rosnacy else 'DOWN'
    trend_1d_status = 'UP' if ostatnia_cena > sma50 else 'DOWN'
    vol_status = 'WYSOKI' if ostatni_wolumen > wolumen_sma else 'NISKI'
    
    print(f"[{nazwa}] Trend: 1D {trend_1d_status} | 1W {trend_1w_status} | Vol: {vol_status} | RSI: {rsi:.1f} | MACD: {'Byczy' if macd_val>macd_sig else 'Niedz.'} | Sentyment: {avg_sent:.2f} ({silnik})")
    
    if punkty_bycze >= 3:
        if not trend_tygodniowy_rosnacy: return False, ostatnia_cena, float(atr), silnik, ""
        if ostatni_wolumen < wolumen_sma * 0.9: return False, ostatnia_cena, float(atr), silnik, ""
        uzasadnienie = f"RSI: {rsi:.1f} | MACD: {'Byczy' if macd_val>macd_sig else 'Niedźwiedzi'} | Sentyment NLP: {avg_sent:.2f}"
        return True, ostatnia_cena, float(atr), silnik, uzasadnienie
            
    return False, ostatnia_cena, float(atr), silnik, ""

def uruchom_automatyzacje():
    print("🛡️ Uruchamiam bota (Pełna agregacja raportu DEV)...")
    
    raport_otwarte_pozycje = ""
    raport_trailing_stop = ""
    
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

    print("\n🌎 Analizuję stan szerokiego rynku (Indeks S&P 500)...")
    rynek_rosnie, spy_cena, spy_sma50 = analizuj_szeroki_rynek()

    print("\n🛡️ Analizuję otwarte pozycje w poszukiwaniu okazji do Trailing Stopa (ochrona zysków)...")
    otwarte_szczegoly = pobierz_otwarte_pozycje_szczegoly()
    posiadane_tickery = []
    
    if isinstance(otwarte_szczegoly, list):
        for p in otwarte_szczegoly:
            tckr = p.get('ticker') or p.get('instrument', {}).get('ticker')
            if not tckr: continue
            posiadane_tickery.append(tckr)
            
            zysk_pln = float(p.get('walletImpact', {}).get('unrealizedProfitLoss', 0.0))
            if zysk_pln > 0:
                yf_sym = next((info['yf'] for info in aktywa_do_handlu.values() if info['t212'] == tckr), None)
                nazwa_spolki = next((nazwa for nazwa, info in aktywa_do_handlu.items() if info['t212'] == tckr), tckr)
                
                if yf_sym:
                    df_ts = yf.download(yf_sym, period="1mo", interval="1d", progress=False)
                    if df_ts is not None and not df_ts.empty:
                        if isinstance(df_ts.columns, pd.MultiIndex): df_ts.columns = df_ts.columns.get_level_values(0)
                        df_ts['SMA20'] = df_ts['Close'].rolling(window=20).mean()
                        cena_ts = float(df_ts['Close'].iloc[-1])
                        sma20_ts = float(df_ts['SMA20'].iloc[-1])
                        
                        if cena_ts < sma20_ts:
                            print(f"🚨 [TRAILING STOP] {nazwa_spolki}: Cena spadła poniżej SMA20!")
                            raport_trailing_stop += f"🚨 *{nazwa_spolki}*: Cena ({cena_ts:.2f}$) spadła poniżej SMA20. Obecny zysk: `+{zysk_pln:.2f} PLN`. Zalecane ręczne zabezpieczenie zysku!\n"

    for nazwa, info in aktywa_do_handlu.items():
        print(f"\nSkupiam się na: {nazwa}...")
        
        if info["t212"] in posiadane_tickery: continue
            
        sygnal, cena_usd, atr_usd, uzyty_silnik, uzasadnienie = analizuj_aktywo(nazwa, info["yf"], info["search"])
        
        if sygnal:
            if not rynek_rosnie: continue
            
            ryzyko_max_pln = total_capital * 0.015
            ryzyko_max_usd = ryzyko_max_pln / kurs_usd_pln
            roznica_sl_usd = atr_usd * 2.0
            liczba_z_ryzyka = int(ryzyko_max_usd / roznica_sl_usd) if roznica_sl_usd > 0 else 0
            
            max_kapital_na_pozycje_pln = total_capital * 0.10
            max_kapital_na_pozycje_usd = max_kapital_na_pozycje_pln / kurs_usd_pln
            liczba_z_kapitalu = int(max_kapital_na_pozycje_usd / cena_usd) if cena_usd > 0 else 0
            
            wolumen = min(liczba_z_ryzyka, liczba_z_kapitalu)
            if wolumen < 1: continue
            
            szacowany_koszt_usd = wolumen * cena_usd
            szacowany_koszt_pln = szacowany_koszt_usd * kurs_usd_pln
            if szacowany_koszt_pln > free_cash: continue
            
            poziom_sl = cena_usd - roznica_sl_usd
            poziom_tp = cena_usd + (roznica_sl_usd * 2.0)
                
            sukces, wynik = otwórz_pozycje_demo(info["t212"], wolumen, poziom_sl, poziom_tp)
            
            if sukces:
                print(f"🚀 SUKCES: {nazwa} - Wysłano zlecenie!")
                notatka_blokady = " (⚠️ Zmniejszono do 10% kapitału)" if (wolumen == liczba_z_kapitalu and liczba_z_kapitalu < liczba_z_ryzyka) else ""
                
                raport_otwarte_pozycje += (
                    f"✅ *{nazwa}* — `{wolumen}` szt. {notatka_blokady}\n"
                    f"   🔸 *Zabezpieczenia:* SL `{poziom_sl:.2f}$` | TP `{poziom_tp:.2f}$`\n"
                    f"   💡 *Uzasadnienie:* Silny trend 1D/1W, wysoki wolumen. {uzasadnienie}\n\n"
                )

    print("\n📩 Generowanie i wysyłanie raportu na Telegram...")
    
    wiadomosc_koncowa = "📊 *DZIENNY RAPORT BOTA COPILOT (DEV)* 📊\n\n"
    if not rynek_rosnie: wiadomosc_koncowa += "⚠️ *Filtr S&P 500:* Rynek znajduje się w trendzie spadkowym. Szukanie nowych pozycji długich (LONG) zostało na dziś zablokowane.\n\n"
         
    if raport_trailing_stop == "" and raport_otwarte_pozycje == "":
        wiadomosc_koncowa += "💤 *Brak nowych akcji na dziś.*\nSystem nie znalazł bezpiecznych okazji spełniających restrykcyjne kryteria i nie wykrył zagrożeń dla otwartych pozycji."
    else:
        if raport_trailing_stop: wiadomosc_koncowa += "🛡️ *ALERTY TRAILING STOP (Ochrona Zysku)*\n" + raport_trailing_stop + "\n"
        if raport_otwarte_pozycje: wiadomosc_koncowa += "🚀 *NOWE POZYCJE (KONTO DEMO)*\n" + raport_otwarte_pozycje
            
    wyslij_telegram(wiadomosc_koncowa)
    print("✅ Zakończono działanie skryptu i wysłano raport!")

if __name__ == "__main__":
    uruchom_automatyzacje()
