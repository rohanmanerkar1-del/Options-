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

def suggest_trade(capital, margin):
    """
    Analyzes market with Advanced Quantitative Logic.
    Strict Compliance: Zerodha Kite Only.
    """
    print(f"\n--- ZERODHA QUANT OPTION BOT ---")
    
    # 3. Get API Instance
    kite = kite_data.get_kite()
    
    # 1. User Profile
    profile = user_profile.get_user_profile()
    risk_level = profile.get("risk_level", "medium")
    
    # 2. Auto-Selection Execution
    print("[*] Scanning Markets (Trend/Momentum/Volatility)...")
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
        print("[!] Could not fetch Spot Price. Aborting.")
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
    
    print("\n========================================")
    print(f" MARKET CONTEXT: {symbol}")
    print("========================================")
    print(f"Trend      : {trend_dir} (Reason: {reason_msg})")
    print(f"Volatility : {volatility}")
    print(f"Timeframe  : {timeframe}")
    print(f"OI Signal  : {oi_signal} (PCR: {pcr:.2f})")
    print(f"IV Rank    : {iv_rank} (IV: {iv if iv else 'N/A'})")
    print(f"Spot Price : {spot_price}")
    print("========================================")
    print(f"Capital: {capital} | Avail Margin: {margin}")
    
    # Decide Strategy
    final_view = "BULLISH" # Default logic from trend/pcr
    if "DOWN" in trend_dir: final_view = "BEARISH"
    elif "UP" in trend_dir: final_view = "BULLISH"
    else:
        if pcr < 0.8: final_view = "BEARISH"
        else: final_view = "BULLISH"
        
    print(f"[-] Final View: {final_view}")
    
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
        print(f"[-] High Margin (>=1.5L). Strategy: OPTION SELLING")
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
            print(f"[!] Validation Failed for {sym}. Abort trade.")
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
            final_view, capital, margin, symbol, expiry_data, atm
        )
        strategy_name = hedged_strat['name']
        print(f"    -> Suggesting: {strategy_name}")
        print(f"    -> Reason: {hedged_strat['reason']}")
        is_hedged = True
        
        # Construct Legs
        for leg in hedged_strat['legs']:
            # STRICT SYMBOL
            leg_sym_base = expiry_engine.get_option_symbol(symbol, expiry_data['date'], leg['strike'], leg['type'])
            leg_sym = "NFO:" + leg_sym_base
            
            prem = validate_option(leg_sym, kite)
            if prem is None:
                print(f"[!] Validation Failed for {leg_sym}. Skipping Leg.")
                # We should strictly abort the whole strategy if one leg fails validation to avoid naked positions
                print("[!] Strategy Aborted due to leg failure.")
                return 
                
            final_trade_legs.append({
                "action": leg['action'], "symbol": leg_sym,
                "strike": leg['strike'], "type": leg['type'],
                "qty": leg['quantity'] * (50 if "NIFTY" in symbol else 15), # 1 Lot approx
                "premium": prem
            })
            
    else:
        # LOW MARGIN -> Buy Cheap OTM/ATM
        opt_type = "CE" if final_view == "BULLISH" else "PE"
        print(f"[-] Low Margin (<50k). Strategy: BUY OPTION {opt_type}")
        action = "BUY"
        
        # OTM Engine needs 'kite' passed
        otm_data = otm_engine.find_affordable_otm(capital, symbol, atm, expiry_data, opt_type, kite)
        
        # Validate the OTM pick
        if otm_data["premium"] is None or otm_data["premium"] == 0:
             print("[!] No valid premium found for Buying. Abort.")
             return
             
        # Double Check Validation on the found symbol
        # OTM engine might have returned a symbol, but we need to check Vol/OI
        check_prem = validate_option(otm_data["symbol"], kite)
        if not check_prem:
             print("[!] Selected OTM failed strict validation (Vol/OI).")
             return

        final_trade_legs.append({
            "action": "BUY", "symbol": otm_data["symbol"], 
            "strike": otm_data["strike"], "type": opt_type, 
            "qty": otm_data["qty"], 
            "premium": otm_data["premium"]
        })
    
    # 5. Output Trade Plan
    print("\n========================================")
    print(f" TRADE PLAN: {strategy_name if is_hedged else (action + ' ' + opt_type)}")
    print("========================================")
    
    total_cost = 0
    total_margin = 0
    
    for leg in final_trade_legs:
        val = leg['qty'] * leg['premium']
        print(f"Leg {final_trade_legs.index(leg)+1}: {leg['action']} {leg['symbol']} @ {leg['premium']}")
        print(f"       Qty: {leg['qty']} | Val: {val:.2f}")
        
        if leg['action'] == "BUY":
            total_cost += val
        else:
            total_cost -= val # Premium received
            
            # Simple margin est
            total_margin += 60000 # Rough est per lot short
            
    print(f"Net Premium Impact: {total_cost:.2f} ({'Debit' if total_cost > 0 else 'Credit'})")
    print(f"\nEst. Capital/Margin Req: {total_margin if total_margin > 0 else total_cost:.2f}")
    
    # 6. Monitor Loop Option
    # ...
