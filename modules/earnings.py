# modules/earnings.py
import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go


def wyswietl_kalendarz_wynikow(symbol: str):
    """Pobiera nadchodzące daty raportów oraz historyczne zaskoczenia EPS (Earnings Surprise)."""
    # Sprawdzenie aktywów niefirmowych
    if any(ext in symbol for ext in ["=F", "-USD", "PLN=X", "^"]):
        st.info("ℹ️ Wybrany walor (surowiec, waluta, krypto lub indeks) nie publikuje raportów finansowych.")
        return

    try:
        t = yf.Ticker(symbol)

        # 1. Nadchodzący raport finansowy
        try:
            kalendarz = t.calendar
        except Exception:
            kalendarz = None

        st.markdown("#### ⏳ Najbliższy raport finansowy")
        if kalendarz is not None:
            if isinstance(kalendarz, dict):
                data_raportu = kalendarz.get("Earnings Date", None)
                if data_raportu:
                    if isinstance(data_raportu, list):
                        data_str = ", ".join([str(d.date()) if hasattr(d, "date") else str(d) for d in data_raportu])
                    else:
                        data_str = str(data_raportu)
                    st.success(f"🗓️ Szacowana data kolejnego raportu: **{data_str}**")
                else:
                    st.info("Brak wpisu o dacie kolejnego raportu w Yahoo Finance.")
            elif isinstance(kalendarz, pd.DataFrame) and not kalendarz.empty:
                st.dataframe(kalendarz, use_container_width=True)
            else:
                st.info("Brak potwierdzonej daty kolejnego raportu.")
        else:
            st.info("Brak danych kalendarza dla tego waloru.")

        st.markdown("---")

        # 2. Historia wyników (EPS vs Oczekiwania)
        st.markdown("#### 📊 Historia zaskoczeń wynikami (EPS Surprise)")
        try:
            earnings_dates = t.get_earnings_dates(limit=8)
        except Exception:
            earnings_dates = None

        if earnings_dates is not None and not earnings_dates.empty:
            df_earn = earnings_dates.copy().reset_index()

            # Dopasowanie nazw kolumn
            rename_map = {}
            for c in df_earn.columns:
                c_str = str(c)
                if "Earnings Date" in c_str: rename_map[c] = "Data Raportu"
                elif "EPS Estimate" in c_str: rename_map[c] = "Szacowany EPS"
                elif "Reported EPS" in c_str: rename_map[c] = "Zaraportowany EPS"
                elif "Surprise" in c_str: rename_map[c] = "Zaskoczenie (%)"
            df_earn.rename(columns=rename_map, inplace=True)

            df_reported = df_earn.dropna(subset=["Zaraportowany EPS"]).copy()

            if not df_reported.empty:
                if "Data Raportu" in df_reported.columns:
                    df_reported["Data"] = pd.to_datetime(df_reported["Data Raportu"]).dt.strftime("%Y-%m-%d")
                else:
                    df_reported["Data"] = df_reported.index.astype(str)

                # Wykres słupkowy: Szacunek vs Realny wynik
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=df_reported["Data"],
                    y=df_reported.get("Szacowany EPS", []),
                    name="Szacunek konsensusu (EPS)",
                    marker_color="rgba(150, 150, 150, 0.6)"
                ))
                
                kolory = ["lime" if float(s or 0) >= 0 else "crimson" for s in df_reported.get("Zaskoczenie (%)", [0]*len(df_reported))]
                fig.add_trace(go.Bar(
                    x=df_reported["Data"],
                    y=df_reported.get("Zaraportowany EPS", []),
                    name="Rzeczywisty EPS",
                    marker_color=kolory
                ))

                fig.update_layout(
                    title=f"Wyniki EPS vs Oczekiwania analityków: {symbol}",
                    barmode="group",
                    template="plotly_dark",
                    height=350,
                    margin=dict(l=20, r=20, t=40, b=20)
                )
                st.plotly_chart(fig, use_container_width=True)

                st.markdown("##### 📝 Szczegółowa tabela raportów:")
                st.dataframe(df_earn, use_container_width=True)
            else:
                st.info("Brak zarchiwizowanych danych EPS dla tego waloru.")
        else:
            st.info("Yahoo Finance posiada ograniczone dane o wynikach EPS dla mniejszych spółek (np. część GPW). Dla spółek z USA dane są w pełni dostępne.")

    except Exception as e:
        st.warning(f"Nie udało się załadować modułu wyników: {e}")
