# modules/fundamentals.py
import yfinance as yf

def pobierz_fundamenty_tekst(ticker: str) -> str:
    """
    Pobiera kluczowe wskaźniki fundamentalne i zamienia je na skondensowany tekst dla modelu LLM.
    """
    # Wykluczenie walorów niebędących spółkami
    if any(ext in ticker for ext in ["=F", "-USD", "PLN=X", "^"]):
        return f"Walor {ticker} to surowiec, waluta lub indeks. Klasyczne wskaźniki (C/Z, P/B) nie mają tu zastosowania. Skup się na sentymencie makro."

    try:
        t = yf.Ticker(ticker)
        info = t.info
        
        if not info or "symbol" not in info:
            return "Brak szczegółowych danych fundamentalnych w bazie dla tego waloru."

        # Pobieranie danych z bezpiecznym fallbackiem
        pe = info.get("trailingPE") or "Brak"
        fwd_pe = info.get("forwardPE") or "Brak"
        pb = info.get("priceToBook") or "Brak"
        roe = info.get("returnOnEquity")
        debt_eq = info.get("debtToEquity") or "Brak"
        rev_growth = info.get("revenueGrowth")
        earn_growth = info.get("earningsGrowth")
        profit_margin = info.get("profitMargins")
        
        # Funkcja pomocnicza do formatowania procentów
        def format_pct(val):
            return f"{round(val * 100, 2)}%" if isinstance(val, (int, float)) else "Brak"

        tekst = (
            f"1. WYCENA: C/Z (Trailing P/E): {pe} | C/Z Prognoza (Forward P/E): {fwd_pe} | C/WK (P/B): {pb}.\n"
            f"2. ZYSKOWNOŚĆ: Zwrot z kapitału (ROE): {format_pct(roe)} | Marża netto: {format_pct(profit_margin)}.\n"
            f"3. WZROST (r/r): Wzrost przychodów: {format_pct(rev_growth)} | Wzrost zysków: {format_pct(earn_growth)}.\n"
            f"4. ZADŁUŻENIE: Dług do kapitału własnego (Debt/Equity): {debt_eq}."
        )
        return tekst

    except Exception as e:
        return f"Wystąpił błąd podczas pobierania danych fundamentalnych: {str(e)}"
