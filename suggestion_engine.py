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
import telegram_interface


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
    """
    # Initialize Logger if not provided (fallback for legacy calls, though we should always pass it)
    import logger as logger_module
    if 'logger' not in kwargs:
         logger = logger_module.TelegramLogger() # Local instance if none passed
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
        
        # We need kite instance passed to get_ltp or use kite directly here
        spot_price = kite_data.get_ltp(lookup_sym, kite) # This now handles Index Tokens correctly if name matches

    if spot_price is None or spot_price == 0:
        # Try direct generic fetch via token map if name is standard
        spot_price = kite_data.get_ltp(symbol, kite)

    if spot_price is None or spot_price == 0:
        logger.log("[!] Could not fetch Spot Price. Aborting.")
        return

    # 3. New Quantitative Checks
    # OI & IV (REAL)
    pcr = oi_analysis_engine.calculate_pcr(kite, symbol)
    
    # Get ATM to check IV and OI Signal of the "Tradeable" instrument
    atm = atm_engine.get_atm_strike(spot_price, symbol)
    expiry_data = expiry_engine.get_expiry(symbol)
    
    # For IV and OI, we check the ATM CE for Bullish/Bearish context or just generic?
    # User said "get_iv_value" and "IV Rank".
    # We will pick ATM CE as the reference for IV Rank.
    atm_sym_base = expiry_engine.get_option_symbol(symbol, expiry_data['date'], atm, "CE")
    atm_sym = "NFO:" + atm_sym_base
    
    iv = kite_data.get_iv_value(kite, atm_sym)
    if iv: oi_analysis_engine.update_iv_history(symbol, iv)
    iv_rank = oi_analysis_engine.calculate_iv_rank(symbol)
    
    # OI Signal (Using Delta)
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
    logger.log(f"Capital: {capital} | Avail Margin: {margin}")
    
    # Decide Strategy
    final_view = "BULLISH" # Default logic from trend/pcr
    if "DOWN" in trend_dir: final_view = "BEARISH"
    elif "UP" in trend_dir: final_view = "BULLISH"
    else:
        if pcr < 0.8: final_view = "BEARISH"
        else: final_view = "BULLISH"
        
    logger.log(f"[-] Final View: {final_view}")
    
    # ----------------------------------------------------
    # DO-NOT-TRADE (DNT) DETECTOR
    # ----------------------------------------------------
    import dnt_engine
    
    # Needs: regime, volatility, trend, spot, iv_rank
    # Infer regime str like before
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
        logger.log(f"   Note: {dnt_res['notes']}")
        return
    
    # ----------------------------------------------------
    # HIGH IV STRATEGY SWITCH (Force Credit)
    # ----------------------------------------------------
    # Logic: IF IV > HV+20% OR IVRank > 80 => VETO LONG
    # We enforce this by hijacking the logic flow below.
    
    # Get HV from metrics
    raw_hv = metrics.get('hv', 0)
    current_iv = iv if iv else 0
    
    high_iv_condition = False
    
    # Check IV vs HV (20% buffer -> 1.2x)
    # HV is annualized %. IV is annualized %.
    if current_iv > (raw_hv * 1.2):
        high_iv_condition = True
        logger.log(f"[!] High IV Detected: IV {current_iv:.1f} > HV {raw_hv:.1f} + 20%")
        
    if iv_rank > 80:
        high_iv_condition = True
        logger.log(f"[!] Extreme IV Rank Detected: {iv_rank}")
        
    if high_iv_condition:
        logger.log(">>> FORCING SYSTEM TO CREDIT STRATEGIES (SELLING) <<<")
        logger.log(">>> Long Option Entries will be VETOED/SKIPPED.")
    
    dnt_res = dnt_engine.check_dnt(dnt_context)
    
    if dnt_res['do_not_trade']:
        logger.log("\n🛑 DO-NOT-TRADE ACTIVE")
        logger.log(f"   Reason: {dnt_res['primary_reason']} ({dnt_res['risk_category']})")
        logger.log(f"   Note: {dnt_res['notes']}")
        return
    
    # ----------------------------------------------------
    # EXPECTED MOVE MATH GATE
    # ----------------------------------------------------
    import expected_move_engine
    import greeks_engine
    
    # We need Greeks for ATM to evaluate general expectancy
    # Get Market Metrics from engine (now exposed)
    metrics = market_regime_engine.get_market_metrics(symbol if "NIFTY" in symbol else "NIFTY")
    metrics['spot_price'] = spot_price
    metrics['regime'] = regime_str
    
    # Fetch ATM Greeks proxy
    atm = atm_engine.get_atm_strike(spot_price, symbol)
    expiry_data = expiry_engine.get_expiry(symbol)
    
    # Use generic calls to greeks_engine for quick check
    # Need time to expiry
    dte = greeks_engine.calculate_time_to_expiry(expiry_data['date'])
    # Assume 15% IV if missing for check or use fetched IV
    check_iv = iv if iv else 0.15 
    # Option Type for View
    check_type = "CE" if final_view == "BULLISH" else "PE"
    
    # Calc Greeks
    # S, K, T, r, sigma, type
    greeks_proxy = greeks_engine.get_greeks(spot_price, atm, dte, 0.07, check_iv, check_type)
    greeks_proxy['iv'] = check_iv * 100 # scale up
    
    # Candidate Proxy
    # Need rough premium. 
    # Use Black Scholes price from Greeks or just fetch?
    # Fetching is safer.
    check_sym_base = expiry_engine.get_option_symbol(symbol, expiry_data['date'], atm, check_type)
    check_sym = "NFO:" + check_sym_base
    check_prem = kite_data.get_ltp(check_sym, kite) # Helper wrapper
    
    if check_prem:
        check_cand = {"premium": check_prem, "type": check_type, "strike": atm}
        
        math_res = expected_move_engine.evaluate_expectancy(check_cand, metrics, greeks_proxy)
        
        logger.log("\n--- EXPECTANCY CHECK ---")
        if not math_res['allowed']:
             logger.log(f"📉 MATH VETO: {math_res['decision_reason']}")
             logger.log(f"   ExpMove: {math_res['expected_spot_move']} vs Cost: {math_res['expected_cost']}")
             logger.log("   Trade has negative mathematical edge. ABORTING.")
             return
        else:
             logger.log(f"✅ PASSED Edge Ratio: {math_res['edge_ratio']}")
    
    # Strike Integration
    atm = atm_engine.get_atm_strike(spot_price, symbol)
    expiry_data = expiry_engine.get_expiry(symbol)
    
    final_trade_legs = []
    
    # --- STRATEGY ROUTING BASED ON MARGIN & CAPITAL ---
    # UPDATED LOGIC (Prioritize Margin Availability):
    # Margin >= 1.5L : Option Selling (Best Probability)
    # Margin >= 50k  : Hedged Spreads (Balanced)
    # Margin < 50k   : Buy Options (Low Capital/Margin)
    
    # Defaults
    is_hedged = False
    strategy_name = ""
    
    if margin >= 150000:
        # HIGH MARGIN -> Sell Strategies
        logger.log(f"[-] High Margin (>=1.5L). Strategy: OPTION SELLING")
        # Invert View for Selling
        sell_type = "PE" if final_view == "BULLISH" else "CE"
        action = "SELL"
        opt_type = sell_type 
        
        # STRICT SYMBOL CONSTRUCTION
        # Format: <UNDERLYING><YY><MON><STRIKE><CE/PE>
        sym_base = expiry_engine.get_option_symbol(symbol, expiry_data['date'], atm, sell_type)
        sym = "NFO:" + sym_base
        
        # 1. FIX LTP + VALIDATION
        prem = validate_option(sym, kite)
        
        # 8. DO NOT PLACE TRADES WITHOUT VALID LTP
        if prem is None:
            logger.log(f"[!] Validation Failed for {sym}. Abort trade.")
            return

        # Check Margin again
        est_margin = margin_engine.estimate_short_margin(symbol, atm, prem)
        lots = int(margin / est_margin) if est_margin > 0 else 0
        
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
        
        # If Strategy is WAIT, abort
        if strategy_name == "WAIT":
             return
        
        # Construct Legs
        for leg in hedged_strat['legs']:
            # STRICT SYMBOL
            leg_sym_base = expiry_engine.get_option_symbol(symbol, expiry_data['date'], leg['strike'], leg['type'])
            leg_sym = "NFO:" + leg_sym_base
            
            prem = validate_option(leg_sym, kite)
            if prem is None:
                logger.log(f"[!] Validation Failed for {leg_sym}. Skipping Leg.")
                # We should strictly abort the whole strategy if one leg fails validation to avoid naked positions
                logger.log("[!] Strategy Aborted due to leg failure.")
                return 
                
            final_trade_legs.append({
                "action": leg['action'], "symbol": leg_sym,
                "strike": leg['strike'], "type": leg['type'],
                "qty": leg['quantity'] * (50 if "NIFTY" in symbol else 15), # 1 Lot approx
                "premium": prem
            })
            
    else:
        # LOW MARGIN -> Buy Cheap OTM/ATM
        
        # --- HIGH IV GUARD ---
        if high_iv_condition:
            logger.log("🚫 SKIPPING BUY TRADE: High IV requires Credit Strategy, but margin is insufficient (<50k).")
            logger.log("   Remaining Cash/Flat to avoid IV Crush.")
            return

        opt_type = "CE" if final_view == "BULLISH" else "PE"
        logger.log(f"[-] Low Margin (<50k). Strategy: BUY OPTION {opt_type}")
        action = "BUY"
        
        # OTM Engine needs 'kite' passed
        otm_data = otm_engine.find_affordable_otm(capital, symbol, atm, expiry_data, opt_type, kite)
        
        # Validate the OTM pick
        if otm_data["premium"] is None or otm_data["premium"] == 0:
             logger.log("[!] No valid premium found for Buying. Abort.")
             return
             
        # Double Check Validation on the found symbol
        # OTM engine might have returned a symbol, but we need to check Vol/OI
        check_prem = validate_option(otm_data["symbol"], kite)
        if not check_prem:
             logger.log("[!] Selected OTM failed strict validation (Vol/OI).")
             return

        final_trade_legs.append({
            "action": "BUY", "symbol": otm_data["symbol"], 
            "strike": otm_data["strike"], "type": opt_type, 
            "qty": otm_data["qty"], 
            "premium": otm_data["premium"]
        })
    
    
    # 5. Output Trade Plan
    # ----------------------------------------------------
    # FINAL VETO GATE (Imported Engine)
    # ----------------------------------------------------
    import trade_veto_engine
    
    # Context for Veto
    # Needs: regime, trend, volatility, spot_price, iv_rank
    # We have: trend_dir, volatility, spot_price, iv, iv_rank
    # Get Regime from engine directly or infer?
    # pick_best_symbol returns trend_dir but market_regime_engine returns precise string.
    # Let's simple infer or assume trend_dir contains it slightly.
    # Ideally: market_regime_engine.get_market_regime(symbol) was called?
    # Actually wait, pick_best_symbol logic uses it internally maybe?
    # Let's call it explicitly to be safe for Veto inputs.
    
    regime_str = market_regime_engine.get_market_regime(symbol if "NIFTY" in symbol else "NIFTY") # Proxy
    veto_context = {
        "regime": regime_str,
        "trend": trend_dir,
        "volatility": volatility,
        "spot_price": spot_price,
        "iv_rank": iv_rank if iv_rank else 0
    }
    
    logger.log("\n--- VETO CHECK ---")
    
    # Check each leg
    legs_to_keep = []
    trade_blocked = False
    
    for leg in final_trade_legs:
        # Prepare Candidate Dict
        cand = {
            "symbol": leg['symbol'],
            "action": leg['action'], # BUY/SELL
            "type": leg['type'],     # CE/PE
            "strike": leg['strike'],
            "expiry": expiry_data['date'], # Needs datetime or algo handled
            "premium": leg['premium']
        }
        
        veto_res = trade_veto_engine.check_veto(cand, veto_context, kite)
        
        if veto_res['veto']:
            logger.log(f"🚫 BLOCKED: {leg['symbol']}")
            logger.log(f"   Reason: {veto_res['veto_reason']} ({veto_res['veto_category']})")
            logger.log(f"   Details: {veto_res['details']}")
            trade_blocked = True
            break # Block whole strategy if one leg is bad? Usually yes for single/spreads.
        else:
            logger.log(f"✅ PASSED: {leg['symbol']}")
            legs_to_keep.append(leg)
            
    if trade_blocked:
        logger.log("✋ Trade Aborted due to Veto.")
        return

    # If passed, print plan
    logger.log("\n========================================")
    logger.log(f" TRADE PLAN: {strategy_name if is_hedged else (action + ' ' + opt_type)}")
    logger.log("========================================")
    
    total_cost = 0
    total_margin = 0
    
    for leg in final_trade_legs:
        val = leg['qty'] * leg['premium']

        # Calculate SL/Target for Display
        sl_price = 0
        target_price = 0
        if leg['action'] == "BUY":
            sl_price = leg['premium'] * 0.80   # 20% SL
            target_price = leg['premium'] * 1.30 # 30% Target
            total_cost += val
        else:
            sl_price = leg['premium'] * 1.30   # 30% SL (Short)
            target_price = leg['premium'] * 0.50 # 50% Target (Short)
            total_cost -= val # Premium received
            
            # Simple margin est
            total_margin += 60000 # Rough est per lot short

        logger.log(f"Leg {final_trade_legs.index(leg)+1}: {leg['action']} {leg['symbol']} @ {leg['premium']}")
        logger.log(f"       Qty: {leg['qty']} | Val: {val:.2f}")
        logger.log(f"       [SL]: {sl_price:.2f} | [Tgt]: {target_price:.2f}")

        # Store for alert
        leg['sl'] = sl_price
        leg['target'] = target_price
            
    logger.log(f"Net Premium Impact: {total_cost:.2f} ({'Debit' if total_cost > 0 else 'Credit'})")
    logger.log(f"\nEst. Capital/Margin Req: {total_margin if total_margin > 0 else total_cost:.2f}")

    # 7. Send Telegram Alert
    alert_msg = f"🚀 *Trade Suggestion*\n\n"
    alert_msg += f"Symbol: {symbol}\nView: {final_view}\nStrateg: {strategy_name if is_hedged else (action + ' ' + opt_type)}\n"
    alert_msg += f"Spot: {spot_price}\n\n*Legs:*\n"
    for leg in final_trade_legs:
        alert_msg += f"{leg['action']} {leg['symbol']} @ {leg['premium']}\nTo: 🎯 {leg['target']:.1f} | 🛑 {leg['sl']:.1f}\n(Qty: {leg['qty']})\n"
    alert_msg += f"\nEst. Cost: {total_margin if total_margin > 0 else total_cost:.2f}"
    
    telegram_interface.send_alert(alert_msg)
