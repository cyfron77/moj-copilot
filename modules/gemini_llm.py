# modules/gemini_llm.py
import google.generativeai as genai
import os
import json
import streamlit as st

def pobierz_ocene_llm(walor_nazwa: str, newsy_tekst: str, dane_fundamentalne_tekst: str) -> dict:
    # Pobranie klucza
    try:
        api_key = st.secrets.get("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY"))
    except:
        api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        return {"sentyment_score": 0.0, "fundament_score": 0.0, "uzasadnienie": "Brak klucza API."}

    genai.configure(api_key=api_key)

    try:
        # Twarde przypisanie modelu wymaganego przez serwery API
        model = genai.GenerativeModel('gemini-3.6-flash')

        prompt = f"""
        Jesteś analitykiem finansowym na Wall Street i GPW. 
        Oceń walor {walor_nazwa} w skali od -1.0 (bardzo negatywnie) do 1.0 (bardzo pozytywnie). 
        Zwróć TYLKO czysty kod JSON, żadnych znaczników markdown:
        {{"sentyment_score": float, "fundament_score": float, "uzasadnienie": "Zwięzłe uzasadnienie, max 2 zdania"}}
        
        Newsy: {newsy_tekst}
        Fundamenty: {dane_fundamentalne_tekst}
        """
        
        response = model.generate_content(prompt)
        czysty_tekst = response.text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        wynik = json.loads(czysty_tekst)
        
        return {
            "sentyment_score": max(-1.0, min(1.0, float(wynik.get("sentyment_score", 0.0)))),
            "fundament_score": max(-1.0, min(1.0, float(wynik.get("fundament_score", 0.0)))),
            "uzasadnienie": wynik.get("uzasadnienie", "")
        }

    except Exception as e:
        return {"sentyment_score": 0.0, "fundament_score": 0.0, "uzasadnienie": f"Błąd API: {str(e)}"}
