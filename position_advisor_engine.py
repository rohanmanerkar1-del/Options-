import kite_data
import market_regime_engine
import oi_analysis_engine
import datetime
import greeks_engine

# ------------------------------------------------------------------------
# CORE ADVISORY LOGIC
# ------------------------------------------------------------------------

def analyze_position(position_data, kite=None):
    """
    Analyzes a SINGLE position and returns an advisory dict.
    
    position_data expected format:
    {
        "tradingsymbol": "NIFTY24JAN21500CE",
        "instrument_token": 123456,
        "quantity": 50, (Positive=Long, Negative=Short)
        "average_price": 100.0,
        "product": "NRML"
    }
    """
    if kite is None:
        kite = kite_data.get_kite()

    symbol = position_data["tradingsymbol"]
    qty = position_data["quantity"]
    avg_price = position_data["average_price"]
    
    # 1. basic Info
    is_long = qty > 0
    qty_abs = abs(qty)
    
    # Check underlying (NIFTY/BANKNIFTY) - simple heuristic
    underlying = "NIFTY"
    if "BANKNIFTY" in symbol: underlying = "BANKNIFTY"
    elif "FINNIFTY" in symbol: underlying = "FINNIFTY"
    
    # Check Option Type
    is_ce = "CE" in symbol
    is_pe = "PE" in symbol
    option_type = "CE" if is_ce else "PE"
    
    # 2. Fetch Live Data
    ltp = kite_data.get_ltp(symbol, kite)
    
    # Handle Data Fetch Breakdown
    if ltp is None or ltp == 0:
        return {
        "symbol": symbol,
        "decision": "DATA_ERROR",
        "confidence": "LOW",
        "pnl_pct": 0.0,
        "primary_reason": "Live Price Unavailable",
        "supporting_factors": [],
        "risk_flags": ["Could not fetch LTP."],
        "ltp": 0
    }

    pnl = (ltp - avg_price) * qty
    pnl_pct = 0
    if avg_price > 0:
        pnl_pct = ((ltp - avg_price) / avg_price) * 100 if is_long else ((avg_price - ltp) / avg_price) * 100

    # 3. Market Context & Greeks
    regime = market_regime_engine.get_market_regime(underlying)  # TRENDING_UP, TRENDING_DOWN, SIDEWAYS
    
    # Fetch Instrument Details for Greeks
    details = kite_data.get_instrument_detail(symbol)
    greeks = {}
    
    if details:
        # We need underlying spot price
        S = kite_data.get_ltp(underlying, kite) or 0
        K = details.get("strike", 0)
        expiry = details.get("expiry")
        T = greeks_engine.calculate_time_to_expiry(expiry)
        
        # IV (Try to fetch real IV, else approx)
        sigma = kite_data.get_iv_value(kite, symbol)
        if not sigma or sigma == 0: sigma = 0.20 # Default fallback 20%
        else: sigma = sigma / 100.0 # Convert to decimal
        
        greeks = greeks_engine.get_greeks(S, K, T, 0.07, sigma, option_type)
        
    # 4. Underlying Trend Check
    u_ltp = kite_data.get_ltp(underlying, kite)
    # oi_signal = oi_analysis_engine.interpret_oi_signal(..., ...) 
    # For simplicity, we compare Regime.
    
    # 5. Volatility / IV
    # iv = kite_data.get_iv_value(kite, symbol)
    
    # --- DECISION LOGIC ---
    decision = "HOLD"
    confidence = "MEDIUM"
    reasons = []
    risks = []
    
    # A. TREND CHECK
    trend_aligned = False
    if is_long:
        if is_ce and "UP" in regime: trend_aligned = True
        elif is_pe and "DOWN" in regime: trend_aligned = True
    else: # Short
        if is_ce and "DOWN" in regime: trend_aligned = True
        elif is_pe and "UP" in regime: trend_aligned = True
        elif regime == "SIDEWAYS": trend_aligned = True # Shorts like sideways

    if trend_aligned:
        reasons.append(f"Market Trend ({regime}) matches position.")
    else:
        risks.append(f"Market Trend ({regime}) opposes position.")

    # B. PROFIT/LOSS CHECK
    if pnl_pct < -15: # 15% Loss
        decision = "CAUTION"
        risks.append(f"High Drawdown: {pnl_pct:.1f}%")
        if pnl_pct < -30:
            decision = "EXIT"
            risks.append("Stop Loss Threshold breached (-30%).")
    elif pnl_pct > 20:
        reasons.append(f"Healthy Profit: {pnl_pct:.1f}%")
        
    # C. TIME DECAY (Theta) Check (Updated with Real Greeks)
    if is_long and greeks:
        theta_cost = greeks.get('theta', 0) * qty_abs # Total money losing per day
        # Heuristic: If Theta cost is > 5% of invested capital per day, it's risky
        invested = avg_price * qty_abs
        if invested > 0 and abs(theta_cost) > (invested * 0.05):
             risks.append(f"High Theta Decay: Losing ₹{abs(theta_cost):.0f}/day")
             if "SIDEWAYS" in regime:
                 decision = "CAUTION" if decision != "EXIT" else "EXIT"
                 risks.append("Decay Risk accelerated by Sideways Market.")
    # Original Theta Decay Check (if no greeks)
    elif is_long and "SIDEWAYS" in regime:
        decision = "CAUTION" if decision != "EXIT" else "EXIT"
        risks.append("Theta Decay Risk (Long in Sideways Market).")

    # D. CONTRARIAN EXIT (Trend Reversal)
    if is_long and is_ce and "DOWN" in regime:
        decision = "EXIT"
        risks.append("Trend Reversed to DOWN.")
    if is_long and is_pe and "UP" in regime:
        decision = "EXIT"
        risks.append("Trend Reversed to UP.")
    
    # E. THESIS FAILURE (Delta)
    if is_long and greeks:
        delta = greeks.get('delta', 0)
        # If Delta is extremely low (Far OTM), report typical lottery ticket status
        if abs(delta) < 0.15 and pnl_pct < 0:
             risks.append("Position is Far OTM (Low Delta).")
             decision = "CAUTION"

    # F. Final Arbitrage
    # If already set to EXIT, stick to it.
    if decision == "EXIT":
        confidence = "HIGH"
    elif decision == "CAUTION":
        confidence = "MEDIUM"
    else:
        # HOLD
        if trend_aligned and pnl_pct > -5:
            confidence = "HIGH"
        else:
            confidence = "LOW"
            
    # Logic Refinement: If EXIT/CAUTION, the "Primary Reason" should be the Risk, not the Trend.
    final_primary_reason = "Monitoring..."
    if decision in ["EXIT", "CAUTION"] and risks:
        final_primary_reason = risks[0] # The main reason for the warning/exit
    elif reasons:
        final_primary_reason = reasons[0]

    result = {
        "symbol": symbol,
        "decision": decision,
        "confidence": confidence,
        "pnl_pct": round(pnl_pct, 1),
        "primary_reason": final_primary_reason,
        "supporting_factors": reasons,
        "risk_flags": risks,
        "ltp": ltp
    }
    
    if greeks:
        result["greeks"] = greeks
        
    return result

