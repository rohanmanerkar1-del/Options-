def estimate_short_margin(symbol, strike, premium, lot_size=None):
    """
    Estimates margin required for a Short Option position.
    Formula Estimation (Zerodha-ish):
    Margin ~ Span + Exposure
    Approx Rule of Thumb: 1.2 * Spot * LotSize * 0.20 (20% of contract value)
    
    This is a rough estimation. Real API call is needed for exact values.
    """
    # Defaults
    if lot_size is None:
        if "NIFTY" in symbol: lot_size = 50 if "BANK" not in symbol else 15
        else: lot_size = 50 # Fallback
        
    # Spot proxy from strike (Rough)
    spot_proxy = strike 
    
    # 20% of Contract Value (Standard Regulation)
    estimated_margin = spot_proxy * lot_size * 0.20
    
    # Add buffer
    return estimated_margin * 1.1

def margin_allows_short(available_margin, required_margin):
    return available_margin >= required_margin

def choose_strategy_based_on_margin(margin, capital, intended_strategy_type="ANY"):
    """
    Filters allowed strategies based on Margin.
    
    Logic:
    - Margin = 0: BUY ONLY.
    - Margin < 10k: BUY ONLY (Safety).
    - Margin 10k-30k: DEBIT SPREADS (Hedged Short allowed).
    - Margin > 30k: SELL / SHORT STRADDLE allowed.
    """
    if margin <= 0:
        return "BUY_ONLY"
        
    if margin < 10000:
        return "BUY_ONLY"
        
    if 10000 <= margin < 30000:
        return "SPREADS_ONLY"
        
    if margin >= 30000:
        return "ALL_ALLOWED" # Selling allowed
        
    return "BUY_ONLY"
