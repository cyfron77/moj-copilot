# modules/news_sentiment.py
import streamlit as st
import yfinance as yf
import feedparser
from textblob import TextBlob
from datetime import datetime


@st.cache_data(ttl=300)
def pobierz_swieze_newsy(symbol: str, query: str):
    news_list = []
    try:
        yf_ticker = yf.Ticker(symbol)
        raw_news = yf_ticker.news
        if raw_news:
            for n in raw_news[:6]:
                tytul = n.get("title", "")
                link = n.get("link", "#")
                ts = n.get("providerPublishTime", None)
                data_str = (
                    datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
                    if ts
                    else "Świeże"
                )
                zrodlo = n.get("publisher", "Yahoo Finance")
                if tytul:
                    news_list.append({"tytul": tytul, "link": link, "data": data_str, "zrodlo": zrodlo})
    except Exception:
        pass

    if len(news_list) < 2:
        is_pl = symbol.endswith(".WA")
        lang = "pl" if is_pl else "en-US"
        gl = "PL" if is_pl else "US"
        ceid = "PL:pl" if is_pl else "US:en"
        clean_q = query.replace(" ", "+")
        rss_url = f"https://news.google.com/rss/search?q={clean_q}+when:7d&hl={lang}&gl={gl}&ceid={ceid}"
        feed = feedparser.parse(rss_url)
        if feed.entries:
            for entry in feed.entries[:6]:
                news_list.append({
                    "tytul": entry.title,
                    "link": entry.link,
                    "data": entry.published if "published" in entry else "Ostatnie dni",
                    "zrodlo": "Google News / Portale",
                })
    return news_list


def przetworz_sentyment(raw_news: list, ticker: str) -> tuple[list, float]:
    sentymenty = []
    news_items = []
    is_pl_symbol = ticker.endswith(".WA")

    for item in raw_news:
        if is_pl_symbol:
            polaryzacja = 0.0
            kolor = "⚪ Neutralny (PL – brak analizy AI)"
        else:
            analiza = TextBlob(item["tytul"])
            polaryzacja = analiza.sentiment.polarity
            kolor = (
                "🟢 Pozytywny" if polaryzacja > 0.05
                else ("🔴 Negatywny" if polaryzacja < -0.05 else "⚪ Neutralny")
            )
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
