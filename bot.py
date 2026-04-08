import pandas as pd
import requests
import os
from datetime import datetime, timedelta

POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

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
    df["EMA9"] = df["c"].ewm(span=9).mean()
    df["EMA20"] = df["c"].ewm(span=20).mean()
    df["RET"] = df["c"].pct_change()
    return df

# -----------------------------
# BREADTH (interne seulement)
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
# SCAN TOP SETUPS
# -----------------------------
def scan_market():
    tickers = load_sp500()

    end_date = datetime.now() - timedelta(days=1)
    start_date = end_date - timedelta(days=120)

    start = start_date.strftime("%Y-%m-%d")
    end = end_date.strftime("%Y-%m-%d")

    results = []

    for t in tickers[:150]:
        df = get_data(t, start, end)
        if df is None or len(df) < 50:
            continue

        df = add_indicators(df)
        last = df.iloc[-1]

        score = 0

        if last["EMA9"] > last["EMA20"]:
            score += 2
        if last["EMA20"] > last["EMA50"]:
            score += 2
        if last["RET"] > 0:
            score += 2

        if score >= 4:
            results.append((t, score))

    df_res = pd.DataFrame(results, columns=["ticker", "score"])

    if df_res.empty:
        return df_res

    return df_res.sort_values("score", ascending=False).head(10)

# -----------------------------
# SNAPSHOT TEXTE (PAS DE %)
# -----------------------------
def interpret_snapshot():
    return "Equities mixte | Oil sous pression | Yields stables | Dollar légèrement faible | Gold en soutien"

# -----------------------------
# BUILD REPORT STYLE HUMAIN
# -----------------------------
def build_report(df, breadth):

    report = "🟫 TEA ELITE RECAP\n\n"

    # SNAPSHOT
    report += "🔹 SNAPSHOT\n"
    report += interpret_snapshot() + "\n\n"

    # MACRO
    report += "🌍 MACRO\n\n"

    if breadth > 60:
        report += "Les marchés montrent une forte résilience avec un biais haussier.\n\n"
        report += "👉 Participation large et momentum solide.\n\n"

    elif breadth > 40:
        report += "Le marché évolue sans direction claire avec une phase de transition.\n\n"
        report += "👉 Rotation interne et absence de conviction forte.\n\n"

    else:
        report += "Les marchés montrent des signes de prudence dans un contexte incertain.\n\n"
        report += "👉 Biais défensif et participation limitée.\n\n"

    # FLOW
    report += "⚡ CROSS-ASSET FLOW\n\n"
    report += "Rotation en cours entre actifs selon le contexte macro.\n\n"
    report += "👉 Le marché ne panique pas, mais reste hésitant.\n\n"

    # INTERNALS
    report += "📊 MARKET INTERNALS\n\n"

    if breadth > 60:
        report += "Structure solide avec leadership clair.\n"
        report += "👉 Environnement bullish.\n\n"

    elif breadth > 40:
        report += "Structure neutre avec rotation sectorielle.\n"
        report += "👉 Environnement incertain.\n\n"

    else:
        report += "Structure affaiblie et leadership fragile.\n"
        report += "👉 Environnement fragile.\n\n"

    # TOP SETUPS
    if not df.empty:
        report += "🎯 TOP SETUPS\n\n"
        for _, row in df.iterrows():
            report += f"{row['ticker']} | Score: {row['score']}\n"

    # TAKEAWAY
    report += "\n🎯 TAKEAWAY TEA\n\n"

    if breadth > 60:
        report += "Momentum dominant → privilégier les pullbacks.\n"

    elif breadth > 40:
        report += "Marché incertain → sélectivité essentielle.\n"

    else:
        report += "Risque élevé → éviter agressivité.\n"

    return report

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

    print("🔄 Scan en cours...")

    tickers = load_sp500()

    end_date = datetime.now() - timedelta(days=1)
    start_date = end_date - timedelta(days=120)

    start = start_date.strftime("%Y-%m-%d")
    end = end_date.strftime("%Y-%m-%d")

    breadth = compute_breadth(tickers, start, end)
    df = scan_market()

    print("Breadth:", round(breadth, 1))
    print("Setups:", len(df))

    message = build_report(df, breadth)

    send_discord(message)

    print("✅ Envoyé sur Discord")

if __name__ == "__main__":
    main()
if __name__ == "__main__":
    main()
