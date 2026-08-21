# modules/gemini_llm.py
import google.generativeai as genai
import os
import json
import streamlit as st

def pobierz_ocene_llm(walor_nazwa: str, newsy_tekst: str, dane_fundamentalne_tekst: str) -> dict:
    """
    Wysyła zebrane dane do Gemini i zwraca oceny liczbowe w formacie JSON.
    Pobiera klucz API ze Streamlit Secrets.
    """
    # Próba pobrania klucza ze Streamlit Secrets, a w ostateczności ze zmiennych środowiskowych
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
    except (FileNotFoundError, KeyError):
        api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        st.warning("⚠️ Brak klucza API Gemini. Oceny LLM ustawiono na 0. Skonfiguruj klucz w ustawieniach aplikacji.")
        return {"sentyment_score": 0.0, "fundament_score": 0.0, "uzasadnienie": "Brak konfiguracji API."}

    genai.configure(api_key=api_key)
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
        czysty_tekst = response.text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        wynik = json.loads(czysty_tekst)
        
        wynik["sentyment_score"] = max(-1.0, min(1.0, float(wynik.get("sentyment_score", 0.0))))
        wynik["fundament_score"] = max(-1.0, min(1.0, float(wynik.get("fundament_score", 0.0))))
        
        return wynik
    except Exception as e:
        return {
            "sentyment_score": 0.0, 
            "fundament_score": 0.0, 
            "uzasadnienie": f"Błąd parsowania lub połączenia API LLM: {str(e)}"
        }
