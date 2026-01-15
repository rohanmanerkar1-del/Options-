def pick_timeframe(volatility_state="Normal"):
    """
    Returns suggested timeframe based on volatility.
    """
    if volatility_state == "High":
        return "5m" # Fast scalping
    elif volatility_state == "Low":
        return "15m" # Swing / Trend
    elif volatility_state == "Extreme":
        return "1m" # Algo/HFT (or stay out)
    else:
        return "5m" # Default intraday
