import atm_engine
import kite_data
import position_sizing
import expiry_engine

def get_otm_strikes(atm, gap, option_type, count=5):
    """
    Returns a list of OTM strikes.
    """
    strikes = []
    if option_type == "CE":
         for i in range(1, count + 1):
            strikes.append(atm + (i * gap))
    else:
         for i in range(1, count + 1):
            strikes.append(atm - (i * gap))
    return strikes

def find_affordable_otm(capital, base_symbol, atm, expiry_data, opt_type, kite):
    """
    Finds the first OTM strike that allows buying at least 1 lot within capital.
    Now uses strict 'kite' instance and 'expiry_engine' symbol builder.
    """
    # Determine Gap
    gap = 100 if "BANKNIFTY" in base_symbol else 50
    
    strikes = get_otm_strikes(atm, gap, opt_type, count=5)
    
    print(f"    [OTM Search] Checking {strikes}...")
    
    expiry_date = expiry_data['date']
    
    for stk in strikes:
        # Strict Symbol Construction
        # NFO: prefix required for Kite LTP? 
        # kite_data.get_ltp handles "NFO:" check, constructing it with "NFO:" is safer if kite_data expects it 
        # or if we need it for trading.
        # User's strict logic returned pure valid tradingsymbol "NIFTY24JAN...".
        # kite_data.get_ltp takes "NIFTY24JAN..." or "NFO:NIFTY24JAN..."
        # But kite.ltp expects "NFO:SYMBOL" usually? 
        # Let's verify kite_data.get_ltp logic: "if symbol not in OPTION_TOKENS and 'NFO:' in symbol..."
        # It implies it handles both?
        # Standardize on passing "NFO:" + symbol to be safe for API calls.
        
        sym_base = expiry_engine.get_option_symbol(base_symbol, expiry_date, stk, opt_type)
        sym = "NFO:" + sym_base
        
        # 🔥 6️⃣ REAL LIQUIDITY FILTER (Using kite_data helper)
        if not kite_data.valid_liquidity(kite, sym):
            print(f"       [Skip] Illiquid: {sym_base}")
            continue

        # If valid, check Affordability
        ltp = kite_data.get_ltp(sym, kite)
        
        if ltp is None: continue

        lots, qty, cost, rem = position_sizing.calculate_lot_size(capital, ltp, base_symbol)
        
        if lots >= 1:
            return {
                "strike": stk,
                "symbol": sym,
                "premium": ltp,
                "lots": lots,
                "qty": qty,
                "cost": cost,
                "rem": rem,
                "is_fallback": False
            }
            
    # Fallback to Deep OTM (Last resort)
    deep_strike = strikes[-1] + gap
    sym_base = expiry_engine.get_option_symbol(base_symbol, expiry_date, deep_strike, opt_type)
    sym = "NFO:" + sym_base
    
    ltp = kite_data.get_ltp(sym, kite)
    return {
        "strike": deep_strike,
        "symbol": sym,
        "premium": ltp if ltp else 0.0,
        "lots": 1, 
        "qty": 50, # Mock qty if affordable logic fails
        "cost": 0,
        "rem": capital,
        "is_fallback": True
    }
