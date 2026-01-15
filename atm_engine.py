def get_atm_strike(spot_price, symbol):
    """
    --- 4. FIX ATM STRIKE CALCULATION ---
    """
    # Normalize
    underlying = symbol.upper()
    if "NIFTY" in underlying and "BANK" not in underlying and "FIN" not in underlying:
         underlying = "NIFTY"
    if "BANK" in underlying: underlying = "BANKNIFTY"
    
    if underlying == "BANKNIFTY":
        step = 100
    elif underlying == "NIFTY":
        step = 50
    else:
        step = 10
        
    return round(spot_price / step) * step

def get_otm_strikes(atm, symbol, option_type="CE", count=5):
    """
    Returns list of OTM strikes using the same step logic.
    """
    underlying = symbol.upper()
    if "NIFTY" in underlying and "BANK" not in underlying: underlying = "NIFTY"
    if "BANK" in underlying: underlying = "BANKNIFTY"

    if underlying == "BANKNIFTY": step = 100
    elif underlying == "NIFTY": step = 50
    else: step = 10
    
    strikes = []
    for i in range(1, count + 1):
        if option_type == "CE":
            strikes.append(atm + (i * step))
        else:
            strikes.append(atm - (i * step))
            
    return strikes
