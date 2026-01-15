def pick_strategy(regime):
    """
    Returns strategy based on Regime (from market_regime_engine).
    Regimes: TRENDING_UP, TRENDING_DOWN, SIDEWAYS, VOLATILE, SLOW, VOLATILE_UP, VOLATILE_DOWN
    """
    regime = regime.upper()
    
    if "TRENDING_UP" in regime:
        return "BUY CE"
    elif "TRENDING_DOWN" in regime:
        return "BUY PE"
    elif "VOLATILE_UP" in regime:
        return "BUY CE (Volatile)"
    elif "VOLATILE_DOWN" in regime:
        return "BUY PE (Volatile)"
    elif "SIDEWAYS" in regime:
        return "STRADDLE SELL (Short)"
    elif "VOLATILE" in regime: # Pure Volatile w/o clear trend
        return "STRANGLE BUY (Long)"
    elif "SLOW" in regime:
        return "DEBIT SPREAD"
        
    return "WAIT"

def get_trade_type_label(ce_or_pe, regime):
    if ce_or_pe == "CE": return "Long Call"
    if ce_or_pe == "PE": return "Long Put"
    if "STRADDLE" in regime: return "Short Straddle"
    if "STRANGLE" in regime: return "Long Strangle"
    return "Custom"
