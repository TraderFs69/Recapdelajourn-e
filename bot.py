import requests
import os
from datetime import datetime, timedelta
from openai import OpenAI
import pandas as pd
import numpy as np

POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

# 📰 NEWS
def fetch_news():
    url = "https://feeds.finance.yahoo.com/rss/2.0/headline?s=spy,qqq,aapl,msft,nvda,tsla&region=US&lang=en-US"
    r = requests.get(url).text

    headlines = []
    for p in r.split("<title>")[2:15]:
        title = p.split("</title>")[0]
        if len(title) > 20:
            headlines.append(title)

    return headlines


# 📊 POLYGON DATA
def get_closes(ticker, days=250):
    end = datetime.now().date()
    start = end - timedelta(days=days)

    url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/{start}/{end}?adjusted=true&limit=5000&apiKey={POLYGON_API_KEY}"

    try:
        r = requests.get(url).json()
        closes = [x["c"] for x in r["results"]]
        return closes
    except:
        return []


# 📊 EMA
def ema(data, period):
    return pd.Series(data).ewm(span=period).mean().iloc[-1]


# 📊 BREADTH
def compute_breadth(tickers):
    above_50 = 0
    above_200 = 0
    total = 0

    for t in tickers[:80]:  # limite pour vitesse
        closes = get_closes(t)
        if len(closes) < 200:
            continue

        last = closes[-1]
        ema50 = ema(closes, 50)
        ema200 = ema(closes, 200)

        if last > ema50:
            above_50 += 1
        if last > ema200:
            above_200 += 1

        total += 1

    if total == 0:
        return 0, 0

    return round(above_50 / total * 100, 1), round(above_200 / total * 100, 1)


# 📊 SECTORS
SECTORS = {
    "XLK": "Tech",
    "XLE": "Énergie",
    "XLF": "Finance",
    "XLV": "Santé",
    "XLY": "Conso discrétionnaire",
    "XLP": "Conso de base"
}


def get_change(ticker):
    today = datetime.now().date()
    yesterday = today - timedelta(days=1)
    prev = today - timedelta(days=2)

    try:
        c1 = get_polygon_close(ticker, yesterday)
        c2 = get_polygon_close(ticker, prev)

        if c1 is None or c2 is None:
            return 0

        return round((c1 - c2) / c2 * 100, 2)

    except:
        return 0


def get_polygon_close(ticker, date):
    url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/{date}/{date}?adjusted=true&apiKey={POLYGON_API_KEY}"
    try:
        r = requests.get(url).json()
        return r["results"][0]["c"]
    except:
        return None


def sector_rotation():
    scores = []

    for t, name in SECTORS.items():
        change = get_change(t)
        scores.append((name, t, change))

    df = pd.DataFrame(scores, columns=["sector", "etf", "score"])
    df = df.sort_values("score", ascending=False)

    return df.head(3)


# 📊 MARKET CORE
def fetch_market():
    return {
        "SPY": get_change("SPY"),
        "QQQ": get_change("QQQ"),
        "UVXY": get_change("UVXY"),
        "USO": get_change("USO")
    }


# 🧮 SCORE
def compute_score(m, breadth50):
    score = 5

    if m["SPY"] > 0: score += 1
    if m["QQQ"] > 0: score += 1
    if m["UVXY"] < 0: score += 1
    if breadth50 > 60: score += 1
    if breadth50 < 40: score -= 1

    return max(1, min(score, 10))


def regime(score):
    if score >= 7:
        return "RISK-ON"
    elif score <= 4:
        return "RISK-OFF"
    return "NEUTRAL"


# 🧠 GPT (FRANÇAIS)
def generate_recap(news, market, breadth50, breadth200, sectors, score, reg):

    prompt = f"""
Tu es un stratège macro style Liz Ann Sonders avec un ton léger.

Fais un recap de marché COURT en français.

Structure:
1. Macro & géopolitique (priorité)
2. Marché (indices + breadth)
3. Rotation sectorielle

Données:
Marché: {market}
Breadth EMA50: {breadth50}%
Breadth EMA200: {breadth200}%

Secteurs dominants:
{sectors.to_string(index=False)}

News:
{news}

Format EXACT:

🟫 TEA ELITE // DAILY RECAP
DATE: {datetime.now().strftime("%Y-%m-%d")}
MODE: {reg}
SCORE: {score}/10

━━━━━━━━━━━━━━━━━━━
MACRO / GÉO
...

━━━━━━━━━━━━━━━━━━━
MARCHÉ
...

━━━━━━━━━━━━━━━━━━━
ROTATION
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

    sp500 = pd.read_csv("https://datahub.io/core/s-and-p-500-companies/r/constituents.csv")["Symbol"].tolist()

    breadth50, breadth200 = compute_breadth(sp500)
    sectors = sector_rotation()

    score = compute_score(market, breadth50)
    reg = regime(score)

    recap = generate_recap(news, market, breadth50, breadth200, sectors, score, reg)

    send_discord(recap)


if __name__ == "__main__":
    main()
