import pandas as pd
import numpy as np
import kite_data

def get_market_regime(symbol="NIFTY"):
    metrics = get_market_metrics(symbol)
    return metrics.get("regime", "SIDEWAYS")
    
def get_market_metrics(symbol="NIFTY"):
    """
    Returns dict with Regime, ATR, RSI etc.
    """
    try:
        # Fetch Data via Kite (approx 3 months -> 90 days)
        # Using "day" candles for longer term trend
        candles = kite_data.get_historical_data(symbol, interval="1d", days=120)
        
        if not candles:
            return {"regime": "SIDEWAYS", "atr": 0, "avg_atr": 0, "spot_price": 0, "iv_rank": 0}
            
        data = pd.DataFrame(candles)
        
        # Rename lower case to Title Case
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
        # ATR (Vol proxy)
        high_low = data['High'] - data['Low']
        high_close = np.abs(data['High'] - data['Close'].shift())
        low_close = np.abs(data['Low'] - data['Close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        data['ATR'] = true_range.rolling(14).mean()
        
        # HISTORICAL VOLATILITY (HV) - 20 Day Annualized
        # Log Returns
        data['LogRet'] = np.log(data['Close'] / data['Close'].shift(1))
        # Rolling Std Dev * Sqrt(252) * 100
        data['HV'] = data['LogRet'].rolling(window=20).std() * np.sqrt(252) * 100
        
        current = data.iloc[-1]
        
        # Logic
        price = current['Close']
        ema20 = current['EMA20']
        ema50 = current['EMA50']
        rsi = current['RSI']
        atr = current['ATR']
        hv = current.get('HV', 0)
        if np.isnan(hv): hv = 0
        avg_atr = data['ATR'].mean()
        
        # 1. Volatility Check
        is_volatile = atr > (avg_atr * 1.3)
        is_slow = atr < (avg_atr * 0.7)
        
        # 2. Trend Check
        regime = "SIDEWAYS"
        if price > ema20 > ema50:
            if is_volatile: regime = "VOLATILE_UP"
            else: regime = "TRENDING_UP"
        elif price < ema20 < ema50:
            if is_volatile: regime = "VOLATILE_DOWN"
            else: regime = "TRENDING_DOWN"
        else:
            if is_volatile: regime = "VOLATILE"
            elif is_slow: regime = "SLOW"
            else: regime = "SIDEWAYS"
            
        return {
            "regime": regime,
            "atr": atr,
            "avg_atr": avg_atr,
            "hv": hv,
            "rsi": rsi,
            "spot_price": price,
            "trend_strength": abs(price - ema50) / price * 100 # Approx % deviation
        }
            
    except Exception as e:
        print(f"[Regime] Error: {e}")
        return {"regime": "SIDEWAYS", "atr": 0, "avg_atr": 0, "spot_price": 0}
