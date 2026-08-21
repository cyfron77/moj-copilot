# modules/ai_engine.py
import pandas as pd

def generuj_sygnaly_techniczne(cena, sma50, sma200, rsi, macd, macd_sig):
    # RSI
    if rsi < 35: sig_rsi = 1
    elif rsi > 70: sig_rsi = -1
    else: sig_rsi = 0
    
    # MACD
    sig_macd = 1 if macd > macd_sig else -1
    
    # Trend
    sig_trend_kr = 1 if cena > sma50 else -1
    sig_trend_dl = 1 if (not pd.isna(sma200) and cena > sma200) else -1
    
    return sig_rsi, sig_macd, sig_trend_kr, sig_trend_dl

def oblicz_werdykt_quant(
    cena: float, sma50: float, sma200: float, rsi: float, macd: float, macd_sig: float,
    llm_sentyment: float, llm_fundament: float, makro_kierunek: float,
    wagi: dict
):
    sig_rsi, sig_macd, sig_trend_kr, sig_trend_dl = generuj_sygnaly_techniczne(cena, sma50, sma200, rsi, macd, macd_sig)
    
    # 1. Analiza Techniczna
    score_ta = (sig_rsi * wagi.get("w_rsi", 1.0)) + (sig_macd * wagi.get("w_macd", 1.0)) + (sig_trend_kr * wagi.get("w_trend", 1.0))
    
    # 2. Makro
    score_macro = makro_kierunek * wagi.get("w_macro", 1.0)
    
    # 3. Sentyment & Fundamenty (LLM)
    score_sent = llm_sentyment * wagi.get("w_sentyment", 2.0)
    score_fund = llm_fundament * wagi.get("w_fundament", 2.5)
    
    # Model Krótkoterminowy (Swing)
    swing_score = score_ta + score_macro + score_sent
    
    # Model Długoterminowy (Invest)
    long_score = (sig_trend_dl * wagi.get("w_trend", 1.0)) + score_macro + score_fund + (score_sent * 0.5)

    def klasyfikuj(s, prog):
        if s >= prog: return "ZDECYDOWANY LONG 🟢", "success"
        elif s > (prog/2): return "LEKKI LONG ↗️", "success"
        elif s <= -prog: return "ZDECYDOWANY SHORT 🔴", "error"
        elif s < -(prog/2): return "LEKKI SHORT ↘️", "error"
        else: return "NEUTRALNY / CZEKAJ ⚪", "warning"

    swing_status, swing_kolor = klasyfikuj(swing_score, 2.5)
    long_status, long_kolor = klasyfikuj(long_score, 3.0)

    return {
        "swing_score": swing_score,
        "swing_status": swing_status,
        "swing_kolor": swing_kolor,
        "long_score": long_score,
        "long_status": long_status,
        "long_kolor": long_kolor,
        "detale": {
            "TA": score_ta,
            "Makro": score_macro,
            "Sentyment": score_sent,
            "Fundamenty": score_fund
        }
    }
