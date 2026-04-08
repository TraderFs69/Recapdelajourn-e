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

    for t in tickers[:80]:  # rapide + safe
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
# SNAPSHOT TEXTE SIMPLE
# -----------------------------
def interpret_snapshot():
    return "Equities mixtes | Oil stable | Yields stables | Dollar neutre | Gold stable"

# -----------------------------
# GPT GENERATION (RETRY)
# -----------------------------
def generate_text(snapshot, breadth):

    prompt = f"""
Tu es un analyste macro avec un style similaire à ZeroHedge.

Écris un recap en français EXACTEMENT dans ce format :

🟫 TEA ELITE RECAP

🔹 SNAPSHOT
{snapshot}

🌍 MACRO
Analyse narrative

👉 Trois dynamiques dominaient :
- ...
- ...
- ...

Conclusion macro

⚡ CROSS-ASSET FLOW
Analyse narrative

📊 MARKET INTERNALS
Analyse narrative

🎯 TAKEAWAY TEA

💡 Traduction :
- ...
- ...

➡️ Conclusion punchy

IMPORTANT :
- Style humain
- Pas robot
- Pas de chiffres
- 150-250 mots
"""

    for i in range(3):  # retry x3
        try:
            response = client.responses.create(
                model="gpt-5-3-instant",
                input=prompt
            )

            text = response.output_text

            if text and len(text) > 100:
                return text

        except Exception as e:
            print(f"Erreur GPT tentative {i+1}:", e)
            time.sleep(2)

    # 🔥 FALLBACK SI GPT FAIL
    return fallback_text(snapshot, breadth)

# -----------------------------
# FALLBACK TEXTE
# -----------------------------
def fallback_text(snapshot, breadth):

    base = "🟫 TEA ELITE RECAP\n\n"
    base += "🔹 SNAPSHOT\n" + snapshot + "\n\n"

    base += "🌍 MACRO\n\n"

    if breadth > 60:
        base += "Le marché reste solide avec une participation large.\n\n"
    elif breadth > 40:
        base += "Le marché évolue sans direction claire.\n\n"
    else:
        base += "Le marché montre des signes de prudence.\n\n"

    base += "⚡ CROSS-ASSET FLOW\n\nRotation entre actifs.\n\n"

    base += "📊 MARKET INTERNALS\n\nStructure fragile.\n\n"

    base += "🎯 TAKEAWAY TEA\n\n"
    base += "Marché incertain → prudence.\n"

    return base

# -----------------------------
# DISCORD SAFE
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

    if not text or len(text) < 50:
        text = fallback_text(snapshot, breadth)

    send_discord(text)

    print("✅ DONE")

if __name__ == "__main__":
    main()
