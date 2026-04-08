import pandas as pd
import requests
import os
import time
from datetime import datetime, timedelta
from openai import OpenAI

# -----------------------------
# CONFIG
# -----------------------------
POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
client = OpenAI()

# -----------------------------
# LOAD SP500
# -----------------------------
def load_sp500():
    try:
        df = pd.read_csv("https://datahub.io/core/s-and-p-500-companies/r/constituents.csv")
        return df["Symbol"].str.replace(".", "-", regex=False).tolist()
    except:
        return []

# -----------------------------
# FETCH DATA SAFE
# -----------------------------
def get_data(ticker, start, end):
    url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/{start}/{end}?adjusted=true&sort=asc&limit=200&apiKey={POLYGON_API_KEY}"
    try:
        r = requests.get(url, timeout=8)
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
# BREADTH SAFE
# -----------------------------
def compute_breadth(tickers, start, end):
    count, valid = 0, 0

    for t in tickers[:80]:
        df = get_data(t, start, end)
        if df is None or len(df) < 50:
            continue

        df["EMA50"] = df["c"].ewm(span=50).mean()
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
    return "Equities mixtes | Oil stable | Yields stables | Dollar neutre | Gold stable"

# -----------------------------
# GPT GENERATION (MEDIA STYLE)
# -----------------------------
def generate_text(snapshot, breadth):

    prompt = f"""
Tu es un journaliste financier professionnel (style ZeroHedge / Bloomberg).

Écris un recap du marché en français.

STYLE :
- narratif
- humain
- intelligent
- jamais robotique

FORMAT EXACT :

🟫 TEA ELITE RECAP

🧠 HEADLINE
Une phrase forte et crédible style média

🔹 SNAPSHOT
{snapshot}

🌍 MACRO

Analyse du marché aujourd’hui

👉 Trois dynamiques dominaient :
- ...
- ...
- ...

Explique ce que le marché price

⚡ CROSS-ASSET FLOW

Analyse :
- pétrole
- dollar
- actions
- or

Ce que ça signifie

📊 MARKET INTERNALS

Analyse :
- structure
- leadership
- participation

Conclusion claire

🎯 TAKEAWAY TEA

👉 idée forte
👉 idée forte

💡 Traduction :

- ...
- ...

➡️ conclusion punchy

IMPORTANT :
- 200 à 300 mots
- PAS générique
- PAS robot
"""

    for i in range(3):
        try:
            response = client.responses.create(
                model="gpt-5-3",
                input=prompt,
                temperature=0.9
            )

            text = response.output_text

            if text and len(text) > 200:
                return text

        except Exception as e:
            print(f"Erreur GPT tentative {i+1}:", e)
            time.sleep(2)

    return None

# -----------------------------
# FALLBACK (QUALITÉ OK)
# -----------------------------
def fallback_text(snapshot, breadth):

    return f"""🟫 TEA ELITE RECAP

🧠 HEADLINE
Marché en attente alors que le manque de conviction domine

🔹 SNAPSHOT
{snapshot}

🌍 MACRO

Les marchés ont évolué sans direction claire, tiraillés entre prudence et absence de catalyseur.

👉 Trois dynamiques dominaient :

- Attentisme
- Rotation défensive
- Faible conviction

Le marché semble en transition.

⚡ CROSS-ASSET FLOW

Les flux restent mitigés sans signal clair.

👉 Le marché observe plus qu’il n’agit.

📊 MARKET INTERNALS

Structure fragile avec participation limitée.

👉 Leadership incertain.

🎯 TAKEAWAY TEA

👉 Le marché attend
👉 Momentum faible

💡 Traduction :

- Breakouts peu fiables
- Risque de faux signaux

➡️ Environnement piégeux
"""

# -----------------------------
# DISCORD
# -----------------------------
def send_discord(msg):
    try:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": msg}, timeout=5)
    except:
        print("Erreur Discord")

# -----------------------------
# MAIN
# -----------------------------
def main():

    print("🚀 START BOT")

    tickers = load_sp500()

    end_date = datetime.now() - timedelta(days=1)
    start_date = end_date - timedelta(days=120)

    start = start_date.strftime("%Y-%m-%d")
    end = end_date.strftime("%Y-%m-%d")

    breadth = compute_breadth(tickers, start, end)
    snapshot = interpret_snapshot()

    print("Breadth:", round(breadth,1))

    text = generate_text(snapshot, breadth)

    if not text:
        print("⚠️ GPT FAIL → fallback")
        text = fallback_text(snapshot, breadth)

    send_discord(text)

    print("✅ DONE")

if __name__ == "__main__":
    main()
