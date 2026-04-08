import pandas as pd
import requests
import os
from datetime import datetime, timedelta
from openai import OpenAI

# -----------------------------
# KEYS
# -----------------------------
POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

# -----------------------------
# LOAD SP500
# -----------------------------
def load_sp500():
    df = pd.read_csv("https://datahub.io/core/s-and-p-500-companies/r/constituents.csv")
    return df["Symbol"].str.replace(".", "-", regex=False).tolist()

# -----------------------------
# FETCH DATA
# -----------------------------
def get_data(ticker, start, end):
    url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/{start}/{end}?adjusted=true&sort=asc&limit=200&apiKey={POLYGON_API_KEY}"
    try:
        r = requests.get(url, timeout=10)
        data = r.json()

        if "results" not in data:
            return None

        df = pd.DataFrame(data["results"])
        df["Date"] = pd.to_datetime(df["t"], unit="ms")
        df.set_index("Date", inplace=True)

        return df
    except:
        return None

# -----------------------------
# INDICATORS
# -----------------------------
def add_indicators(df):
    df["EMA50"] = df["c"].ewm(span=50).mean()
    return df

# -----------------------------
# BREADTH (interne)
# -----------------------------
def compute_breadth(tickers, start, end):
    count = 0
    valid = 0

    for t in tickers[:100]:
        df = get_data(t, start, end)
        if df is None or len(df) < 50:
            continue

        df = add_indicators(df)
        valid += 1

        if df["c"].iloc[-1] > df["EMA50"].iloc[-1]:
            count += 1

    if valid == 0:
        return 50

    return (count / valid) * 100

# -----------------------------
# SNAPSHOT TEXTE
# -----------------------------
def interpret_snapshot():
    return "Equities mixte | Oil sous pression | Yields stables | Dollar légèrement faible | Gold en soutien"

# -----------------------------
# GPT GENERATION
# -----------------------------
def generate_market_text(snapshot, breadth):

    prompt = f"""
Tu es un analyste macro professionnel avec un style similaire à ZeroHedge.

Écris un recap du marché en français avec ce format EXACT :

🟫 TEA ELITE RECAP

🔹 SNAPSHOT
{snapshot}

🌍 MACRO
Analyse narrative du contexte du marché aujourd’hui

👉 Trois dynamiques dominaient :
- ...
- ...
- ...

Conclusion macro

⚡ CROSS-ASSET FLOW
Analyse du comportement :
- Oil
- Dollar
- Actions
- Gold

Conclusion claire du comportement du marché

📊 MARKET INTERNALS
Analyse interne du marché :
- structure
- leadership
- participation

Conclusion sur la solidité du marché

🎯 TAKEAWAY TEA
2 idées fortes

💡 Traduction :
- ...
- ...

➡️ Conclusion punchy

IMPORTANT :
- Texte fluide, humain, pas robot
- Pas de chiffres techniques
- Style narratif comme un article
- Maximum 250 mots
"""

    try:
        response = client.chat.completions.create(
            model="gpt-5-3-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8
        )

        return response.choices[0].message.content

    except Exception as e:
        print("Erreur GPT:", e)
        return "⚠️ Erreur génération du recap"

# -----------------------------
# DISCORD
# -----------------------------
def send_discord(message):
    try:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": message})
    except:
        print("Erreur Discord")

# -----------------------------
# MAIN
# -----------------------------
def main():

    print("🔄 Génération du recap...")

    tickers = load_sp500()

    end_date = datetime.now() - timedelta(days=1)
    start_date = end_date - timedelta(days=120)

    start = start_date.strftime("%Y-%m-%d")
    end = end_date.strftime("%Y-%m-%d")

    breadth = compute_breadth(tickers, start, end)
    snapshot = interpret_snapshot()

    text = generate_market_text(snapshot, breadth)

    send_discord(text)

    print("✅ Recap envoyé")

if __name__ == "__main__":
    main()
