import sys
from datetime import datetime
import pandas as pd
import numpy as np
import yfinance as yf

# Zakładamy, że moduł indicators.py jest w folderze modules
from modules import indicators


def download_data(symbol: str, period: str = "2y", interval: str = "1d") -> pd.DataFrame:
    """
    Pobiera dane z yfinance i dodaje zaawansowane wskaźniki z modules.indicators.[web:102][web:103]
    """
    df = yf.download(symbol, period=period, interval=interval, progress=False)
    if df is None or df.empty:
        raise ValueError(f"Nie udało się pobrać danych dla symbolu {symbol}")

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # Dodanie wskaźników: SMA, RSI, MACD, ATR, Bollinger etc.
    df = indicators.dodaj_zaawansowane_wskazniki(df)

    # Upewniamy się, że mamy podstawowe kolumny
    required_cols = ["Close", "SMA50", "RSI", "MACD", "MACD_Signal", "ATR"]
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Brakuje kolumny {col} w danych po dodaniu wskaźników")

    df = df.dropna(subset=required_cols).copy()
    return df


def run_backtest(
    df: pd.DataFrame,
    start_cash: float = 10000.0,
    risk_pct: float = 0.015,
    atr_mult: float = 2.0,
) -> dict:
    """
    Prosty backtest strategii long-only:
    - Wejście LONG gdy:
        Close > SMA50, RSI < 35, MACD > MACD_Signal (3 punkty bycze)
    - SL = Close - ATR * atr_mult
    - TP = Close + ATR * atr_mult * 2
    - Wyjście przy SL, TP albo gdy MACD < MACD_Signal lub Close < SMA50.
    """
    equity = start_cash
    cash = start_cash
    position_qty = 0
    entry_price = None
    sl_price = None
    tp_price = None
    entry_date = None

    equity_curve = []
    trades = []

    for idx, row in df.iterrows():
        close = float(row["Close"])
        sma50 = float(row["SMA50"])
        rsi = float(row["RSI"])
        macd = float(row["MACD"])
        macd_sig = float(row["MACD_Signal"])
        atr = float(row["ATR"])

        # Aktualizacja krzywej kapitału (jeśli mamy otwartą pozycję, equity = cash + wartość pozycji)
        if position_qty > 0 and entry_price is not None:
            equity = cash + position_qty * close
        equity_curve.append({"date": idx, "equity": equity})

        # Logika wyjścia, jeśli mamy pozycję
        if position_qty > 0:
            exit_reason = None
            exit_price = None

            # Stop Loss
            if close <= sl_price:
                exit_reason = "SL"
                exit_price = close

            # Take Profit
            elif close >= tp_price:
                exit_reason = "TP"
                exit_price = close

            # Odwrócenie sygnału (MACD < sygnał albo cena < SMA50)
            elif (macd < macd_sig) or (close < sma50):
                exit_reason = "SignalExit"
                exit_price = close

            if exit_reason is not None and exit_price is not None:
                pnl = (exit_price - entry_price) * position_qty
                cash += position_qty * exit_price
                equity = cash
                trades.append({
                    "entry_date": entry_date,
                    "exit_date": idx,
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "qty": position_qty,
                    "pnl": pnl,
                    "reason": exit_reason,
                })
                # Zamykamy pozycję
                position_qty = 0
                entry_price = None
                sl_price = None
                tp_price = None
                entry_date = None

                # Po wyjściu przechodzimy do kolejnej świecy
                continue

        # Logika wejścia, jeśli NIE mamy pozycji
        if position_qty == 0:
            punkty_bycze = 0
            if close > sma50:
                punkty_bycze += 1
            if rsi < 35:
                punkty_bycze += 1
            if macd > macd_sig:
                punkty_bycze += 1

            # Wymagamy min. 3 punktów byczych (jak w bocie)
            if punkty_bycze >= 3:
                # Wyznaczenie SL / TP na bazie ATR
                sl = close - atr * atr_mult
                tp = close + atr * atr_mult * 2.0
                if sl >= close:
                    # ATR zbyt mały lub dane dziwne, pomijamy
                    continue

                ryzyko_max_kwota = equity * risk_pct
                risk_per_share = close - sl
                qty = int(ryzyko_max_kwota / risk_per_share) if risk_per_share > 0 else 0

                if qty < 1:
                    continue

                koszt_pozycji = qty * close
                if koszt_pozycji > cash:
                    continue

                # Otwieramy pozycję
                position_qty = qty
                entry_price = close
                sl_price = sl
                tp_price = tp
                entry_date = idx

                cash -= koszt_pozycji
                equity = cash + position_qty * close

    # Po pętli: jeśli została otwarta pozycja, zamykamy ją po ostatniej cenie
    if position_qty > 0 and entry_price is not None:
        last_idx = df.index[-1]
        last_close = float(df["Close"].iloc[-1])
        pnl = (last_close - entry_price) * position_qty
        cash += position_qty * last_close
        equity = cash
        trades.append({
            "entry_date": entry_date,
            "exit_date": last_idx,
            "entry_price": entry_price,
            "exit_price": last_close,
            "qty": position_qty,
            "pnl": pnl,
            "reason": "EndOfData",
        })

    # Metryki
    trades_df = pd.DataFrame(trades)
    equity_df = pd.DataFrame(equity_curve)

    total_pnl = trades_df["pnl"].sum() if not trades_df.empty else 0.0
    num_trades = len(trades_df)
    wins = len(trades_df[trades_df["pnl"] > 0]) if not trades_df.empty else 0
    losses = len(trades_df[trades_df["pnl"] <= 0]) if not trades_df.empty else 0
    win_rate = (wins / num_trades * 100.0) if num_trades > 0 else 0.0

    # Sharpe na podstawie PnL per trade (uproszczony)
    if num_trades > 1:
        mean_pnl = trades_df["pnl"].mean()
        std_pnl = trades_df["pnl"].std()
        sharpe = float(mean_pnl / std_pnl) if std_pnl > 0 else 0.0
    else:
        sharpe = 0.0

    # Max drawdown na podstawie krzywej kapitału
    equity_series = equity_df["equity"]
    running_max = equity_series.cummax()
    drawdown = (equity_series - running_max) / running_max
    max_dd = float(drawdown.min()) if len(drawdown) > 0 else 0.0

    result = {
        "start_cash": start_cash,
        "end_equity": float(equity_df["equity"].iloc[-1]) if not equity_df.empty else start_cash,
        "total_pnl": float(total_pnl),
        "num_trades": int(num_trades),
        "wins": int(wins),
        "losses": int(losses),
        "win_rate": float(win_rate),
        "sharpe": float(sharpe),
        "max_drawdown_pct": max_dd * 100.0,
        "trades_df": trades_df,
        "equity_df": equity_df,
    }
    return result


