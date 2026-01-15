import pandas as pd
import numpy as np
import kite_data

def get_market_regime(symbol="NIFTY"):
    """
    Analyzes the market regime using EMA, RSI, and ATR.
    Returns: regime string ("TRENDING_UP", "TRENDING_DOWN", "SIDEWAYS", "VOLATILE", "SLOW")
    """
    try:
        # Fetch Data via Kite (approx 3 months -> 90 days)
        # Using "day" candles for longer term trend
        candles = kite_data.get_historical_data(symbol, interval="1d", days=120)
        
        if not candles:
            return "SIDEWAYS" # Fallback
            
        data = pd.DataFrame(candles)
        
        # Rename lower case to Title Case for consistency if needed, but Zerodha gives 'close'
        # We need to standardize column names to: Close, High, Low, Open
        data.rename(columns={'close': 'Close', 'high': 'High', 'low': 'Low', 'open': 'Open'}, inplace=True)
        
        # Indicators
        data['EMA20'] = data['Close'].ewm(span=20).mean()
        data['EMA50'] = data['Close'].ewm(span=50).mean()
        
        # RSI
        delta = data['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        data['RSI'] = 100 - (100 / (1 + rs))
        
        # ATR (Vol proxy)
        high_low = data['High'] - data['Low']
        high_close = np.abs(data['High'] - data['Close'].shift())
        low_close = np.abs(data['Low'] - data['Close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        data['ATR'] = true_range.rolling(14).mean()
        
        current = data.iloc[-1]
        
        # Logic
        price = current['Close']
        ema20 = current['EMA20']
        ema50 = current['EMA50']
        rsi = current['RSI']
        atr = current['ATR']
        avg_atr = data['ATR'].mean()
        
        # 1. Volatility Check
        is_volatile = atr > (avg_atr * 1.3)
        is_slow = atr < (avg_atr * 0.7)
        
        # 2. Trend Check
        if price > ema20 > ema50:
            if is_volatile: return "VOLATILE_UP"
            return "TRENDING_UP"
            
        elif price < ema20 < ema50:
            if is_volatile: return "VOLATILE_DOWN"
            return "TRENDING_DOWN"
            
        else:
            # Sideways or unclear
            if is_volatile: return "VOLATILE"
            if is_slow: return "SLOW"
            return "SIDEWAYS"
            
    except Exception as e:
        print(f"[Regime] Error: {e}")
        return "SIDEWAYS" # Safe Fallback
