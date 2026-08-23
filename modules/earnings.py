# modules/earnings.py
import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

def pobierz_wyniki_tekst(symbol: str) -> str:
    """Funkcja dla LLM - pobiera historię zaskoczeń EPS (Earnings Surprise) jako tekst."""
    if any(ext in symbol for ext in ["=F", "-USD", "PLN=X", "^"]):
        return "Brak raportów kwartalnych (nie dotyczy tego typu aktywa)."

    try:
        t = yf.Ticker(symbol)
        tekst = ""
        
        try:
            earnings = t.get_earnings_dates(limit=4)
            if earnings is not None and not earnings.empty:
                df = earnings.copy().reset_index()
                df_reported = df.dropna(subset=["Reported EPS"])
                
                if not df_reported.empty:
                    tekst += "Historia zysku na akcję (EPS) i weryfikacja celów:\n"
                    for idx, row in df_reported.iterrows():
                        data_rap = str(row.iloc[0]).split(" ")[0]
                        rep = row.get("Reported EPS", "brak")
                        est = row.get("EPS Estimate", "brak")
                        surp = row.get("Surprise")
                        
                        surp_str = f"{round(surp * 100, 2)}%" if isinstance(surp, (int, float)) else "brak"
                        tekst += f"- {data_rap}: Zaraportowano {rep} (Prognoza: {est}). Zaskoczenie rynkowe: {surp_str}.\n"
        except:
            pass
            
        if not tekst:
            tekst = "Brak szczegółowej historii EPS w darmowej bazie danych. Oceń firmę na podstawie podanych fundamentów i newsów."
            
        return tekst
    except Exception as e:
        return f"Błąd bazy wyników: {str(e)}"

def wyswietl_kalendarz_wynikow(symbol: str):
    """Zwraca widok wykresu zysków do zakładki w aplikacji Streamlit."""
    if any(ext in symbol for ext in ["=F", "-USD", "PLN=X", "^"]):
        st.info("ℹ️ Wybrany walor nie publikuje raportów finansowych.")
        return

    try:
        t = yf.Ticker(symbol)

        try:
            kalendarz = t.calendar
        except Exception:
            kalendarz = None

        st.markdown("#### ⏳ Najbliższy raport finansowy")
        if kalendarz is not None:
            if isinstance(kalendarz, dict):
                data_raportu = kalendarz.get("Earnings Date", None)
                if data_raportu:
                    data_str = ", ".join([str(d.date()) if hasattr(d, "date") else str(d) for d in (data_raportu if isinstance(data_raportu, list) else [data_raportu])])
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
        st.markdown("#### 📊 Historia zaskoczeń wynikami (EPS Surprise)")
        try:
            earnings_dates = t.get_earnings_dates(limit=8)
        except Exception:
            earnings_dates = None

        if earnings_dates is not None and not earnings_dates.empty:
            df_earn = earnings_dates.copy().reset_index()
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
                df_reported["Data"] = pd.to_datetime(df_reported["Data Raportu"]).dt.strftime("%Y-%m-%d") if "Data Raportu" in df_reported.columns else df_reported.index.astype(str)

                fig = go.Figure()
                fig.add_trace(go.Bar(x=df_reported["Data"], y=df_reported.get("Szacowany EPS", []), name="Szacunek konsensusu", marker_color="rgba(150, 150, 150, 0.6)"))
                kolory = ["lime" if float(s or 0) >= 0 else "crimson" for s in df_reported.get("Zaskoczenie (%)", [0]*len(df_reported))]
                fig.add_trace(go.Bar(x=df_reported["Data"], y=df_reported.get("Zaraportowany EPS", []), name="Rzeczywisty EPS", marker_color=kolory))
                fig.update_layout(title=f"Wyniki EPS vs Oczekiwania: {symbol}", barmode="group", template="plotly_dark", height=350, margin=dict(l=20, r=20, t=40, b=20))
                st.plotly_chart(fig, use_container_width=True)

                st.markdown("##### 📝 Szczegółowa tabela raportów:")
                st.dataframe(df_earn, use_container_width=True)
            else:
                st.info("Brak zarchiwizowanych danych EPS.")
        else:
            st.info("Brak szczegółowej historii EPS w bazie.")
    except Exception as e:
        st.warning(f"Błąd modułu wyników: {e}")