def main():
    if len(sys.argv) > 1:
        symbol = sys.argv[1]
    else:
        symbol = "SPY"  # domyślnie indeksowy ETF S&P 500

    print(f"📊 Uruchamiam prosty backtest dla: {symbol}")
    df = download_data(symbol, period="2y", interval="1d")
    result = run_backtest(df)

    print("\n=== Wyniki backtestu ===")
    print(f"Startowy kapitał: {result['start_cash']:.2f}")
    print(f"Końcowy kapitał: {result['end_equity']:.2f}")
    print(f"Łączny PnL: {result['total_pnl']:.2f}")
    print(f"Liczba transakcji: {result['num_trades']}")
    print(f"Wygrane / Przegrane: {result['wins']} / {result['losses']}")
    print(f"Win Rate: {result['win_rate']:.1f}%")
    print(f"Sharpe (per trade): {result['sharpe']:.2f}")
    print(f"Maksymalny drawdown: {result['max_drawdown_pct']:.2f}%")

    # Zapis wyników do CSV (opcjonalnie)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    trades_path = f"backtest_{symbol}_{timestamp}_trades.csv"
    equity_path = f"backtest_{symbol}_{timestamp}_equity.csv"

    result["trades_df"].to_csv(trades_path, index=False)
    result["equity_df"].to_csv(equity_path, index=False)

    print(f"\nZapisano szczegóły transakcji do: {trades_path}")
    print(f"Zapisano krzywą kapitału do: {equity_path}")


if __name__ == "__main__":
    main()
