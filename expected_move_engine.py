
import math

def evaluate_expectancy(candidate, market_metrics, greeks, holding_minutes=60):
    """
    Evaluates if Expected Move justifies the Cost.
    
    Inputs:
    - candidate: {premium, type (CE/PE), strike}
    - market_metrics: {atr, avg_atr, spot_price, iv_rank}
    - greeks: {delta, theta, iv}
    - holding_minutes: expected hold time (default 60 mins)
    
    Returns:
    {
      "allowed": bool,
      "expected_spot_move": float,
      "expected_option_gain": float,
      "expected_cost": float,
      "edge_ratio": float,
      "decision_reason": str
    }
    """
    
    # 1. EXTRACT DATA
    atr = market_metrics.get('atr', 0)
    spot = market_metrics.get('spot_price', 0)
    
    delta = abs(greeks.get('delta', 0.5))
    theta = abs(greeks.get('theta', 0))
    iv = greeks.get('iv', 0) / 100.0 # Convert to decimal
    
    premium = candidate['premium']
    
    # Defaults
    if atr == 0 or spot == 0:
        return _allow("Data Missing (ATR/Spot)", 0, 0, 0, 999)

    # 2. CALCULATE EXPECTED SPOT MOVE
    # Method 1: ATR Based
    # Normalized for holding period
    # Session minutes = 375 (9:15 to 3:30)
    session_minutes = 375
    move_atr = atr * math.sqrt(holding_minutes / session_minutes)
    
    # Method 2: IV Based
    # Move = Spot * IV * sqrt(days / 365)
    # Convert holding mins to years? 
    # holding_hours / (24*365)? Or trading hours?
    # Standard: IV is annualized. T = minutes / (252 * 375) approx for trading time?
    # Let's use simplified: T = holding_minutes / (365 * 1440) for calendar time decay logic 
    # but for volatility usually we use trading days.
    # Let's stick to user formula approximation if provided, or standard:
    # User formula: Spot * IV * sqrt(holding_window / trading_days??) -> "trading_days" unit?
    # Let's assume standard annualized IV projection for the specific window.
    # T_years = holding_minutes / (365 * 24 * 60)
    T_years = holding_minutes / 525600.0
    move_iv = spot * iv * math.sqrt(T_years)
    
    # Conservative Estimate (Lower of two)
    # Sometimes IV implies much less than ATR in dull regimes.
    expected_spot_move = min(move_atr, move_iv) if move_iv > 0 else move_atr
    
    # 3. EXPECTED OPTION GAIN
    expected_option_gain = expected_spot_move * delta
    
    # 4. TOTAL EXPECTED COST (Risk + Decay + Trans)
    # User Formula: premium_paid + theta_cost + trans
    # We interpreted "premium_paid" as "Risked Amount" (Stop Loss) for Buy trades.
    # Let's assume 20% Stop Loss Risk on Premium.
    
    risk_amount = premium * 0.20
    
    # Theta Cost for holding period
    # Theta is usually daily decay.
    # Cost = Theta * (minutes / minutes_in_day?) or minutes_in_session?
    # Theta is per calendar day usually.
    theta_cost = theta * (holding_minutes / (24 * 60)) # Fraction of day?
    # Actually theta is often linear per day passing.
    # Let's assume proportional decay.
    theta_cost = theta * (holding_minutes / 1440.0)
    if theta_cost < 0.1: theta_cost = 0.5 # Minimum decay floor
    
    trans_cost = 2.0 # Brokerage + Slippage est per lot unit
    
    total_expected_cost = risk_amount + theta_cost + trans_cost
    
    # 5. DECISION GATE
    # Gain >= 1.2 * Cost
    edge_ratio = expected_option_gain / total_expected_cost if total_expected_cost > 0 else 0
    
    # Adjust Buffer based on Regime
    # If Range/Sideways, require higher edge
    # Adjust Buffer based on Regime
    # IF regime == RANGE (Sideways/Slow) -> 1.5
    # ELSE -> 1.2
    regime = market_metrics.get('regime', "SIDEWAYS")
    required_edge = 1.2 # Default for Trending/Volatile
    
    if "SIDEWAYS" in regime or "SLOW" in regime:
        required_edge = 1.5
    
    if edge_ratio >= required_edge:
        return _allow(f"Positive Expectancy ({edge_ratio:.2f})", expected_spot_move, expected_option_gain, total_expected_cost, edge_ratio)
    else:
        reason = f"Low Edge ({edge_ratio:.2f}). ExpMove {expected_spot_move:.1f}pts < Cost."
        return _block(reason, expected_spot_move, expected_option_gain, total_expected_cost, edge_ratio)

def _allow(reason, em, og, cost, ratio):
    return {
        "allowed": True,
        "expected_spot_move": round(em, 2),
        "expected_option_gain": round(og, 2),
        "expected_cost": round(cost, 2),
        "edge_ratio": round(ratio, 2),
        "decision_reason": reason
    }

def _block(reason, em, og, cost, ratio):
    return {
        "allowed": False,
        "expected_spot_move": round(em, 2),
        "expected_option_gain": round(og, 2),
        "expected_cost": round(cost, 2),
        "edge_ratio": round(ratio, 2),
        "decision_reason": reason
    }
