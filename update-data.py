import json
from datetime import datetime
import yfinance as yf

# Fetch EUR/USD data from Yahoo Finance
ticker = "EURUSD=X"
data = yf.download(ticker, period="60d", interval="1d", progress=False)

if data.empty:
    print("Error: Could not fetch data from Yahoo Finance.")
    exit(1)

# Flatten columns if multi-index
if hasattr(data.columns, "levels"):
    data.columns = data.columns.get_level_values(0)

dates = data.index.strftime("%Y-%m-%d").tolist()
closes = [float(c) for c in data["Close"].tolist()]

# Technical Calculations & Momentum Filters
period = 14
slice_prices = closes[-period:]
sma = sum(slice_prices) / period
variance = sum((x - sma) ** 2 for x in slice_prices) / period
st_dev = variance ** 0.5

upper_band = round(sma + (2 * st_dev), 4)
lower_band = round(sma - (2 * st_dev), 4)
current_price = closes[-1]

# Short-term Momentum (Fast vs Slow EMA approximation via slices)
ema_fast = sum(closes[-5:]) / 5
ema_slow = sum(closes[-10:]) / 10

# RSI Calculation
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

# Optimized Risk Management (Tight Stop Loss & High Probability Take Profit)
sl_multiplier = 0.8  # Stop loss más ajustado para cortar pérdidas al instante
tp_multiplier = 1.2  # Take profit optimizado para asegurar cierres ganadores rápidos

signal = "NEUTRAL"
stop_loss = None
take_profit = None

# High-Precision Filters for Maximum Winning Trades
if (ema_fast > ema_slow and rsi > 45 and rsi < 65) or current_price <= lower_band:
    signal = "BUY (LONG)"
    stop_loss = round(current_price - (st_dev * sl_multiplier), 4)
    take_profit = round(current_price + (st_dev * tp_multiplier), 4)
elif (ema_fast < ema_slow and rsi < 55 and rsi > 35) or current_price >= upper_band:
    signal = "SELL (SHORT)"
    stop_loss = round(current_price + (st_dev * sl_multiplier), 4)
    take_profit = round(current_price - (st_dev * tp_multiplier), 4)
else:
    stop_loss = round(current_price - (st_dev * sl_multiplier), 4)
    take_profit = round(current_price + (st_dev * tp_multiplier), 4)

# --- ADVANCED BACKTESTING MODULE (Optimized for High Win Rate) ---
initial_capital = 10000.0
capital = initial_capital
position = 0  
entry_hist_price = 0.0
entry_date = ""
trades = []

for i in range(period, len(closes)):
    hist_slice = closes[i - period : i]
    h_sma = sum(hist_slice) / period
    h_var = sum((x - h_sma) ** 2 for x in hist_slice) / period
    h_std = h_var ** 0.5
    h_upper = h_sma + (2 * h_std)
    h_lower = h_sma - (2 * h_std)
    p_close = closes[i]
    
    h_ema_fast = sum(closes[i-5:i]) / 5
    h_ema_slow = sum(closes[i-10:i]) / 10

    h_gains = [
        closes[j] - closes[j - 1]
        for j in range(i - period, i)
        if closes[j] > closes[j - 1]
    ]
    h_losses = [
        closes[j - 1] - closes[j]
        for j in range(i - period, i)
        if closes[j] < closes[j - 1]
    ]
    h_ag = sum(h_gains) / period if h_gains else 0
    h_al = sum(h_losses) / period if h_losses else 0
    h_rs = h_ag / h_al if h_al > 0 else 100
    h_rsi = 100 - (100 / (1 + h_rs))

    if position == 0:
        if (h_ema_fast > h_ema_slow and 45 < h_rsi < 65) or p_close <= h_lower:
            position = 1
            entry_hist_price = p_close
            entry_date = dates[i]
        elif (h_ema_fast < h_ema_slow and 35 < h_rsi < 55) or p_close >= h_upper:
            position = -1
            entry_hist_price = p_close
            entry_date = dates[i]
    elif position == 1:
        # Check Take Profit or tight Stop Loss for immediate filtering of winning trades
        if p_close >= entry_hist_price + (h_std * tp_multiplier) or p_close <= entry_hist_price - (h_std * sl_multiplier):
            profit = (p_close - entry_hist_price) * 10000
            capital += profit
            trades.append(
                {
                    "entry": entry_date,
                    "exit": dates[i],
                    "type": "BUY",
                    "entryPrice": round(entry_hist_price, 4),
                    "exitPrice": round(p_close, 4),
                    "profit": round(profit, 2),
                }
            )
            position = 0
    elif position == -1:
        if p_close <= entry_hist_price - (h_std * tp_multiplier) or p_close >= entry_hist_price + (h_std * sl_multiplier):
            profit = (entry_hist_price - p_close) * 10000
            capital += profit
            trades.append(
                {
                    "entry": entry_date,
                    "exit": dates[i],
                    "type": "SELL",
                    "entryPrice": round(entry_hist_price, 4),
                    "exitPrice": round(p_close, 4),
                    "profit": round(profit, 2),
                }
            )
            position = 0

winning_trades = [t for t in trades if t["profit"] > 0]
win_rate = (
    round((len(winning_trades) / len(trades)) * 100, 1) if trades else 0.0
)
total_return = round(((capital - initial_capital) / initial_capital) * 100, 2)

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
    "stopLoss": stop_loss,
    "takeProfit": take_profit,
    "backtest": {
        "initialCapital": initial_capital,
        "finalCapital": round(capital, 2),
        "totalReturn": total_return,
        "winRate": win_rate,
        "trades": trades[-5:],
    },
}

with open("data.json", "w") as f:
    json.dump(output, f, indent=4)

print("Successfully generated data.json with high-winrate momentum strategy.")
