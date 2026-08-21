# modules/gemini_llm.py
import google.generativeai as genai
import os
import json
import streamlit as st

def pobierz_ocene_llm(walor_nazwa: str, newsy_tekst: str, dane_fundamentalne_tekst: str) -> dict:
    """
    Wysyła zebrane dane do Gemini i zwraca oceny liczbowe w formacie JSON.
    Wymaga ustawienia zmiennej środowiskowej GEMINI_API_KEY.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        st.warning("⚠️ Brak klucza API Gemini. Oceny LLM ustawiono na 0. Ustaw zmienną środowiskową GEMINI_API_KEY.")
        return {"sentyment_score": 0.0, "fundament_score": 0.0, "uzasadnienie": "Brak konfiguracji API."}

    genai.configure(api_key=api_key)
    # Używamy modelu flash, który jest szybki i tani w użyciu API
    model = genai.GenerativeModel('gemini-1.5-flash')

    prompt = f"""
    Jesteś analitykiem finansowym na Wall Street i GPW. 
    Przeanalizuj poniższe dane dla waloru: {walor_nazwa}.
    
    Wydaj ocenę w dwóch kategoriach w skali od -1.0 (bardzo negatywnie) do 1.0 (bardzo pozytywnie).
    
    Zwróć TYLKO czysty, poprawny kod JSON. Żadnego formatowania markdown, żadnych znaczników ```json.
    Struktura:
    {{
        "sentyment_score": float,
        "fundament_score": float,
        "uzasadnienie": "Zwięzłe uzasadnienie, max 2 zdania"
    }}

    Newsy z ostatnich dni:
    {newsy_tekst}

    Dane fundamentalne i kalendarz wyników:
    {dane_fundamentalne_tekst}
    """
    
    try:
        response = model.generate_content(prompt)
        # Czyszczenie odpowiedzi w razie gdyby LLM dodał znaczniki formatowania
        czysty_tekst = response.text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        wynik = json.loads(czysty_tekst)
        
        # Zabezpieczenie przed przekroczeniem skali
        wynik["sentyment_score"] = max(-1.0, min(1.0, float(wynik.get("sentyment_score", 0.0))))
        wynik["fundament_score"] = max(-1.0, min(1.0, float(wynik.get("fundament_score", 0.0))))
        
        return wynik
    except Exception as e:
        return {
            "sentyment_score": 0.0, 
            "fundament_score": 0.0, 
            "uzasadnienie": f"Błąd parsowania lub połączenia API LLM: {str(e)}"
        }
