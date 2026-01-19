
import datetime
import os
import csv
import config

def check_dnt(market_context):
    """
    Evaluates global Do-Not-Trade conditions.
    
    Inputs:
    - market_context: {
        "regime": str,
        "volatility": str,
        "trend": str, 
        "spot_price": float,
        "iv_rank": float
      }
      
    Returns:
    {
      "do_not_trade": bool,
      "primary_reason": str,
      "risk_category": str,
      "notes": str
    }
    """
    
    # SYSTEM CONSTANTS
    MAX_TRADES_PER_DAY = 5
    MAX_DAILY_LOSS = -2000 # Example
    
    result = {
        "do_not_trade": False,
        "primary_reason": "",
        "risk_category": "",
        "notes": ""
    }
    
    # ----------------------------------------------------------------
    # 1. OVERTRADING / FATIGUE PROTECTION
    # ----------------------------------------------------------------
    stats = _get_daily_stats()
    
    if stats['count'] >= MAX_TRADES_PER_DAY:
        return _dnt("Max Trades Reached", "OVERTRADING", f"Daily limit of {MAX_TRADES_PER_DAY} trades reached.")
        
    if stats['consecutive_losses'] >= 2:
         return _dnt("Consecutive Losses", "FATIGUE", "2 consecutive losses detected. Take a break.")
    
    # ----------------------------------------------------------------
    # 2. THETA BLEED ENVIRONMENT (Time Based)
    # ----------------------------------------------------------------
    now = datetime.datetime.now()
    current_time_str = now.strftime("%H:%M")
    
    # If late day and Market is Flat/Low Vol -> Decay Risk
    regime = market_context.get('regime', "SIDEWAYS")
    vol_state = market_context.get('volatility', "LOW")
    
    if current_time_str > "13:30" and "SIDEWAYS" in regime and "LOW" in vol_state:
        return _dnt("Theta Bleed Risk", "THETA BLEED", f"Time > 1:30 PM and Market is {regime}/{vol_state}.")

    # ----------------------------------------------------------------
    # 3. NO-EDGE MARKET CONDITION
    # ----------------------------------------------------------------
    # If Market is Slow/Sideways and IV is Falling/Low
    # Need IV context
    # Assume IV Rank is passed
    iv_rank = market_context.get('iv_rank', 50)
    
    if "SLOW" in regime:
         return _dnt("Dead Market", "NO_EDGE", "Market Regime detected as SLOW/DEAD.")
         
    if "SIDEWAYS" in regime and vol_state == "LOW" and iv_rank < 20:
         return _dnt("Low Vol Range", "NO_EDGE", "Sideways market with Low IV. Option Sellers only.")
         
    return result

def _dnt(reason, category, notes):
    return {
        "do_not_trade": True,
        "primary_reason": reason,
        "risk_category": category,
        "notes": notes
    }

def _get_daily_stats():
    """
    Reads trade_journal.csv to count today's trades and PnL.
    """
    count = 0
    consecutive_losses = 0
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    
    if not os.path.exists("trade_journal.csv"):
        return {'count': 0, 'consecutive_losses': 0}
        
    try:
        with open("trade_journal.csv", "r") as f:
            reader = csv.DictReader(f)
            # Find today's trades
            trades = []
            for row in reader:
                if row['Timestamp'].startswith(today_str):
                    trades.append(row)
            
            count = len(trades)
            
            # Check last 2 for losses
            # Assumes chronological order
            if count >= 2:
                last_1 = float(trades[-1]['PnL'])
                last_2 = float(trades[-2]['PnL'])
                if last_1 < 0 and last_2 < 0:
                    consecutive_losses = 2
                    
    except Exception as e:
        print(f"[DNT] Error reading journal: {e}")
        
    return {'count': count, 'consecutive_losses': consecutive_losses}
