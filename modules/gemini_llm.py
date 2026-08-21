# modules/gemini_llm.py
import google.generativeai as genai
import os
import json
import streamlit as st

def pobierz_ocene_llm(walor_nazwa: str, newsy_tekst: str, dane_fundamentalne_tekst: str) -> dict:
    try:
        api_key = st.secrets.get("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY"))
    except:
        api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        return {"sentyment_score": 0.0, "fundament_score": 0.0, "uzasadnienie": "Brak klucza API."}

    genai.configure(api_key=api_key)

    try:
        # DIAGNOSTYKA: Pobieramy listę autoryzowanych modeli dla tego klucza
        dostepne_modele = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        st.warning(f"Diagnostyka API. Twój klucz widzi modele: {dostepne_modele}")
        
        # Automatyczny wybór pierwszego działającego modelu Gemini
        wybrany_model = next((m for m in dostepne_modele if "gemini" in m), None)
        
        if not wybrany_model:
            return {"sentyment_score": 0.0, "fundament_score": 0.0, "uzasadnienie": "Klucz API nie ma dostępu do żadnego modelu Gemini."}
        
        # GenerativeModel wymaga nazwy bez prefiksu "models/"
        nazwa_bez_prefiksu = wybrany_model.replace("models/", "")
        model = genai.GenerativeModel(nazwa_bez_prefiksu)

        prompt = f"""
        Oceń walor {walor_nazwa} w skali od -1.0 do 1.0. Zwróć TYLKO czysty kod JSON:
        {{"sentyment_score": float, "fundament_score": float, "uzasadnienie": "tekst"}}
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
