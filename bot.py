import requests
import os
from datetime import datetime, timedelta
from openai import OpenAI
import pandas as pd
import time

POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

# =========================
# 🔁 SAFE REQUEST
# =========================
def safe_request(url, retries=3):
    for i in range(retries):
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                return r.json()
        except:
            time.sleep(1)
    return None


# =========================
# 📰 NEWS
# =========================
def fetch_news():
    try:
        url = "https://feeds.finance.yahoo.com/rss/2.0/headline?s=spy,qqq,aapl,msft,nvda,tsla&region=US&lang=en-US"
        text = requests.get(url, timeout=10).text

        headlines = []
        for p in text.split("<title>")[2:12]:
            title = p.split("</title>")[0]
            if len(title) > 20:
                headlines.append(title)

        return headlines
    except:
        return ["Aucune nouvelle majeure disponible"]


# =========================
# 📊 POLYGON CLOSE
# =========================
def get_polygon_close(ticker, date):
    url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/{date}/{date}?adjusted=true&apiKey={POLYGON_API_KEY}"
    data = safe_request(url)

    try:
        return data["results"][0]["c"]
    except:
        return None


# =========================
# 📊 FALLBACK YAHOO
# =========================
def get_yahoo_change(ticker):
    try:
        url = f"https://query1.finance.yahoo.com/v7/finance/quote?symbols={ticker}"
        r = requests.get(url, timeout=10).json()
        q = r["quoteResponse"]["result"][0]

        price = q["regularMarketPrice"]
        prev = q["regularMarketPreviousClose"]

        return round((price - prev) / prev * 100, 2)
    except:
        return 0


# =========================
# 📊 CHANGE (POLYGON + FALLBACK)
# =========================
def get_change(ticker):
    try:
        today = datetime.now().date()
        d1 = today - timedelta(days=1)
        d2 = today - timedelta(days=2)

        c1 = get_polygon_close(ticker, d1)
        c2 = get_polygon_close(ticker, d2)

        if c1 and c2:
            return round((c1 - c2) / c2 * 100, 2)

        # fallback
        return get_yahoo_change(ticker)

    except:
        return 0


# =========================
# 📊 MARKET
# =========================
def fetch_market():
    tickers = ["SPY", "QQQ", "UVXY", "USO"]
    return {t: get_change(t) for t in tickers}


# =========================
# 📊 BREADTH (OPTIMISÉ)
# =========================
def compute_breadth(tickers):
    above50 = 0
    total = 0

    for t in tickers[:30]:  # 🔥 réduit pour performance
        url = f"https://api.polygon.io/v2/aggs/ticker/{t}/range/1/day/{datetime.now().date()-timedelta(days=200)}/{datetime.now().date()}?apiKey={POLYGON_API_KEY}"
        data = safe_request(url)

        try:
            closes = [x["c"] for x in data["results"]]
            if len(closes) < 50:
                continue

            ema50 = pd.Series(closes).ewm(span=50).mean().iloc[-1]

            if closes[-1] > ema50:
                above50 += 1

            total += 1

        except:
            continue

    if total == 0:
        return 50

    return round(above50 / total * 100, 1)


# =========================
# 📊 SECTORS
# =========================
SECTORS = ["XLK", "XLE", "XLF", "XLV", "XLY", "XLP"]

def sector_rotation():
    data = [(s, get_change(s)) for s in SECTORS]
    df = pd.DataFrame(data, columns=["sector", "perf"])
    return df.sort_values("perf", ascending=False).head(3)


# =========================
# 🧮 SCORE
# =========================
def compute_score(market, breadth):
    score = 5

    if market["SPY"] > 0: score += 1
    if market["QQQ"] > 0: score += 1
    if market["UVXY"] < 0: score += 1
    if breadth > 60: score += 1
    if breadth < 40: score -= 1

    return max(1, min(score, 10))


def regime(score):
    if score >= 7:
        return "RISK-ON"
    elif score <= 4:
        return "RISK-OFF"
    return "NEUTRAL"


# =========================
# 🧠 GPT
# =========================
def generate_recap(news, market, breadth, sectors, score, reg):

    prompt = f"""
Tu es un stratège macro.

Fais un recap court en français style Bloomberg.

Données:
Marché: {market}
Breadth: {breadth}%
Secteurs: {sectors.to_string(index=False)}
News: {news}

Format:

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

    r = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.5,
    )

    return r.choices[0].message.content


# =========================
# 📤 DISCORD
# =========================
def send(msg):
    requests.post(DISCORD_WEBHOOK_URL, json={"content": f"```{msg}```"})


# =========================
# 🚀 MAIN
# =========================
def main():
    try:
        send("🔄 TEA BOT START")

        news = fetch_news()
        market = fetch_market()

        sp500 = pd.read_csv("https://datahub.io/core/s-and-p-500-companies/r/constituents.csv")["Symbol"].tolist()

        breadth = compute_breadth(sp500)
        sectors = sector_rotation()

        score = compute_score(market, breadth)
        reg = regime(score)

        recap = generate_recap(news, market, breadth, sectors, score, reg)

        send(recap)

    except Exception as e:
        send(f"❌ ERREUR:\n{str(e)}")


if __name__ == "__main__":
    main()
