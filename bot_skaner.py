# bot_skaner.py
import os
import time
import requests
import pandas as pd
import numpy as np

# Importy z modułów zbudowanych w naszym Quant Modelu
from modules.data_loader import pobierz_dane
from modules.news_sentiment import pobierz_swieze_newsy
from modules.fundamentals import pobierz_fundamenty_tekst
from modules.earnings import pobierz_wyniki_tekst
from modules.gemini_llm import pobierz_ocene_llm
from modules.ai_engine import oblicz_werdykt_quant
from modules.optimizer import wczytaj_wagi
from modules.journal import wczytaj_baze_aktywow

# Pobranie kluczy API z sekretów GitHuba
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

        # 1. Pobieranie danych technicznych z ostatnich 6 miesięcy
        df = pobierz_dane(ticker, "6mo", "1d")
        if df is None or df.empty:
            continue

        ostatnia_cena = float(df["Close"].iloc[-1])
        sma50 = float(df["SMA50"].iloc[-1]) if not pd.isna(df["SMA50"].iloc[-1]) else ostatnia_cena
        sma200 = float(df["SMA200"].iloc[-1]) if not pd.isna(df["SMA200"].iloc[-1]) else np.nan
        rsi = float(df["RSI"].iloc[-1]) if not pd.isna(df["RSI"].iloc[-1]) else 50.0
        macd = float(df["MACD"].iloc[-1]) if not pd.isna(df["MACD"].iloc[-1]) else 0.0
        macd_sig = float(df["MACD_Signal"].iloc[-1]) if not pd.isna(df["MACD_Signal"].iloc[-1]) else 0.0

        # 2. Agregacja danych tekstowych (newsy 30 dni + wskaźniki + EPS)
        raw_news = pobierz_swieze_newsy(ticker, query)
        newsy_tekst = "\n".join([f"- [{n['data']}] {n['tytul']}" for n in raw_news])
        dane_fund = (
            f"--- BIEŻĄCA WYCENA ---\n{pobierz_fundamenty_tekst(ticker)}\n\n"
            f"--- WYNIKI (EPS) ---\n{pobierz_wyniki_tekst(ticker)}\n\n"
            f"Cena: {ostatnia_cena}, RSI: {rsi:.2f}."
        )

        # 3. Odpytanie modelu Gemini (Z 3-sekundowym opóźnieniem chroniącym przed limitem)
        llm_data = pobierz_ocene_llm(ticker, newsy_tekst, dane_fund)
        time.sleep(3) 

        # 4. Finalny Werdykt Quant
        wagi = wczytaj_wagi(ticker)
        werdykt = oblicz_werdykt_quant(
            ostatnia_cena, sma50, sma200, rsi, macd, macd_sig,
            llm_data["sentyment_score"], llm_data["fundament_score"], 
            (0.5 if ostatnia_cena > sma50 else -0.5), wagi
        )

        # 5. Filtracja - bot powiadamia TYLKO dla bardzo mocnych sygnałów
        swing_status = werdykt["swing_status"]
        if "ZDECYDOWANY" in swing_status:
            ikonka = "🟢" if "LONG" in swing_status else "🔴"
            wiadomosc = (
                f"{ikonka} **ALERT QUANT MODEL** {ikonka}\n\n"
                f"**Aktywo:** {nazwa}\n"
                f"**Werdykt:** {swing_status} (Punkty: {werdykt['swing_score']:.2f})\n"
                f"**Cena obecna:** {ostatnia_cena:.2f}\n\n"
                f"**Uzasadnienie AI:**\n{llm_data['uzasadnienie']}"
            )
            wyslij_telegram(wiadomosc)
            print(f"Wysłano alert Telegram dla {ticker}!")

    print("Zakończono pomyślnie sesję skanowania.")

if __name__ == "__main__":
    uruchom_skanowanie()
