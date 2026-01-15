import kite_data
import pandas as pd
import numpy as np
import time

# List of instruments to scan
SYMBOL_LIST = [
    "NIFTY",
    "BANKNIFTY",
    "FINNIFTY",
    "RELIANCE",
    "HDFCBANK",
    "ICICIBANK",
    "SBIN",
    "TCS",
    "INFY"
]

def fetch_data(symbol):
    """
    Fetches historical data for a symbol to calculate indicators.
    Returns DataFrame or None if failed.
    """
    try:
        # Fetch 5-day history on 5-min timeframe for reliable intraday trend
        candles = kite_data.get_historical_data(symbol, interval="5minute", days=5)
        if not candles or len(candles) < 50:
            return None
            
        df = pd.DataFrame(candles)
        return df
    except Exception as e:
        print(f"[AutoSelect] Error fetching data for {symbol}: {e}")
        return None

def calculate_indicators(df):
    """
    Adds ATR, EMA20, EMA50, RSI to the DataFrame.
    """
    try:
        # EMA
        df['EMA20'] = df['close'].ewm(span=20, adjust=False).mean()
        df['EMA50'] = df['close'].ewm(span=50, adjust=False).mean()
        
        # RSI (14)
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        # ATR (14)
        df['H-L'] = df['high'] - df['low']
        df['H-PC'] = abs(df['high'] - df['close'].shift(1))
        df['L-PC'] = abs(df['low'] - df['close'].shift(1))
        df['TR'] = df[['H-L', 'H-PC', 'L-PC']].max(axis=1)
        df['ATR'] = df['TR'].rolling(window=14).mean()
        
        return df
    except Exception as e:
        print(f"[AutoSelect] Error calculating indicators: {e}")
        return df

def score_symbol(symbol, df):
    """
    Scores a symbol based on Trend, Momentum, and Volatility directly.
    Returns: score (float), details (dict)
    """
    current = df.iloc[-1]
    prev = df.iloc[-2] # To check crossing
    
    score = 0
    reasons = []
    
    close = current['close']
    ema20 = current['EMA20']
    ema50 = current['EMA50']
    rsi = current['RSI']
    atr = current['ATR']
    
    # --- 1. TREND SCORE (Max 5) ---
    trend = "SIDEWAYS"
    if close > ema20 > ema50:
        score += 3
        trend = "UP"
        reasons.append("Strong Uptrend")
    elif close < ema20 < ema50:
        score += 3
        trend = "DOWN"
        reasons.append("Strong Downtrend")
    elif close > ema20:
        score += 1
        trend = "WEAK_UP"
    elif close < ema20:
        score += 1
        trend = "WEAK_DOWN"
        
    # Breakout Bonus
    if (prev['close'] < prev['EMA20']) and (close > ema20):
        score += 2
        reasons.append("Fresh Breakout")
    elif (prev['close'] > prev['EMA20']) and (close < ema20):
        score += 2
        reasons.append("Fresh Breakdown")
        
    # --- 2. MOMENTUM SCORE (Max 3) ---
    if 55 < rsi < 70:
        score += 2
        reasons.append("Bullish Momentum")
    elif 30 < rsi < 45:
        score += 2
        reasons.append("Bearish Momentum")
        
    # --- 3. VOLATILITY/ACTIVITY (Max 2) ---
    avg_atr = df['ATR'].mean()
    if atr > avg_atr * 1.1:
        score += 1.5
        reasons.append("High Volatility")
        volatility = "High"
    elif atr < avg_atr * 0.8:
        reasons.append("Low Volatility")
        volatility = "Low"
    else:
        volatility = "Normal"

    # --- 4. INDEX BIAS ---
    if symbol in ["NIFTY", "BANKNIFTY", "FINNIFTY"]:
        score += 0.5
        
    return score, {
        "symbol": symbol,
        "score": score,
        "trend": trend,
        "volatility": volatility,
        "close": close,
        "reasons": ", ".join(reasons)
    }

def pick_best_symbol():
    """
    Iterates through SYMBOL_LIST, fetches data, scores them, and returns the best one.
    """
    print(f"\n[AutoSelect] Scanning {len(SYMBOL_LIST)} symbols for best opportunity...")
    
    best_score = -999
    best_pick = None
    
    for sym in SYMBOL_LIST:
        print(f" -> Checking {sym}...", end="")
        df = fetch_data(sym)
        if df is None:
            print(" [Skipped - No Data]")
            continue
            
        df = calculate_indicators(df)
        score, details = score_symbol(sym, df)
        
        print(f" Score: {score:.1f} ({details['trend']})")
        
        if score > best_score:
            best_score = score
            best_pick = details
            
    if best_pick:
        return (
            best_pick['symbol'], 
            best_pick['reasons'], 
            best_pick['trend'], 
            best_pick['volatility'], 
            best_pick['close']
        )
    else:
        print("\n[AutoSelect] No suitable symbol found. Defaulting to NIFTY.")
        return "NIFTY", "Default Fallback", "SIDEWAYS", "Normal", 0.0

if __name__ == "__main__":
    pick_best_symbol()
