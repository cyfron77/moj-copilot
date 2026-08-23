# bot_skaner.py
import os
import time
import requests
import pandas as pd
import numpy as np

from modules.data_loader import pobierz_dane
from modules.news_sentiment import pobierz_swieze_newsy
from modules.fundamentals import pobierz_fundamenty_tekst
from modules.earnings import pobierz_wyniki_tekst
from modules.gemini_llm import pobierz_ocene_llm
from modules.ai_engine import oblicz_werdykt_quant
from modules.optimizer import wczytaj_wagi
from modules.journal import wczytaj_baze_aktywow

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def wyslij_telegram(wiadomosc):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Brak danych Telegrama w zmiennych środowiskowych.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": wiadomosc, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

def uruchom_skanowanie():
    aktywa = wczytaj_baze_aktywow()
    print(f"Rozpoczynam skanowanie {len(aktywa)} walorów...")

    for nazwa, info in aktywa.items():
        ticker = info["ticker"]
        query = info["search_term"]
        print(f"Analizuję {ticker}...")

        # 1. Pobieranie danych i wskaźników
        df = pobierz_dane(ticker, "6mo", "1d")
        if df is None or df.empty:
            continue

        ostatnia_cena = float(df["Close"].iloc[-1])
        sma50 = float(df["SMA50"].iloc[-1]) if not pd.isna(df["SMA50"].iloc[-1]) else ostatnia_cena
        sma200 = float(df["SMA200"].iloc[-1]) if not pd.isna(df["SMA200"].iloc[-1]) else np.nan
        rsi = float(df["RSI"].iloc[-1]) if not pd.isna(df["RSI"].iloc[-1]) else 50.0
        macd = float(df["MACD"].iloc[-1]) if not pd.isna(df["MACD"].iloc[-1]) else 0.0
        macd_sig = float(df["MACD_Signal"].iloc[-1]) if not pd.isna(df["MACD_Signal"].iloc[-1]) else 0.0
        
        # Wyliczanie zmienności ATR na potrzeby Telegrama (jeśli brak z data_loadera)
        if "ATR" in df.columns and not pd.isna(df["ATR"].iloc[-1]):
            atr = float(df["ATR"].iloc[-1])
        else:
            tr1 = df['High'] - df['Low']
            tr2 = (df['High'] - df['Close'].shift()).abs()
            tr3 = (df['Low'] - df['Close'].shift()).abs()
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = float(tr.rolling(window=14).mean().iloc[-1])

        # 2. Pobieranie danych tekstowych dla AI
        raw_news = pobierz_swieze_newsy(ticker, query)
        newsy_tekst = "\n".join([f"- [{n['data']}] {n['tytul']}" for n in raw_news])
        dane_fund = (
            f"--- BIEŻĄCA WYCENA ---\n{pobierz_fundamenty_tekst(ticker)}\n\n"
            f"--- WYNIKI (EPS) ---\n{pobierz_wyniki_tekst(ticker)}\n\n"
            f"Cena: {ostatnia_cena}, RSI: {rsi:.2f}."
        )

        # 3. Odpytanie modelu Gemini z 10-sekundową pauzą (Ochrona przed błędem 429 API)
        llm_data = pobierz_ocene_llm(ticker, newsy_tekst, dane_fund)
        time.sleep(10) 

        # 4. Werdykt Quant
        wagi = wczytaj_wagi(ticker)
        werdykt = oblicz_werdykt_quant(
            ostatnia_cena, sma50, sma200, rsi, macd, macd_sig,
            llm_data["sentyment_score"], llm_data["fundament_score"], 
            (0.5 if ostatnia_cena > sma50 else -0.5), wagi
        )

        # 5. Filtracja i wysyłka
        swing_status = werdykt["swing_status"]
        if "ZDECYDOWANY" in swing_status:
            # Obliczanie SL i TP dla Telegrama (Mnożnik x2)
            if "LONG" in swing_status:
                ikonka = "🟢"
                sl = ostatnia_cena - (atr * 2.0)
                tp = ostatnia_cena + (atr * 4.0)
            else:
                ikonka = "🔴"
                sl = ostatnia_cena + (atr * 2.0)
                tp = ostatnia_cena - (atr * 4.0)

            wiadomosc = (
                f"{ikonka} **ALERT QUANT MODEL** {ikonka}\n\n"
                f"**Aktywo:** {nazwa}\n"
                f"**Werdykt:** {swing_status} ({werdykt['swing_score']:.2f} pkt)\n\n"
                f"**Cena obecna:** {ostatnia_cena:.2f}\n"
                f"🛑 **Sugerowany SL:** {sl:.2f}\n"
                f"🎯 **Sugerowany TP:** {tp:.2f}\n\n"
                f"**Uzasadnienie AI:**\n{llm_data['uzasadnienie']}"
            )
            wyslij_telegram(wiadomosc)
            print(f"Wysłano alert Telegram dla {ticker}!")

    print("Zakończono pomyślnie sesję skanowania.")

if __name__ == "__main__":
    uruchom_skanowanie()
