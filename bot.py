import requests
import os
from datetime import datetime, timedelta
from openai import OpenAI
import pandas as pd

POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

# 📰 NEWS
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


# 📊 POLYGON DAILY CLOSE
def get_polygon_close(ticker, date):
    url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/{date}/{date}?adjusted=true&apiKey={POLYGON_API_KEY}"
    try:
        r = requests.get(url).json()
        return r["results"][0]["c"]
    except:
        return None


def get_change(ticker):
    today = datetime.now().date()
    yesterday = today - timedelta(days=1)
    prev = today - timedelta(days=2)

    try:
        close_today = get_polygon_close(ticker, yesterday)
        close_prev = get_polygon_close(ticker, prev)

        if close_today is None or close_prev is None:
            return 0

        change = ((close_today - close_prev) / close_prev) * 100
        return round(change, 2)

    except:
        return 0


# 📊 MARKET DATA
def fetch_market():
    tickers = {
        "SPY": "Market",
        "QQQ": "Tech",
        "UVXY": "Volatility",
        "USO": "Oil",
        "XLE": "Energy",
        "XLK": "TechSector",
        "XLF": "Financials"
    }

    data = {}
    for t in tickers:
        data[t] = get_change(t)

    return data


# 🧮 SCORE
def compute_score(m):
    score = 5

    if m["SPY"] > 0: score += 1
    if m["QQQ"] > 0: score += 1
    if m["UVXY"] < 0: score += 1  # volatilité baisse = positif
    if m["USO"] < 0: score += 1  # pétrole baisse = positif
    if m["XLF"] > 0: score += 1

    return max(1, min(score, 10))


def regime(score):
    if score >= 7:
        return "RISK-ON"
    elif score <= 4:
        return "RISK-OFF"
    return "NEUTRAL"


# 📈 SP500
def fetch_sp500():
    df = pd.read_csv("https://datahub.io/core/s-and-p-500-companies/r/constituents.csv")
    return df["Symbol"].str.replace(".", "-", regex=False).tolist()


def top_movers():
    tickers = fetch_sp500()[:100]  # rapide

    results = []

    for t in tickers:
        change = get_change(t)
        results.append((t, change))

    df = pd.DataFrame(results, columns=["ticker", "change"])
    df = df.sort_values("change", ascending=False)

    return df.head(5), df.tail(5)


# 🧠 GPT
def generate_recap(news, market, score, reg, top, worst):

    news_text = "\n".join(news)
    market_text = "\n".join([f"{k}: {v}%" for k, v in market.items()])
    top_text = "\n".join([f"{r.ticker}: {r.change}%" for _, r in top.iterrows()])
    worst_text = "\n".join([f"{r.ticker}: {r.change}%" for _, r in worst.iterrows()])

    prompt = f"""
Create a SHORT hedge fund style recap.

Tone:
- Bloomberg terminal
- Light but sharp
- No emojis

Market Score: {score}/10
Regime: {reg}

Market Data:
{market_text}

Top Movers:
{top_text}

Worst Movers:
{worst_text}

News:
{news_text}

Format EXACT:

🟫 TEA ELITE // DAILY RECAP
DATE: {datetime.now().strftime("%Y-%m-%d")}
MODE: {reg}
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
