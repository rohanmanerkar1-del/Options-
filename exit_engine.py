import datetime

def should_exit_by_target(entry_price, current_price, target_price=0):
    """
    Exit if current price hits target.
    If target_price is provided, use it. Else default to 1.30x.
    """
    if entry_price <= 0: return False
    
    if target_price > 0:
        return current_price >= target_price
        
    return current_price >= (entry_price * 1.30)

def should_exit_by_stoploss(entry_price, current_price, sl_price=0):
    """
    Exit if current price hits SL.
    If sl_price is provided, use it. Else default to 0.80x.
    """
    if entry_price <= 0: return False
    
    if sl_price > 0:
        return current_price <= sl_price
        
    return current_price <= (entry_price * 0.80)

def should_exit_by_trailing_sl(current_price, trailing_sl_price):
    """
    Exit if current price drops below dynamic trailing SL.
    """
    if trailing_sl_price <= 0: return False
    return current_price < trailing_sl_price

def should_exit_by_time_decay(days_left, is_otm=False):
    """
    - If days_left <= 2 and trade is OTM -> exit (Theta Decay Risk)
    """
    if days_left <= 2 and is_otm:
        return True
    if days_left <= 0:
        return True # Expiry Exit
    return False

def should_exit_by_trend_reversal(trend_now, trend_entry):
    """
    - If trend_entry was UP and trend_now turns DOWN -> exit
    - If trend_entry was DOWN and trend_now turns UP -> exit
    """
    trend_now = trend_now.upper()
    trend_entry = trend_entry.upper()
    
    if "UP" in trend_entry and "DOWN" in trend_now:
        return True
    if "DOWN" in trend_entry and "UP" in trend_now:
        return True
        
    return False

def should_exit_short_by_iv_spike(iv_last, iv_current):
    """
    For Short Sellers: If IV spikes significantly (>20%), Vega risk is high.
    Exit short positions.
    """
    if iv_last <= 0: return False
    spike = (iv_current - iv_last) / iv_last
    return spike > 0.20
    
def should_exit_short_by_price_spike(entry_price, current_price, sl_price=0):
    """
    For Short: Entry is High, Loss is Higher.
    If current > SL -> Exit.
    """
    if sl_price > 0:
        return current_price >= sl_price
    
    # Default 30% SL on premium
    return current_price >= (entry_price * 1.30)

def should_exit_short_by_target(entry_price, current_price, target_price=0):
    """
    For Short: Profit is Lower Price.
    target_price should be < entry_price.
    """
    if target_price > 0:
        return current_price <= target_price
        
    # Default 50% decay target
    return current_price <= (entry_price * 0.50)

