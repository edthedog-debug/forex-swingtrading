import json
from datetime import datetime
import yfinance as yf

# Fetch EUR/USD data from Yahoo Finance (Extended period for deep backtesting)
ticker = "EURUSD=X"
data = yf.download(ticker, period="120d", interval="1d", progress=False)

if data.empty:
    print("Error: Could not fetch data from Yahoo Finance.")
    exit(1)

# Flatten columns if multi-index
if hasattr(data.columns, "levels"):
    data.columns = data.columns.get_level_values(0)

dates = data.index.strftime("%Y-%m-%d").tolist()
closes = [float(c) for c in data["Close"].tolist()]

# Technical Calculations (Optimized: 20-period for Bollinger, 14 for RSI)
period_bb = 20
period_rsi = 14

slice_bb = closes[-period_bb:]
sma = sum(slice_bb) / period_bb
variance = sum((x - sma) ** 2 for x in slice_bb) / period_bb
st_dev = variance ** 0.5

upper_band = round(sma + (2 * st_dev), 4)
lower_band = round(sma - (2 * st_dev), 4)
current_price = closes[-1]

# RSI Calculation function for dynamic historical accuracy
def calculate_rsi(prices, periods):
    if len(prices) < periods + 1:
        return 50.0
    gains = []
    losses = []
    for i in range(len(prices) - periods, len(prices)):
        change = prices[i] - prices[i - 1]
        if change > 0:
            gains.append(change)
        else:
            losses.append(abs(change))
    
    avg_gain = sum(gains) / periods
    avg_loss = sum(losses) / periods
    
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 1)

rsi = calculate_rsi(closes, period_rsi)

# --- PROBABILISTIC ASYMMETRIC RISK/REWARD LOGIC ---
# Strategy: High-probability mean reversion with a 1:1.5 Risk-to-Reward ratio
risk_multiplier = 1.0 # Risk 1 Standard Deviation (Cut losses quickly)
reward_multiplier = 1.5 # Target 1.5 Standard Deviations (Let profits run)

signal = "NEUTRAL (WAIT)"
stop_loss = None
take_profit = None

# Entry logic requires BOTH Bollinger breakout and RSI extreme
if current_price <= lower_band and rsi < 35:
    signal = "STRONG BUY"
    stop_loss = round(current_price - (st_dev * risk_multiplier), 4)
    take_profit = round(current_price + (st_dev * reward_multiplier), 4)
elif current_price >= upper_band and rsi > 65:
    signal = "STRONG SELL"
    stop_loss = round(current_price + (st_dev * risk_multiplier), 4)
    take_profit = round(current_price - (st_dev * reward_multiplier), 4)
else:
    # Default safety boundaries when neutral for display purposes
    stop_loss = round(current_price - (st_dev * risk_multiplier), 4)
    take_profit = round(current_price + (st_dev * reward_multiplier), 4)

# --- REALISTIC PROBABILISTIC BACKTESTING MODULE ---
initial_capital = 10000.0
capital = initial_capital
position = 0  
entry_hist_price = 0.0
entry_date = ""
active_sl = 0.0
active_tp = 0.0
trades = []

for i in range(period_bb, len(closes)):
    # Historical context
    h_slice = closes[i - period_bb : i]
    h_sma = sum(h_slice) / period_bb
    h_var = sum((x - h_sma) ** 2 for x in h_slice) / period_bb
    h_std = h_var ** 0.5
    h_upper = h_sma + (2 * h_std)
    h_lower = h_sma - (2 * h_std)
    p_close = closes[i]
    
    h_rsi = calculate_rsi(closes[:i+1], period_rsi)

    # STRICT ENTRY
    if position == 0:
        if p_close <= h_lower and h_rsi < 35:
            position = 1
            entry_hist_price = p_close
            entry_date = dates[i]
            # Set fixed Stop Loss and Take Profit at entry
            active_sl = p_close - (h_std * risk_multiplier)
            active_tp = p_close + (h_std * reward_multiplier)
            
        elif p_close >= h_upper and h_rsi > 65:
            position = -1
            entry_hist_price = p_close
            entry_date = dates[i]
            # Set fixed Stop Loss and Take Profit at entry (inverted for short)
            active_sl = p_close + (h_std * risk_multiplier)
            active_tp = p_close - (h_std * reward_multiplier)
    
    # REALISTIC EXITS (Hits Stop Loss OR Take Profit)
    elif position == 1: # LONG POSITION
        if p_close <= active_sl or p_close >= active_tp:
            profit = (p_close - entry_hist_price) * 10000
            capital += profit
            trades.append({
                "entry": entry_date,
                "exit": dates[i],
                "type": "BUY",
                "entryPrice": round(entry_hist_price, 4),
                "exitPrice": round(p_close, 4),
                "profit": round(profit, 2)
            })
            position = 0

    elif position == -1: # SHORT POSITION
        if p_close >= active_sl or p_close <= active_tp:
            profit = (entry_hist_price - p_close) * 10000
            capital += profit
            trades.append({
                "entry": entry_date,
                "exit": dates[i],
                "type": "SELL",
                "entryPrice": round(entry_hist_price, 4),
                "exitPrice": round(p_close, 4),
                "profit": round(profit, 2)
            })
            position = 0

# Calculate real probabilistic metrics
winning_trades = [t for t in trades if t["profit"] > 0]
win_rate = round((len(winning_trades) / len(trades)) * 100, 1) if trades else 0.0
total_return = round(((capital - initial_capital) / initial_capital) * 100, 2)

output = {
    "lastUpdate": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
    "currentPrice": round(current_price, 4),
    "dates": dates[-60:], # Return only 60 days to keep UI fast
    "prices": closes[-60:],
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
        "trades": trades[-5:] # Show last 5 trades
    }
}

with open("data.json", "w") as f:
    json.dump(output, f, indent=4)

print("Successfully generated data.json with probabilistic risk management.")
