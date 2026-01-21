import time
import user_profile
import kite_data
import atm_engine
import position_sizing
import market_regime_engine
import strategy_engine
import expiry_engine
import otm_engine
import exit_engine
import trailing_sl_engine
import trade_journal
import margin_engine
from auto_symbol_selector import pick_best_symbol
import oi_analysis_engine
import hedging_engine
import timeframe_engine

import performance_engine


# -------------------------------------------------------------------------
# VALIDATION HELPER
# -------------------------------------------------------------------------
def validate_option(symbol, kite):
    """
    STRICT VALIDATION:
    1. LTP >= 2
    2. Volume >= 5000
    3. OI >= 10000
    """
    data = kite_data.get_real_option_data(symbol, kite)
    if not data:
        print(f"[!] Could not fetch data for {symbol}")
        return None
        
    ltp = data['ltp']
    vol = data['volume']
    oi = data['oi']
    
    if ltp is None or ltp < 2:
        print(f"[!] Invalid Premium: {ltp} (Must be > 2). Skipping {symbol}")
        return None
        
    if vol < 5000:
        print(f"[!] Low Liquidity: Volume {vol} < 5000. Skipping {symbol}")
        return None
        
    if oi < 10000:
        print(f"[!] Insufficient OI: {oi} < 10000. Skipping {symbol}")
        return None
        
    return ltp