def get_advice_report(kite=None, positions=None):
    """
    Generates a full text report for all positions.
    """
    if not positions:
        return "No open positions to analyze."
        
    report = ["🛡️ **Position Advisor Report**"]
    
    for pos in positions:
        # Filter for Options/Futures only (ignore equity holdings for now if mixed)
        if "CE" not in pos['tradingsymbol'] and "PE" not in pos['tradingsymbol'] and "FUT" not in pos['tradingsymbol']:
             continue
             
        advice = analyze_position(pos, kite)
        
        icon = "🟢" if advice['decision'] == "HOLD" else "Mj" if advice['decision'] == "CAUTION" else "🔴"
        if advice['decision'] == "CAUTION": icon = "⚠️"
        if advice['decision'] == "DATA_ERROR": icon = "❓"
        
        block = [
            f"{icon} **{advice['decision']}** | {pos['tradingsymbol']}",
            f"   PnL: {advice['pnl_pct']}% | Conf: {advice['confidence']}",
            f"   Reason: {advice['primary_reason']}"
        ]
        
        # Add Greeks info if available
        if "greeks" in advice:
             g = advice["greeks"]
             block.append(f"   📊 Greeks: Δ {g['delta']:.2f} | Θ {g['theta']:.2f}")
             
        if advice['risk_flags']:
            # Make risks cleaner
            for r in advice['risk_flags']:
                block.append(f"   🚩 {r}")
            
        report.append("\n".join(block))
        
    return "\n\n".join(report)

if __name__ == "__main__":
    print("--- Position Advisor Engine (Real Data Run) ---")
    
    try:
        # 1. Initialize Real Kite
        print("[*] Initializing Kite Session from config...")
        kite = kite_data.get_kite()
        
        if not kite:
            print("❌ Failed to initialize Kite. Check config.py credentials.")
            exit()
            
        # 2. Fetch Real Positions
        print("[*] Fetching Open Positions...")
        # Note: We need the full boolean or dict. 
        # kite.positions() returns {'net': [...], 'day': [...]}
        positions = kite.positions()['net']
        
        if not positions:
            print("ℹ️ No open positions found (Net). checking Day positions...")
            positions = kite.positions()['day']
            
        if not positions:
            print("Message: No active positions found in your account.")
        else:
            print(f"[*] Found {len(positions)} positions. Analyzing...\n")
            
            # 3. Analyze
            # We iterate and print detailed individual analysis or just the report
            print("="*60)
            print(get_advice_report(kite, positions))
            print("="*60)
            
    except Exception as e:
        print(f"❌ Error running with real data: {e}")
        print("Tip: Ensure your ACCESS_TOKEN in config.py is valid and active.")
