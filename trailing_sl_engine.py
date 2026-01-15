def get_trailing_sl(entry_price, current_price, current_sl):
    """
    Calculates the new trailing stop-loss based on price movement.
    
    Logic:
    - If price > 10% of entry, lock SL at -5% (Break-even-ish/Small Loss)
    - If price > 20% of entry, lock SL at +5% (Profit Lock)
    - If price > 30% of entry, lock SL at +15% (Deep Profit Lock)
    - Default: Return the existing SL (which starts at 70% of entry)
    
    Returns:
        float: The new stop-loss price (highest of calculated or current_sl).
    """
    if entry_price <= 0: return current_sl
    
    new_sl = current_sl
    
    # Check Price thresholds
    if current_price >= entry_price * 1.30:
        # Trail to +15% profit
        proposed = entry_price * 1.15
        if proposed > new_sl: new_sl = proposed
        
    elif current_price >= entry_price * 1.20:
        # Trail to +5% profit
        proposed = entry_price * 1.05
        if proposed > new_sl: new_sl = proposed
        
    elif current_price >= entry_price * 1.10:
        # Trail to -5% (Reduce risk)
        proposed = entry_price * 0.95
        if proposed > new_sl: new_sl = proposed
        
    return new_sl