def suggest_trade(capital, margin, **kwargs):
    """
    Analyzes market with Advanced Quantitative Logic.
    Strict Compliance: Zerodha Kite Only.
    Returns: Dict { "status": "WAIT"|"TRADE", "reason": str, "data": dict }
    """
    # Initialize Logger
    import logger as logger_module
    if 'logger' not in kwargs:
         logger = logger_module.SimpleLogger() # Local instance
    else:
         logger = kwargs['logger']

    logger.log(f"\n--- ZERODHA QUANT OPTION BOT ---")
    
    # 3. Get API Instance
    kite = kite_data.get_kite()
    
    # 1. User Profile
    profile = user_profile.get_user_profile()
    risk_level = profile.get("risk_level", "medium")
    
    # 2. Auto-Selection Execution
    logger.log("[*] Scanning Markets (Trend/Momentum/Volatility)...")
    symbol, reason_msg, trend_dir, volatility, spot_price = pick_best_symbol()
    
    if spot_price is None or spot_price == 0:
        # Mapping for Indices check
        idx_map = {"NIFTY": "NSE:NIFTY 50", "BANKNIFTY": "NSE:NIFTY BANK", "FINNIFTY": "NSE:NIFTY FIN SERVICE"}
        lookup_sym = idx_map.get(symbol, f"NSE:{symbol}")
        spot_price = kite_data.get_ltp(lookup_sym, kite)

    if spot_price is None or spot_price == 0:
        spot_price = kite_data.get_ltp(symbol, kite)

    if spot_price is None or spot_price == 0:
        msg = f"[!] Could not fetch Spot Price for {symbol}. Aborting."
        logger.log(msg)
        return {"status": "WAIT", "reason": "Data Fetch Failure (Spot Price)"}

    # 3. New Quantitative Checks
    pcr = oi_analysis_engine.calculate_pcr(kite, symbol)
    atm = atm_engine.get_atm_strike(spot_price, symbol)
    expiry_data = expiry_engine.get_expiry(symbol)
    
    if not expiry_data:
        logger.log("[!] Could not determine Expiry.")
        return {"status": "WAIT", "reason": "Data Fetch Failure (Expiry)"}

    atm_sym_base = expiry_engine.get_option_symbol(symbol, expiry_data['date'], atm, "CE")
    atm_sym = "NFO:" + atm_sym_base
    
    iv = kite_data.get_iv_value(kite, atm_sym)
    if iv: oi_analysis_engine.update_iv_history(symbol, iv)
    iv_rank = oi_analysis_engine.calculate_iv_rank(symbol)
    
    # OI Signal
    oi_delta, quote_data = oi_analysis_engine.get_oi_delta(kite, atm_sym)
    net_change = quote_data.get('net_change', 0)
    oi_signal = oi_analysis_engine.interpret_oi_signal(net_change, oi_delta)
    
    # Timeframe
    timeframe = timeframe_engine.pick_timeframe(volatility)
    
    logger.log("\n========================================")
    logger.log(f" MARKET CONTEXT: {symbol}")
    logger.log("========================================")
    logger.log(f"Trend      : {trend_dir} (Reason: {reason_msg})")
    logger.log(f"Volatility : {volatility}")
    logger.log(f"Timeframe  : {timeframe}")
    logger.log(f"OI Signal  : {oi_signal} (PCR: {pcr:.2f})")
    logger.log(f"IV Rank    : {iv_rank} (IV: {iv if iv else 'N/A'})")
    logger.log(f"Spot Price : {spot_price}")
    logger.log("========================================")
    
    # --- PERFORMANCE FEEDBACK INTEGRATION ---
    feedback = performance_engine.get_feedback(current_context={
        "Regime": trend_dir,
        "Strategy": "Trend Following" 
    })
    
    logger.log(f"[Quant] Performance Feedback: {feedback}")
    size_mult = max(0.5, min(1.0, feedback.get('size_multiplier', 1.0)))
    if size_mult < 1.0:
        logger.log(f"[!] Throttling Size by {(1-size_mult)*100:.0f}% due to performance history.")
        
    logger.log(f"Capital: {capital} | Avail Margin: {margin}")
    
    # Decide Strategy
    final_view = "BULLISH"
    if "DOWN" in trend_dir: final_view = "BEARISH"
    elif "UP" in trend_dir: final_view = "BULLISH"
    else:
        if pcr < 0.8: final_view = "BEARISH"
        else: final_view = "BULLISH"
        
    logger.log(f"[-] Final View: {final_view}")

    # --- EXTRA CONFIRMATION CHECK (ADAPTIVE) ---
    if feedback.get('extra_confirmation_required', False):
        logger.log("[!] Performance Engine requires EXTRA CONFIRMATION.")
        if volatility == "Low":
             msg = "[x] Confirmation Failed: Volatility Low + Risk High."
             logger.log(msg)
             return {"status": "WAIT", "reason": "Performance Veto (Low Vol + High Risk)"}
             
        if final_view == "BULLISH" and pcr < 0.9:
             msg = f"[x] Confirmation Failed: PCR {pcr:.2f} too low for Risky Bullish Setup."
             logger.log(msg)
             return {"status": "WAIT", "reason": f"Performance Veto (PCR {pcr:.2f} Low)"}
        if final_view == "BEARISH" and pcr > 1.1:
             msg = f"[x] Confirmation Failed: PCR {pcr:.2f} too high for Risky Bearish Setup."
             logger.log(msg)
             return {"status": "WAIT", "reason": f"Performance Veto (PCR {pcr:.2f} High)"}
             
        logger.log("[v] Extra Confirmation Passed.")

    # ----------------------------------------------------
    # DO-NOT-TRADE (DNT) DETECTOR
    # ----------------------------------------------------
    import dnt_engine
    regime_str = market_regime_engine.get_market_regime(symbol if "NIFTY" in symbol else "NIFTY")
    
    dnt_context = {
        "regime": regime_str,
        "volatility": volatility,
        "trend": trend_dir,
        "spot_price": spot_price,
        "iv_rank": iv_rank
    }
    
    dnt_res = dnt_engine.check_dnt(dnt_context)
    
    if dnt_res['do_not_trade']:
        logger.log("\n🛑 DO-NOT-TRADE ACTIVE")
        logger.log(f"   Reason: {dnt_res['primary_reason']} ({dnt_res['risk_category']})")
        return {"status": "WAIT", "reason": f"DNT: {dnt_res['primary_reason']}"}
    
    # ----------------------------------------------------
    # HIGH IV STRATEGY SWITCH
    # ----------------------------------------------------
    metrics = market_regime_engine.get_market_metrics(symbol if "NIFTY" in symbol else "NIFTY")
    raw_hv = metrics.get('hv', 0)
    current_iv = iv if iv else 0
    
    high_iv_condition = False
    if current_iv > (raw_hv * 1.2):
        high_iv_condition = True
        logger.log(f"[!] High IV Detected: IV {current_iv:.1f} > HV {raw_hv:.1f} + 20%")
    if iv_rank > 80:
        high_iv_condition = True
        logger.log(f"[!] Extreme IV Rank Detected: {iv_rank}")
        
    if high_iv_condition:
        logger.log(">>> FORCING SYSTEM TO CREDIT STRATEGIES (SELLING) <<<")
        logger.log(">>> Long Option Entries will be VETOED/SKIPPED.")
    
    # Double check DNT just in case
    dnt_res = dnt_engine.check_dnt(dnt_context)
    if dnt_res['do_not_trade']:
        return {"status": "WAIT", "reason": f"DNT: {dnt_res['primary_reason']}"}
    
    # ----------------------------------------------------
    # EXPECTED MOVE MATH GATE
    # ----------------------------------------------------
    import expected_move_engine
    import greeks_engine
    
    metrics['spot_price'] = spot_price
    metrics['regime'] = regime_str
    
    atm = atm_engine.get_atm_strike(spot_price, symbol)
    dte = greeks_engine.calculate_time_to_expiry(expiry_data['date'])
    check_iv = iv if iv else 0.15 
    check_type = "CE" if final_view == "BULLISH" else "PE"
    
    greeks_proxy = greeks_engine.get_greeks(spot_price, atm, dte, 0.07, check_iv, check_type)
    greeks_proxy['iv'] = check_iv * 100 
    
    check_sym_base = expiry_engine.get_option_symbol(symbol, expiry_data['date'], atm, check_type)
    check_sym = "NFO:" + check_sym_base
    check_prem = kite_data.get_ltp(check_sym, kite) 
    
    if check_prem:
        check_cand = {"premium": check_prem, "type": check_type, "strike": atm}
        math_res = expected_move_engine.evaluate_expectancy(check_cand, metrics, greeks_proxy)
        
        logger.log("\n--- EXPECTANCY CHECK ---")
        if not math_res['allowed']:
             est_delta = abs(greeks_proxy.get('delta', 0.5))
             gain = math_res['expected_option_gain']
             cost = math_res['expected_cost']
             edge = math_res['edge_ratio']

             logger.log("\n-----------------------------------------------------------")
             logger.log(" ⛔ MATH VETO: Trade has negative mathematical edge.")
             logger.log("-----------------------------------------------------------")
             logger.log(f"Reason: {math_res['decision_reason']}")

             logger.log("\n[WHY WAS THIS VETOED?]")
             logger.log("The Expected Spot Move is not enough to cover the Option Cost")
             logger.log("because options only capture a fraction (Delta) of the move.")

             logger.log(f"\n[THE MATH]")
             logger.log(f"• Spot Move Required : {math_res['expected_spot_move']} pts (Based on Volatility)")
             logger.log(f"• Option Delta       : {est_delta:.2f} (Captures ~{int(est_delta*100)}% of spot move)")
             logger.log(f"• Expected Option Gain ≈ ₹{gain:.2f} (Spot Move * Delta)")
             logger.log(f"• Total Cost/Risk      ≈ ₹{cost:.2f} (Stop Loss + Decay + Slippage)")

             logger.log(f"\n[COMPARISON]")
             logger.log(f"Expected Option Gain (₹{gain:.2f}) < Option Cost (₹{cost:.2f})")
             logger.log(f"Edge = {edge:.2f} means you expect to get ₹{edge:.2f} back for every ₹1 risked.")

             logger.log(f"\n[CONCLUSION]")
             logger.log("This trade is mathematically losing even if direction is correct.")
             logger.log("This setup benefits OPTION SELLERS, not buyers.")

             logger.log(f"\n[WHAT MUST CHANGE?]")
             logger.log("1. Expected Move must increase (Waiting for stronger breakout?)")
             logger.log("2. Option Cost must fall (Wait for pullback/lower premiums?)")
             logger.log("3. Delta must improve (Select a closer strike?)")
             logger.log("-----------------------------------------------------------")
             
             return {"status": "WAIT", "reason": f"Math Veto: {math_res['decision_reason']}"}
        else:
             logger.log(f"✅ PASSED Edge Ratio: {math_res['edge_ratio']}")
    
    # Strike Integration
    atm = atm_engine.get_atm_strike(spot_price, symbol)
    final_trade_legs = []
    
    # Default State
    is_hedged = False
    strategy_name = ""
    
    if margin >= 150000:
        # HIGH MARGIN -> Sell Strategies
        logger.log(f"[-] High Margin (>=1.5L). Strategy: OPTION SELLING")
        sell_type = "PE" if final_view == "BULLISH" else "CE"
        action = "SELL"
        opt_type = sell_type 
        
        sym_base = expiry_engine.get_option_symbol(symbol, expiry_data['date'], atm, sell_type)
        sym = "NFO:" + sym_base
        prem = validate_option(sym, kite)
        
        if prem is None:
            logger.log(f"[!] Validation Failed for {sym}.")
            return {"status": "WAIT", "reason": "Option Validation Failed (LTP/Vol)"}

        est_margin = margin_engine.estimate_short_margin(symbol, atm, prem)
        lots = int(margin / est_margin) if est_margin > 0 else 0
        lots = int(lots * size_mult)
        
        final_trade_legs.append({
            "action": "SELL", "symbol": sym,
            "strike": atm, "type": sell_type,
            "qty": (lots if lots > 0 else 1) * (50 if "NIFTY" in symbol else 15),
            "premium": prem
        })

    elif margin >= 50000:
        # MID MARGIN -> Hedged Spreads
        print(f"[-] Mid Margin (50k-1.5L). Strategy: HEDGED SPREAD")
        hedged_strat = hedging_engine.get_hedged_strategy(
            final_view, capital, margin, symbol, expiry_data, atm,
            iv_rank=(iv_rank if iv_rank else 0)
        )
        strategy_name = hedged_strat['name']
        logger.log(f"    -> Suggesting: {strategy_name}")
        logger.log(f"    -> Reason: {hedged_strat['reason']}")
        is_hedged = True
        
        if strategy_name == "WAIT":
             return {"status": "WAIT", "reason": "Hedge Engine suggested WAIT"}
        
        for leg in hedged_strat['legs']:
            leg_sym_base = expiry_engine.get_option_symbol(symbol, expiry_data['date'], leg['strike'], leg['type'])
            leg_sym = "NFO:" + leg_sym_base
            prem = validate_option(leg_sym, kite)
            if prem is None:
                logger.log(f"[!] Validation Failed for {leg_sym}. Skipping Leg.")
                return {"status": "WAIT", "reason": "Leg Validation Failed (LTP/Vol)"}
                
            final_trade_legs.append({
                "action": leg['action'], "symbol": leg_sym,
                "strike": leg['strike'], "type": leg['type'],
                "qty": int(leg['quantity'] * size_mult) * (50 if "NIFTY" in symbol else 15),
                "premium": prem
            })
            
    else:
        # LOW MARGIN -> Buy Cheap OTM/ATM
        if high_iv_condition:
            logger.log("🚫 SKIPPING BUY TRADE: High IV requires Credit Strategy.")
            return {"status": "WAIT", "reason": "High IV + Low Margin (Cannot Sell)"}

        opt_type = "CE" if final_view == "BULLISH" else "PE"
        logger.log(f"[-] Low Margin (<50k). Strategy: BUY OPTION {opt_type}")
        action = "BUY"
        
        otm_data = otm_engine.find_affordable_otm(capital, symbol, atm, expiry_data, opt_type, kite)
        
        if otm_data["premium"] is None or otm_data["premium"] == 0:
             logger.log("[!] No valid premium found for Buying. Abort.")
             return {"status": "WAIT", "reason": "No Affordable Option Found"}
             
        check_prem = validate_option(otm_data["symbol"], kite)
        if not check_prem:
             logger.log("[!] Selected OTM failed strict validation (Vol/OI).")
             return {"status": "WAIT", "reason": "OTM Validation Failed"}

        final_trade_legs.append({
            "action": "BUY", "symbol": otm_data["symbol"], 
            "strike": otm_data["strike"], "type": opt_type, 
            "qty": int(otm_data["qty"] * size_mult), 
            "premium": otm_data["premium"]
        })
    
    # 5. Output Trade Plan (Veto Check)
    import trade_veto_engine
    
    regime_str = market_regime_engine.get_market_regime(symbol if "NIFTY" in symbol else "NIFTY") 
    veto_context = {
        "regime": regime_str,
        "trend": trend_dir,
        "volatility": volatility,
        "spot_price": spot_price,
        "iv_rank": iv_rank if iv_rank else 0
    }
    
    logger.log("\n--- VETO CHECK ---")
    
    legs_to_keep = []
    trade_blocked = False
    block_reason = ""
    
    for leg in final_trade_legs:
        cand = {
            "symbol": leg['symbol'],
            "action": leg['action'], 
            "type": leg['type'], 
            "strike": leg['strike'],
            "expiry": expiry_data['date'],
            "premium": leg['premium']
        }
        
        veto_res = trade_veto_engine.check_veto(cand, veto_context, kite)
        
        if veto_res['veto']:
            logger.log(f"🚫 BLOCKED: {leg['symbol']}")
            logger.log(f"   Reason: {veto_res['veto_reason']} ({veto_res['veto_category']})")
            trade_blocked = True
            block_reason = veto_res['veto_reason']
            break 
        else:
            logger.log(f"✅ PASSED: {leg['symbol']}")
            legs_to_keep.append(leg)
            
    if trade_blocked:
        logger.log("✋ Trade Aborted due to Veto.")
        return {"status": "WAIT", "reason": f"Veto: {block_reason}"}

    # If passed, print plan
    logger.log("\n========================================")
    logger.log(f" TRADE PLAN: {strategy_name if is_hedged else (action + ' ' + opt_type)}")
    logger.log("========================================")
    
    total_cost = 0
    total_margin = 0
    
    for leg in final_trade_legs:
        val = leg['qty'] * leg['premium']
        sl_price = 0
        target_price = 0
        if leg['action'] == "BUY":
            sl_price = leg['premium'] * 0.80   
            target_price = leg['premium'] * 1.30 
            total_cost += val
        else:
            sl_price = leg['premium'] * 1.30   
            target_price = leg['premium'] * 0.50 
            total_cost -= val 
            total_margin += 60000 

        logger.log(f"Leg {final_trade_legs.index(leg)+1}: {leg['action']} {leg['symbol']} @ {leg['premium']}")
        logger.log(f"       Qty: {leg['qty']} | Val: {val:.2f}")
        logger.log(f"       [SL]: {sl_price:.2f} | [Tgt]: {target_price:.2f}")

        leg['sl'] = sl_price
        leg['target'] = target_price
            
    logger.log(f"Net Premium Impact: {total_cost:.2f} ({'Debit' if total_cost > 0 else 'Credit'})")
    logger.log(f"\nEst. Capital/Margin Req: {total_margin if total_margin > 0 else total_cost:.2f}")

    return {
        "status": "TRADE", 
        "reason": "All Conditions Met",
        "data": {
            "strategy": strategy_name if is_hedged else f"{action} {opt_type}",
            "cost": total_cost,
            "margin": total_margin,
            "legs": final_trade_legs
        }
    }

