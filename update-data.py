import json
from datetime import datetime
import yfinance as yf

# Fetch EUR/USD data (2 years of data required to calculate the 200 SMA context filter)
ticker = "EURUSD=X"
data = yf.download(ticker, period="2y", interval="1d", progress=False)

if data.empty:
    print("Error: Could not fetch data from Yahoo Finance.")
    exit(1)

# Flatten columns if multi-index
if hasattr(data.columns, "levels"):
    data.columns = data.columns.get_level_values(0)

dates = data.index.strftime("%Y-%m-%d").tolist()
closes = [float(c) for c in data["Close"].tolist()]

# Technical Parameters
period_bb = 20
period_rsi = 14
period_sma200 = 200

if len(closes) < period_sma200:
    print("Not enough data for SMA 200")
    exit(1)

# Current Indicators (20-period for Bollinger, 200 for Macro Trend)
slice_bb = closes[-period_bb:]
sma20 = sum(slice_bb) / period_bb
variance = sum((x - sma20) ** 2 for x in slice_bb) / period_bb
st_dev = variance ** 0.5

upper_band = round(sma20 + (2 * st_dev), 4)
lower_band = round(sma20 - (2 * st_dev), 4)
current_price = closes[-1]
sma200 = sum(closes[-period_sma200:]) / period_sma200

# RSI Calculation function
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

# --- INSTITUTIONAL FILTERING LOGIC ---
signal = "NEUTRAL (WAIT)"
stop_loss = None
take_profit = None

risk_multiplier = 1.0
reward_multiplier = 2.0 # Standard 1:2 R:R, but actively managed via Break-Even

# Context Filter: Trend Identification
is_uptrend = current_price > sma200
is_downtrend = current_price < sma200

# Entry logic strictly respects the macro trend context
if is_uptrend and current_price <= lower_band and rsi < 40:
    signal = "STRONG BUY (TREND ALIGNED)"
    stop_loss = round(current_price - (st_dev * risk_multiplier), 4)
    take_profit = round(current_price + (st_dev * reward_multiplier), 4)
elif is_downtrend and current_price >= upper_band and rsi > 60:
    signal = "STRONG SELL (TREND ALIGNED)"
    stop_loss = round(current_price + (st_dev * risk_multiplier), 4)
    take_profit = round(current_price - (st_dev * reward_multiplier), 4)
else:
    # Default boundaries for UI display
    stop_loss = round(current_price - (st_dev * risk_multiplier), 4)
    take_profit = round(current_price + (st_dev * reward_multiplier), 4)

# --- ADVANCED BACKTESTING MODULE (Break-Even & Context Filters) ---
initial_capital = 10000.0
capital = initial_capital
position = 0  
entry_hist_price = 0.0
entry_date = ""
active_sl = 0.0
active_tp = 0.0
break_even_triggered = False

trades = []
peak_capital = initial_capital
max_drawdown = 0.0
gross_profit = 0.0
gross_loss = 0.0

for i in range(period_sma200, len(closes)):
    # Local context
    h_slice_bb = closes[i - period_bb : i]
    h_sma20 = sum(h_slice_bb) / period_bb
    h_var = sum((x - h_sma20) ** 2 for x in h_slice_bb) / period_bb
    h_std = h_var ** 0.5
    h_upper = h_sma20 + (2 * h_std)
    h_lower = h_sma20 - (2 * h_std)
    
    h_sma200 = sum(closes[i - period_sma200 : i]) / period_sma200
    p_close = closes[i]
    h_rsi = calculate_rsi(closes[:i+1], period_rsi)

    # STRICT ENTRY (With Macro Trend Filter)
    if position == 0:
        if p_close > h_sma200 and p_close <= h_lower and h_rsi < 40:
            position = 1
            entry_hist_price = p_close
            entry_date = dates[i]
            active_sl = p_close - (h_std * risk_multiplier)
            active_tp = p_close + (h_std * reward_multiplier)
            break_even_triggered = False
            
        elif p_close < h_sma200 and p_close >= h_upper and h_rsi > 60:
            position = -1
            entry_hist_price = p_close
            entry_date = dates[i]
            active_sl = p_close + (h_std * risk_multiplier)
            active_tp = p_close - (h_std * reward_multiplier)
            break_even_triggered = False
    
    # DYNAMIC EXITS
    elif position == 1: 
        # Break-Even trigger: If price moves 1 Risk unit in favor, move SL to Entry
        if not break_even_triggered and p_close >= entry_hist_price + (h_std * risk_multiplier):
            active_sl = entry_hist_price 
            break_even_triggered = True
            
        if p_close <= active_sl or p_close >= active_tp:
            profit = (p_close - entry_hist_price) * 10000
            capital += profit
            trades.append({
                "entry": entry_date, "exit": dates[i], "type": "BUY",
                "entryPrice": round(entry_hist_price, 4), "exitPrice": round(p_close, 4),
                "profit": round(profit, 2)
            })
            position = 0

    elif position == -1: 
        # Break-Even trigger for Short
        if not break_even_triggered and p_close <= entry_hist_price - (h_std * risk_multiplier):
            active_sl = entry_hist_price
            break_even_triggered = True

        if p_close >= active_sl or p_close <= active_tp:
            profit = (entry_hist_price - p_close) * 10000
            capital += profit
            trades.append({
                "entry": entry_date, "exit": dates[i], "type": "SELL",
                "entryPrice": round(entry_hist_price, 4), "exitPrice": round(p_close, 4),
                "profit": round(profit, 2)
            })
            position = 0

    # Drawdown Calculation
    if capital > peak_capital:
        peak_capital = capital
    current_dd = (peak_capital - capital) / peak_capital * 100
    if current_dd > max_drawdown:
        max_drawdown = current_dd

# Institutional Metrics Processing
for t in trades:
    if t["profit"] > 0:
        gross_profit += t["profit"]
    else:
        gross_loss += abs(t["profit"])

winning_trades = [t for t in trades if t["profit"] > 0]
win_rate = round((len(winning_trades) / len(trades)) * 100, 1) if trades else 0.0
total_return = round(((capital - initial_capital) / initial_capital) * 100, 2)
profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else 0.0

output = {
    "lastUpdate": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
    "currentPrice": round(current_price, 4),
    "dates": dates[-60:], 
    "prices": closes[-60:],
    "upperBand": upper_band,
    "lowerBand": lower_band,
    "sma": round(sma20, 4),
    "sma200": round(sma200, 4),
    "rsi": rsi,
    "signal": signal,
    "stopLoss": stop_loss,
    "takeProfit": take_profit,
    "backtest": {
        "initialCapital": initial_capital,
        "finalCapital": round(capital, 2),
        "totalReturn": total_return,
        "winRate": win_rate,
        "maxDrawdown": round(max_drawdown, 2),
        "profitFactor": profit_factor,
        "totalTrades": len(trades),
        "trades": trades[-5:]
    }
}

with open("data.json", "w") as f:
    json.dump(output, f, indent=4)
