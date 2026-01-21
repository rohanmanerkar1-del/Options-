def get_atm_strike(spot_price, symbol):
    """
    --- 4. FIX ATM STRIKE CALCULATION ---
    """
    # Normalize (Strict Checks)
    underlying = symbol.upper()
    
    # 1. Handle BANKNIFTY vs stocks like HDFCBANK
    if "BANKNIFTY" in underlying or "NIFTY BANK" in underlying:
        underlying = "BANKNIFTY"
    elif "FINNIFTY" in underlying or "NIFTY FIN" in underlying:
        underlying = "FINNIFTY"
    elif "NIFTY" in underlying and "FIN" not in underlying:
         underlying = "NIFTY"
         
    if underlying == "BANKNIFTY":
        step = 100
    elif underlying == "NIFTY" or underlying == "FINNIFTY":
        step = 50
    else:
        # Stocks
        step = 10
        
    return round(spot_price / step) * step

def get_otm_strikes(atm, symbol, option_type="CE", count=5):
    """
    Returns list of OTM strikes using the same step logic.
    """
    underlying = symbol.upper()
    
    if "BANKNIFTY" in underlying or "NIFTY BANK" in underlying:
        underlying = "BANKNIFTY"
    elif "FINNIFTY" in underlying or "NIFTY FIN" in underlying:
        underlying = "FINNIFTY"
    elif "NIFTY" in underlying and "FIN" not in underlying:
        underlying = "NIFTY"

    if underlying == "BANKNIFTY": step = 100
    elif underlying == "NIFTY" or underlying == "FINNIFTY": step = 50
    else: step = 10
    
    strikes = []
    for i in range(1, count + 1):
        if option_type == "CE":
            strikes.append(atm + (i * step))
        else:
            strikes.append(atm - (i * step))
            
    return strikes
