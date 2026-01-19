
import datetime
import greeks_engine
import kite_data
import market_regime_engine

def check_veto(candidate, market_context, kite):
    """
    Analyzes a trade candidate and returns a Veto Object.
    
    Inputs:
    - candidate: {symbol, type (CE/PE/SELL/BUY), strike, expiry, premium, ltp}
    - market_context: {regime, trend, volatility, spot_price}
    - kite: API instance
    
    Returns:
    {
      "veto": bool,
      "veto_reason": str,
      "veto_category": str,
      "details": str
    }
    """
    
    symbol = candidate['symbol']
    action = candidate['action'] # BUY / SELL
    opt_type = candidate['type'] # CE / PE
    ltp = candidate['premium']
    
    # Defaults
    result = {
        "veto": False, 
        "veto_reason": "", 
        "veto_category": "", 
        "details": ""
    }

    # ----------------------------------------------------------------
    # 1. LIQUIDITY & SPREAD VETO
    # ----------------------------------------------------------------
    # Rule 1: Spread > 2% -> Veto
    # Rule 2: Spread > 1% AND Premium < 20 -> Veto
    spread_info = kite_data.get_quote_spread(symbol, kite)
    
    if spread_info:
        spread_pct = spread_info['spread_pct']
        
        if spread_pct > 2.0:
            return _veto("Wide Spread", "LIQUIDITY", f"Bid-Ask Spread is {spread_pct:.2f}% (>2%). Slippage Risk.")
            
        if spread_pct > 1.0 and ltp < 20.0:
            return _veto("Wide Spread on Cheap Option", "LIQUIDITY", f"Spread {spread_pct:.2f}% is too high for LTP {ltp}.")
            
    # Basic Check for Sellers (Gamma/Tail Risk on pennies)
    if ltp < 5 and action == "SELL":
        return _veto("Price too low for Selling", "LIQUIDITY", f"LTP {ltp} is risky for selling (Gamma risk).")

    # ----------------------------------------------------------------
    # 2. TIME DECAY VETO (Blocks Late Day OTM Buys)
    # ----------------------------------------------------------------
    now = datetime.datetime.now()
    current_time_str = now.strftime("%H:%M")
    
    # Calculate DTE
    expiry_date = candidate.get('expiry') # Need strictly
    dfe = greeks_engine.calculate_time_to_expiry(expiry_date) * 365 # Days
    
    if action == "BUY":
        # New Rule: Block ALL new Longs if DTE <= 3
        if dfe <= 3.0:
             return _veto("Expiry Too Close (<3 Days)", "TIME DECAY", f"Buying with DTE {dfe:.1f} is high Gamma risk.")

        # If DTE <= 1 (Expiry or day before) AND Time > 13:30 AND OTM
        if dfe <= 1.0 and current_time_str > "13:30":
            # Check OTM status
            spot = market_context.get('spot_price', 0)
            strike = candidate.get('strike', 0)
            is_otm = (opt_type == "CE" and spot < strike) or (opt_type == "PE" and spot > strike)
            
            if is_otm:
                return _veto("Late Day OTM Buy", "TIME DECAY", "Buying OTM options > 1:30 PM near expiry is poor R:R.")

    # ----------------------------------------------------------------
    # 3. RANGE REGIME VETO (Blocks Longs in Chop)
    # ----------------------------------------------------------------
    regime = market_context.get('regime', "SIDEWAYS")
    
    if action == "BUY" and ("SIDEWAYS" in regime or "SLOW" in regime):
        # Allow only if Volatility is expanding
        vol_state = market_context.get('volatility', "LOW")
        if "HIGH" not in vol_state:
             return _veto("Buying in Sideways Market", "RANGE REGIME", f"Regime is {regime} and Volatility is {vol_state}. Sellers edge.")

    # ----------------------------------------------------------------
    # 4. VOLATILITY TAX VETO (Blocks Expensive/Overpriced Options)
    # ----------------------------------------------------------------
    # Formula: Volatility Tax = IV / RV
    # IF Tax > 1.2 -> Veto Longs
    
    iv = kite_data.get_iv_value(kite, symbol) or 0
    iv_rank = market_context.get('iv_rank', 0)
    rv = market_context.get('hv', 0) # Using HV as Realized Volatility
    
    # Calculate Volatility Tax
    vol_tax = 0
    if rv > 0:
        vol_tax = iv / rv
    
    if action == "BUY":
        # Rule: Volatility Tax > 1.2 or Extreme Rank > 80
        tax_breach = (vol_tax > 1.2)
        rank_breach = (iv_rank > 80)
        
        if tax_breach or rank_breach:
             reason = f"Volatility Tax {vol_tax:.2f} > 1.2" if tax_breach else f"IV Rank {iv_rank} > 80"
             return _veto("Overpriced Option", "VOLATILITY TAX", f"{reason}. IV is expensive vs Realized Vol.")
             
    # ----------------------------------------------------------------
    # 5. URGENCY VETO (The "Why Now?" Check)
    # ----------------------------------------------------------------
    # Direction without urgency = Bleed.
    # If Buying, we need Trend Strength or High Momentum
    trend_dir = market_context.get('trend', "")
    
    if action == "BUY":
        # Check alignment
        if opt_type == "CE" and "UP" not in trend_dir:
             # Counter trend buy?
             pass # Maybe mean reversion, allow for now unless strict
        
        # Check Theta vs Move
        # If Theta is high, we need high conviction
        # Calculate Theta
        # We need greeks. 
        # For efficiency, maybe skip expensive calc if satisfied elsewhere.
        pass

    return result

def _veto(reason, category, details):
    return {
        "veto": True,
        "veto_reason": reason,
        "veto_category": category,
        "details": details
    }
