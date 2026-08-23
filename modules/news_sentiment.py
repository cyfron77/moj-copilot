# modules/news_sentiment.py
import streamlit as st
import yfinance as yf
import feedparser
from textblob import TextBlob
from datetime import datetime

@st.cache_data(ttl=300)
def pobierz_swieze_newsy(symbol: str, query: str):
    news_list = []
    seen_urls = set()

    # 1. Yahoo Finance (Najświeższe raporty i breaking news)
    try:
        yf_ticker = yf.Ticker(symbol)
        raw_news = yf_ticker.news
        if raw_news:
            for n in raw_news[:8]:
                tytul = n.get("title", "")
                link = n.get("link", "#")
                ts = n.get("providerPublishTime", None)
                data_str = datetime.fromtimestamp(ts).strftime("%Y-%m-%d") if ts else "Świeże"
                zrodlo = n.get("publisher", "Yahoo Finance")
                
                if tytul and link not in seen_urls:
                    news_list.append({"tytul": tytul, "link": link, "data": data_str, "zrodlo": zrodlo})
                    seen_urls.add(link)
    except Exception:
        pass

    # 2. Google News RSS (Szeroki kontekst do 30 dni wstecz)
    is_pl = symbol.endswith(".WA")
    lang = "pl" if is_pl else "en-US"
    gl = "PL" if is_pl else "US"
    ceid = "PL:pl" if is_pl else "US:en"
    clean_q = query.replace(" ", "+")
    
    # Używamy when:30d aby zgarnąć wiadomości z całego miesiąca
    rss_url = f"https://news.google.com/rss/search?q={clean_q}+when:30d&hl={lang}&gl={gl}&ceid={ceid}"
    
    try:
        feed = feedparser.parse(rss_url)
        if feed.entries:
            for entry in feed.entries[:15]: # Zwiększono limit do 15 artykułów z Google
                link = entry.link
                if link not in seen_urls:
                    news_list.append({
                        "tytul": entry.title,
                        "link": link,
                        "data": entry.published if "published" in entry else "Ostatnie 30 dni",
                        "zrodlo": "Google News / Portale"
                    })
                    seen_urls.add(link)
    except Exception:
        pass

    return news_list

def przetworz_sentyment(raw_news: list, ticker: str) -> tuple[list, float]:
    """Przetwarza nagłówki klasycznym algorytmem TextBlob na potrzeby interfejsu UI (zakładka Sentyment)"""
    sentymenty = []
    news_items = []
    is_pl_symbol = ticker.endswith(".WA")

    for item in raw_news:
        if is_pl_symbol:
            polaryzacja = 0.0
            kolor = "⚪ Neutralny (PL)"
        else:
            analiza = TextBlob(item["tytul"])
            polaryzacja = analiza.sentiment.polarity
            kolor = "🟢 Pozytywny" if polaryzacja > 0.05 else ("🔴 Negatywny" if polaryzacja < -0.05 else "⚪ Neutralny")
        
        sentymenty.append(polaryzacja)
        news_items.append({
            "tytul": item["tytul"],
            "score": polaryzacja,
            "status": kolor,
            "data": item["data"],
            "zrodlo": item["zrodlo"],
            "link": item["link"],
        })

    avg_sent = sum(sentymenty) / len(sentymenty) if sentymenty else 0.0
    return news_items, avg_sent
