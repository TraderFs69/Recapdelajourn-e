import requests
import os
from datetime import datetime
from openai import OpenAI
import pandas as pd

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

# 📰 NEWS (Yahoo RSS)
def fetch_news():
    url = "https://feeds.finance.yahoo.com/rss/2.0/headline?s=spy,qqq,aapl,msft,nvda,tsla&region=US&lang=en-US"
    r = requests.get(url).text

    headlines = []
    parts = r.split("<title>")

    for p in parts[2:15]:
        title = p.split("</title>")[0]
        if len(title) > 20:
            headlines.append(title)

    return headlines


# 📊 MARKET DATA
def get_quote(ticker):
    try:
        url = f"https://query1.finance.yahoo.com/v7/finance/quote?symbols={ticker}"
        r = requests.get(url).json()
        q = r["quoteResponse"]["result"][0]
        return round(q.get("regularMarketChangePercent", 0), 2)
    except:
        return 0


def fetch_market():
    tickers = {
        "SPY": "Market",
        "QQQ": "Tech",
        "VIX": "Volatility",
        "^TNX": "Rates",
        "CL=F": "Oil",
        "XLE": "Energy",
        "XLK": "TechSector",
        "XLF": "Financials"
    }

    data = {}
    for t in tickers:
        data[t] = get_quote(t)

    return data


# 🧮 MARKET SCORE
def compute_score(market):
    score = 5

    if market["SPY"] > 0: score += 1
    if market["QQQ"] > 0: score += 1
    if market["VIX"] < 0: score += 1
    if market["^TNX"] < 0: score += 1
    if market["CL=F"] < 0: score += 1

    return max(1, min(score, 10))


def regime(score):
    if score >= 7:
        return "RISK-ON"
    elif score <= 4:
        return "RISK-OFF"
    return "NEUTRAL"


# 📈 TOP MOVERS (S&P500 sample)
def fetch_sp500():
    df = pd.read_csv("https://datahub.io/core/s-and-p-500-companies/r/constituents.csv")
    return df["Symbol"].tolist()[:100]  # pour vitesse


def top_movers():
    tickers = fetch_sp500()
    results = []

    for t in tickers:
        change = get_quote(t)
        results.append((t, change))

    df = pd.DataFrame(results, columns=["ticker", "change"])
    df = df.sort_values("change", ascending=False)

    return df.head(5), df.tail(5)


# 🧠 GPT ANALYSIS
def generate_recap(news, market, score, regime, top, worst):

    news_text = "\n".join(news)
    market_text = "\n".join([f"{k}: {v}%" for k, v in market.items()])

    top_text = "\n".join([f"{r.ticker}: {r.change}%" for _, r in top.iterrows()])
    worst_text = "\n".join([f"{r.ticker}: {r.change}%" for _, r in worst.iterrows()])

    prompt = f"""
Create a SHORT hedge fund style market recap.

Tone:
- Like Liz Ann Sonders + Bloomberg terminal
- Light but sharp
- No emojis

Structure:
1. Macro & Geopolitics (priority)
2. Market behavior (use data)
3. Key stocks / sectors

Market Score: {score}/10
Regime: {regime}

Market Data:
{market_text}

Top Movers:
{top_text}

Worst Movers:
{worst_text}

News:
{news_text}

Format EXACTLY:

🟫 TEA ELITE // DAILY RECAP
DATE: {datetime.now().strftime("%Y-%m-%d")}
MODE: {regime}
SCORE: {score}/10

━━━━━━━━━━━━━━━━━━━
MACRO / GEO
...

━━━━━━━━━━━━━━━━━━━
MARKET
...

━━━━━━━━━━━━━━━━━━━
FLOW / LEADERS
...
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.6,
    )

    return response.choices[0].message.content


# 📤 DISCORD
def send_discord(msg):
    requests.post(DISCORD_WEBHOOK_URL, json={"content": f"```{msg}```"})


# 🚀 MAIN
def main():
    news = fetch_news()
    market = fetch_market()
    score = compute_score(market)
    reg = regime(score)

    top, worst = top_movers()

    recap = generate_recap(news, market, score, reg, top, worst)
    send_discord(recap)


if __name__ == "__main__":
    main()
