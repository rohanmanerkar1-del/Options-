import math
import lot_engine

def calculate_lot_size(capital, premium, symbol):
    """
    Calculates how many lots to buy based on capital.
    Returns (lots, total_qty, total_cost, rem_capital)
    """
    lot_size = lot_engine.get_lot_size(symbol)
    
    cost_per_lot = premium * lot_size
    
    if cost_per_lot == 0:
        return 0, 0, 0, capital

    # Max lots affordable
    max_lots = math.floor(capital / cost_per_lot)
    
    total_qty = max_lots * lot_size
    total_cost = max_lots * cost_per_lot
    remaining_capital = capital - total_cost
    
    return max_lots, total_qty, total_cost, remaining_capital

def get_risk_reward(premium):
    """
    --- 5. FIX STOPLOSS & TARGET CALCULATION ---
    SL = entry_price * 0.80       # 20% stoploss
    TARGET = entry_price * 1.30   # 30% target
    """
    sl_price = round(premium * 0.80, 2)
    target_price = round(premium * 1.30, 2)
    
    risk = round(premium - sl_price, 2)
    reward = round(target_price - premium, 2)
    
    return sl_price, target_price, risk, reward
