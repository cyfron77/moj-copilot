# modules/ai_engine.py
import pandas as pd

AI_PROFILES = {
    "Zbalansowany": {"w_trend": 1.0, "w_rsi": 1.0, "w_macd": 1.0, "w_sent": 1.0, "w_vol": 1.0},
    "Konserwatywny": {"w_trend": 1.5, "w_rsi": 1.0, "w_macd": 1.5, "w_sent": 0.5, "w_vol": 1.0},
    "Agresywny": {"w_trend": 0.8, "w_rsi": 1.2, "w_macd": 1.2, "w_sent": 1.0, "w_vol": 0.8},
}


def oblicz_ai_werdykt(
    cena: float,
    sma50: float,
    sma200: float,
    rsi: float,
    macd: float,
    macd_sig: float,
    avg_sent: float,
    atr: float,
    adx: float,
    vol_ratio: float,
    data_len: int,
    w_trend: float,
    w_rsi: float,
    w_macd: float,
    w_sent: float,
    w_vol: float,
) -> dict:
    jakosc_flags = []

    # Trend (SMA50)
    trend_signal = 1 if cena > sma50 else -1
    trend_opis = "Trend wzrostowy (Cena > SMA50)" if trend_signal == 1 else "Trend spadkowy (Cena < SMA50)"

    # RSI
    if rsi < 35:
        rsi_signal = 1
        rsi_opis = "Wyprzedanie (RSI < 35)"
    elif rsi > 70:
        rsi_signal = -1
        rsi_opis = "Wykupienie (RSI > 70)"
    else:
        rsi_signal = 0
        rsi_opis = "RSI neutralny (35–70)"

    # MACD
    if macd > macd_sig:
        macd_signal = 1
        macd_opis = "MACD > Sygnał (pro-wzrostowo)"
    else:
        macd_signal = -1
        macd_opis = "MACD < Sygnał (pro-spadkowo)"

    # Sentyment
    if avg_sent > 0.05:
        sent_signal = 1
        sent_opis = "Pozytywny / byczy"
    elif avg_sent < -0.05:
        sent_signal = -1
        sent_opis = "Negatywny / niedźwiedzi"
    else:
        sent_signal = 0
        sent_opis = "Neutralny"

    # Wolumen
    if not pd.isna(vol_ratio) and vol_ratio >= 1.3:
        vol_signal = 1
        vol_opis = "Wzmożony wolumen (>=130% średniej)"
    else:
        vol_signal = 0
        vol_opis = "Wolumen w normie / brak potwierdzenia"

    base_score = (
        w_trend * trend_signal
        + w_rsi * rsi_signal
        + w_macd * macd_signal
        + w_sent * sent_signal
        + w_vol * vol_signal
    )

    atr_ratio = atr / cena if cena > 0 else 0.0
    if data_len < 50:
        base_score *= 0.7
        jakosc_flags.append("⚠️ Mało danych (mniej niż 50 świec) – score x0.7")

    if atr_ratio > 0.05:
        jakosc_flags.append("⚠️ Bardzo wysoka zmienność (ATR > 5% ceny)")
    elif atr_ratio < 0.01:
        jakosc_flags.append("ℹ️ Niska zmienność (ATR < 1% ceny)")

    if not pd.isna(sma200):
        if cena < sma200:
            base_score *= 0.7
            jakosc_flags.append("⚠️ Cena poniżej SMA200 (score x0.7)")
        elif cena > sma200 and trend_signal == 1:
            base_score *= 1.1
            jakosc_flags.append("✅ Cena powyżej SMA200 i SMA50 (score x1.1)")

    if not pd.isna(adx):
        if adx < 20:
            base_score *= 0.8
            jakosc_flags.append("⚠️ Słaby trend (ADX < 20) (score x0.8)")
        elif adx > 25:
            base_score *= 1.1
            jakosc_flags.append("✅ Silny trend (ADX > 25) (score x1.1)")

    if base_score >= 3:
        status = "MOCNY KANDYDAT NA LONGA (KUPNO)"
        kolor = "success"
        komentarz = "Przewaga sygnałów prowzrostowych."
    elif base_score <= -3:
        status = "KANDYDAT NA SHORTA / OSTRZEŻENIE"
        kolor = "error"
        komentarz = "Przewaga sygnałów prospadkowych."
    else:
        status = "NEUTRALNY / OBSERWACJA"
        kolor = "info"
        komentarz = "Sygnały mieszane lub rynek w konsolidacji."

    return {
        "score": base_score,
        "status": status,
        "kolor": kolor,
        "komentarz": komentarz,
        "trend_opis": trend_opis,
        "rsi_opis": rsi_opis,
        "macd_opis": macd_opis,
        "sent_opis": sent_opis,
        "vol_opis": vol_opis,
        "jakosc_flags": jakosc_flags,
    }
