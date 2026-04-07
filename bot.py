import requests
import os
from datetime import datetime
from openai import OpenAI

# 🔑 KEYS
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

# 📰 FETCH NEWS (Yahoo Finance RSS)
def fetch_news():
    url = "https://feeds.finance.yahoo.com/rss/2.0/headline?s=spy,aapl,msft,nvda,tsla&region=US&lang=en-US"
    
    r = requests.get(url)
    text = r.text

    headlines = []

    # extraction simple des titres RSS
    parts = text.split("<title>")
    for p in parts[2:15]:  # skip first junk + limit
        title = p.split("</title>")[0]
        if len(title) > 20:
            headlines.append(title)

    return headlines


# 📊 FETCH MARKET DATA (Yahoo)
def fetch_market_data():
    tickers = ["SPY", "QQQ", "XLE", "XLF"]

    data = {}

    for t in tickers:
        url = f"https://query1.finance.yahoo.com/v7/finance/quote?symbols={t}"
        try:
            r = requests.get(url).json()
            quote = r["quoteResponse"]["result"][0]
            change = quote.get("regularMarketChangePercent", 0)
            data[t] = round(change, 2)
        except:
            data[t] = 0

    return data


# 🧠 GPT ANALYSIS (STYLE TEA)
def generate_recap(headlines, market_data):

    news_text = "\n".join(headlines)

    market_text = "\n".join([f"{k}: {v}%" for k, v in market_data.items()])

    prompt = f"""
You are a macro strategist like Liz Ann Sonders with a light, punchy tone.

Create a SHORT market recap.

Structure:
1. Macro & Geopolitics (MOST IMPORTANT)
2. Market behavior (use SPY, QQQ, sectors)
3. Key stocks / themes

Rules:
- Keep it SHORT
- Only IMPORTANT info
- Bloomberg terminal style
- No emojis

Market Data:
{market_text}

News:
{news_text}

Output format EXACTLY like:

🟫 TEA // DAILY RECAP
DATE: {datetime.now().strftime("%Y-%m-%d")}
MODE: ...

━━━━━━━━━━━━━━━━━━━
MACRO / GEO
...

━━━━━━━━━━━━━━━━━━━
MARKET
...

━━━━━━━━━━━━━━━━━━━
KEY MOVES
...
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
    )

    return response.choices[0].message.content


# 📤 DISCORD
def send_discord(message):
    data = {"content": f"```{message}```"}
    requests.post(DISCORD_WEBHOOK_URL, json=data)


# 🚀 MAIN
def main():
    headlines = fetch_news()
    market_data = fetch_market_data()

    recap = generate_recap(headlines, market_data)
    send_discord(recap)


if __name__ == "__main__":
    main()
