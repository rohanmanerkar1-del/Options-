import kite_data

def get_market_trend(symbol):
    """
    Analyzes 5-min historical data to determine Trend and Volatility.
    Returns: (Trend_String, Volatility_String)
    """
    # Fetch last 5 days just to be sure we have enough data (though 1 day sufficient for intraday)
    candles = kite_data.get_historical_data(symbol, interval="5minute", days=2)
    
    if not candles or len(candles) < 20: 
        return "SIDEWAYS", "Normal" # Default if no data
    
    # Simple Logic: 
    # Compare current close with 20-period Simple Moving Average (SMA)
    
    closes = [c['close'] for c in candles]
    current_price = closes[-1]
    
    # Calculate SMA 20
    period = 20
    if len(closes) >= period:
        sma_20 = sum(closes[-period:]) / period
    else:
        sma_20 = sum(closes) / len(closes)
        
    # Trend
    trend = "SIDEWAYS"
    if current_price > (sma_20 * 1.001): # 0.1% buffer
        trend = "UP"
    elif current_price < (sma_20 * 0.999):
        trend = "DOWN"
        
    # Volatility Check (ATR or Candle Range)
    # Simple approximate: Average range of last 5 candles
    last_5_ranges = [(c['high'] - c['low']) for c in candles[-5:]]
    avg_range = sum(last_5_ranges) / 5
    price_pct = (avg_range / current_price) * 100
    
    volatility = "Normal"
    if price_pct > 0.3: # If 5min candle moves > 0.3% of asset value
        volatility = "High"
    elif price_pct < 0.1:
        volatility = "Low"
        
    return trend, volatility
