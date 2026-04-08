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
# BREADTH
# -----------------------------
def compute_breadth(tickers, start, end):
    count = 0
    valid = 0

    for t in tickers[:100]:  # rapide
        df = get_data(t, start, end)
        if df is None or len(df) < 50:
            continue

        df = add_indicators(df)
        valid += 1

        if df["c"].iloc[-1] > df["EMA50"].iloc[-1]:
            count += 1

    if valid == 0:
        return 0

    return round((count / valid) * 100, 1)

# -----------------------------
# SNAPSHOT ETF
# -----------------------------
def get_snapshot():
    assets = {
        "SPY": "Equities",
        "USO": "Oil",
        "TLT": "Yields",
        "UUP": "Dollar",
        "GLD": "Gold"
    }

    changes = {}

    end_date = datetime.now() - timedelta(days=1)
    start_date = end_date - timedelta(days=5)

    start = start_date.strftime("%Y-%m-%d")
    end = end_date.strftime("%Y-%m-%d")

    for t, name in assets.items():
        df = get_data(t, start, end)
        if df is None or len(df) < 2:
            changes[name] = "?"
            continue

        ret = (df["c"].iloc[-1] / df["c"].iloc[-2] - 1) * 100
        changes[name] = f"{round(ret,1)}%"

    return changes

# -----------------------------
# MARKET REGIME
# -----------------------------
def regime_text(breadth):
    if breadth > 60:
        return "bullish"
    elif breadth > 40:
        return "neutre"
    else:
        return "faible"

# -----------------------------
# SCAN
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
            results.append((t, score, last["c"]))

    df_res = pd.DataFrame(results, columns=["ticker", "score", "price"])

    if df_res.empty:
        return df_res

    return df_res.sort_values("score", ascending=False).head(10)

# -----------------------------
# REPORT
# -----------------------------
def build_report(df, breadth, snapshot):
    regime = regime_text(breadth)

    report = "🟫 TEA ELITE RECAP\n\n"

    # SNAPSHOT
    report += "🔹 SNAPSHOT\n"
    report += f"Equities {snapshot['Equities']} | Oil {snapshot['Oil']} | Yields {snapshot['Yields']} | Dollar {snapshot['Dollar']} | Gold {snapshot['Gold']}\n\n"

    # MACRO AUTO
    report += "🌍 MACRO\n\n"

    if regime == "bullish":
        report += "Le marché montre une forte résilience et price un scénario favorable.\n\n"
    elif regime == "neutre":
        report += "Le marché reste en équilibre, sans direction claire.\n\n"
    else:
        report += "Le marché montre des signes de faiblesse et prudence.\n\n"

    # FLOW
    report += "⚡ CROSS-ASSET FLOW\n\n"
    report += "Rotation en cours entre actifs selon le contexte macro.\n\n"

    # INTERNALS
    report += "📊 MARKET INTERNALS\n\n"
    report += f"Breadth: {breadth}%\n"
    report += f"Régime: {regime}\n\n"

    # SETUPS
    report += "🎯 TOP SETUPS\n\n"
    for _, row in df.iterrows():
        report += f"{row['ticker']} | Score: {row['score']} | Price: {round(row['price'],2)}\n"

    # TAKEAWAY
    report += "\n🎯 TAKEAWAY TEA\n\n"

    if regime == "bullish":
        report += "Momentum dominant → privilégier les pullbacks.\n"
    elif regime == "neutre":
        report += "Marché indécis → privilégier prudence et sélectivité.\n"
    else:
        report += "Risque élevé → éviter agressivité.\n"

    return report

# -----------------------------
# DISCORD
# -----------------------------
def send_discord(msg):
    requests.post(DISCORD_WEBHOOK_URL, json={"content": msg})

# -----------------------------
# MAIN
# -----------------------------
def main():
    tickers = load_sp500()

    end_date = datetime.now() - timedelta(days=1)
    start_date = end_date - timedelta(days=120)

    start = start_date.strftime("%Y-%m-%d")
    end = end_date.strftime("%Y-%m-%d")

    breadth = compute_breadth(tickers, start, end)
    snapshot = get_snapshot()
    df = scan_market()

    if df.empty:
        message = "⚠️ Aucun setup valide aujourd’hui"
    else:
        message = build_report(df, breadth, snapshot)

    send_discord(message)

if __name__ == "__main__":
    main()
