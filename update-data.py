import json
from datetime import datetime
import yfinance as yf

# Fetch EUR/USD data from Yahoo Finance
ticker = "EURUSD=X"
data = yf.download(ticker, period="60d", interval="1d", progress=False)

if data.empty:
    print("Error: Could not fetch data from Yahoo Finance.")
    exit(1)

# Flatten columns if multi-index (yfinance update behavior)
if hasattr(data.columns, "levels"):
    data.columns = data.columns.get_level_values(0)

dates = data.index.strftime("%Y-%m-%d").tolist()
closes = data["Close"].tolist()

# Ensure standard Python floats
closes = [float(c) for c in closes]

# Simple Technical Calculations (SMA, Bollinger Bands, RSI)
period = 14
slice_prices = closes[-period:]
sma = sum(slice_prices) / period
variance = sum((x - sma) ** 2 for x in slice_prices) / period
st_dev = variance ** 0.5

upper_band = round(sma + (2 * st_dev), 4)
lower_band = round(sma - (2 * st_dev), 4)
current_price = closes[-1]

# Simple RSI approximation
gains = [
    closes[i] - closes[i - 1]
    for i in range(len(closes) - period, len(closes))
    if closes[i] > closes[i - 1]
]
losses = [
    closes[i - 1] - closes[i]
    for i in range(len(closes) - period, len(closes))
    if closes[i] < closes[i - 1]
]
avg_gain = sum(gains) / period if gains else 0
avg_loss = sum(losses) / period if losses else 0
rs = avg_gain / avg_loss if avg_loss > 0 else 100
rsi = round(100 - (100 / (1 + rs)), 1)

# Signal Logic
signal = "NEUTRAL"
if current_price <= lower_band or rsi < 42:
    signal = "BUY (LONG)"
elif current_price >= upper_band or rsi > 60:
    signal = "SELL (SHORT)"

output = {
    "lastUpdate": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
    "currentPrice": round(current_price, 4),
    "dates": dates,
    "prices": closes,
    "upperBand": upper_band,
    "lowerBand": lower_band,
    "sma": round(sma, 4),
    "rsi": rsi,
    "signal": signal,
}

with open("data.json", "w") as f:
    json.dump(output, f, indent=4)

print("Successfully generated data.json from Yahoo Finance.")
