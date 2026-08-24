import os
import time
import requests
import pandas as pd
import numpy as np

# Konfiguracja API Trading 212 (Środowisko Demo)
T212_API_KEY = os.getenv("T212_API_KEY")
T212_API_SECRET = os.getenv("T212_API_SECRET")
T212_BASE_URL = "https://demo.trading212.com/api/v0/equity"

# W Pythonie nie musimy ręcznie kodować Base64, biblioteka 'requests' robi to za nas w parametrze 'auth'

def pobierz_stan_konta():
    """Moduł Ochrony Kapitału: sprawdza wolne środki i saldo konta demo"""
    url = f"{T212_BASE_URL}/account/cash"
    try:
        response = requests.get(url, auth=(T212_API_KEY, T212_API_SECRET))
        if response.status_code == 200:
            data = response.json()
            return data.get("free", 0.0), data.get("total", 0.0)
        else:
            print(f"❌ ODRZUCENIE Z SERWERA API! Kod błędu: {response.status_code}")
            print(f"Treść odpowiedzi od brokera: {response.text}")
    except Exception as e:
        print(f"Błąd pobierania danych konta: {e}")
    return 0.0, 0.0

def otwórz_pozycje_demo(ticker, quantity):
    """Wysyła zlecenie rynkowe do Trading 212 Demo"""
    url = f"{T212_BASE_URL}/orders/market"
    payload = {
        "quantity": quantity,
        "ticker": ticker
    }
    response = requests.post(url, json=payload, auth=(T212_API_KEY, T212_API_SECRET))
    return response.status_code == 200, response.json()

# ... (tutaj reszta kodu, funkcja uruchom_test_automatyzacji zostaje bez zmian) ...

def uruchom_test_automatyzacji():
    print("🛡️ Uruchamiam testową wersję Copilota z integracją Trading 212 Demo...")
    
    # 1. Sprawdzenie ochrony kapitału
    free_cash, total_capital = pobierz_stan_konta()
    print(f"💰 Wolne środki Demo: {free_cash:.2f} | Całkowity kapitał: {total_capital:.2f}")
    
    if free_cash < 200:
        print("❌ Ochrona kapitału: Zbyt mało wolnych środków na koncie demo. Przerywam.")
        return

    # Lista testowych aktywów powiązana z symbolami Trading 212
    aktywa_testowe = [
        {"nazwa": "NVIDIA", "ticker": "NVDA_US_EQ"},
        {"nazwa": "PKOBP", "ticker": "PKO.WA"}
    ]

    for aktywo in aktywa_testowe:
        ticker = aktywo["ticker"]
        print(f"Analizuję {aktywo['nazwa']} ({ticker})...")
        
        # Symulacja warunku wejścia (w docelowej wersji spięte z naszym silnikiem punktowym)
        sygnał_kupna = True 
        
        if sygnał_kupna:
            # Kalkulator ryzyka: przeznaczamy max 1.5% kapitału na transakcję
            dopuszczalne_ryzyko = total_capital * 0.015
            szacowana_cena = 100.0 # Przykładowa cena bazowa
            
            # Bezpieczny wolumen (np. 1 sztuka/kontrakt w celach testowych środowiska deweloperskiego)
            wolumen = 1.0 
            koszt_pozycji = wolumen * szacowana_cena
            
            # --- MODUŁ KONTROLI KAPITAŁU ---
            if koszt_pozycji > free_cash:
                print(f"⛔ Blokada kapitału: Koszt pozycji przekracza wolne środki.")
                continue
                
            print(f"✅ Warunki spełnione. Wysyłam zlecenie testowe dla {ticker}...")
            sukces, wynik = otwórz_pozycje_demo(ticker, wolumen)
            
            if sukces:
                print(f"🚀 SUKCES! Otwarto pozycję testową na koncie Demo. Odpowiedź: {wynik}")
            else:
                print(f"❌ Odrzucono zlecenie przez API: {wynik}")

if __name__ == "__main__":
    uruchom_test_automatyzacji()
