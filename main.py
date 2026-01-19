from suggestion_engine import suggest_trade
import kite_data
import market_regime_engine
import greeks_engine
import datetime
import time

# ------------------------------------------------------------------------
# HOLD-TIME RECOMMENDATION ENGINE
# ------------------------------------------------------------------------
class HoldTimeAdvisor:
    def __init__(self):
        self.kite = kite_data.get_kite()
        # Cache for order times to avoid repetitive API calls
        self.entry_time_cache = {} 
        
    def get_entry_time(self, symbol):
        """
        Attempts to find the latest filled order time for this symbol.
        """
        if symbol in self.entry_time_cache:
            return self.entry_time_cache[symbol]
            
        try:
            orders = self.kite.orders()
            # Sort by time desc
            # Find last COMPLETED order for this symbol
            for o in reversed(orders):
                if o['tradingsymbol'] == symbol and o['status'] == 'COMPLETE':
                    # Store as object
                    limit_time = o['order_timestamp']
                    self.entry_time_cache[symbol] = limit_time
                    return limit_time
        except Exception as e:
            print(f"[!] Error fetching orders: {e}")
            
        return None

    def analyze_position(self, pos):
        """
        Analyzes a SINGLE position for Time-based guidance.
        """
        symbol = pos['tradingsymbol']
        qty = pos['quantity']
        
        # 1. Determine Time Held
        entry_time = self.get_entry_time(symbol)
        time_held_min = 0
        if entry_time:
            now = datetime.datetime.now(entry_time.tzinfo) # Match timezone
            diff = now - entry_time
            time_held_min = int(diff.total_seconds() / 60)
        else:
            # Fallback if no order found (e.g. carried over)
             pass 

        # 2. Market Context
        # Determine Underlying
        underlying = "NIFTY"
        if "BANKNIFTY" in symbol: underlying = "BANKNIFTY"
        elif "FINNIFTY" in symbol: underlying = "FINNIFTY"
        
        regime = market_regime_engine.get_market_regime(underlying)
        
        # 3. Base Patience Window
        # TREND: 60-90m, VOLATILE: 30-45m, RANGE: 15-25m
        base_patience = 25 # Default (RANGE)
        if "TREND" in regime: base_patience = 75 # Avg of 60-90
        elif "VOLATILE" in regime: base_patience = 40
        else: base_patience = 20
        
        # 4. Adjustments
        adjustments = []
        patience_score = 0
        
        # A. Greeks Logic
        details = kite_data.get_instrument_detail(symbol)
        greeks = {}
        if details:
            S = kite_data.get_ltp(underlying, self.kite) or 0
            K = details.get("strike", 0)
            T = greeks_engine.calculate_time_to_expiry(details.get("expiry"))
            sigma = kite_data.get_iv_value(self.kite, symbol)
            if not sigma: sigma = 20
            sigma = sigma / 100.0
            
            option_type = "CE" if "CE" in symbol else "PE"
            greeks = greeks_engine.get_greeks(S, K, T, 0.07, sigma, option_type)
            
            # Theta Adjustment:
            # If Theta is high (near expiry), reduce patience
            theta = greeks.get('theta', 0)
            if abs(theta) > 15: # Arbitrary high decay
                patience_score -= 15
                adjustments.append(f"High Theta Decay ({theta:.1f})")
            
            # Delta Adjustment:
            # If Delta is moving in favor (Spot Progress), increase patience
            # We assume current PnL reflects this roughly or check underlying trend
            delta = greeks.get('delta', 0)
            is_long = qty > 0
            
            # Spot Trend Check
            u_ltp = S
            # We don't have entry spot easily unless we cached it. 
            # We rely on Regime.
            if is_long:
                 if ("UP" in regime and "CE" in symbol) or ("DOWN" in regime and "PE" in symbol):
                     patience_score += 20
                     adjustments.append("Trend Supports Position")
                 elif regime == "SIDEWAYS":
                     patience_score -= 10
                     adjustments.append("Sideways Market (Decay Risk)")
        
        dfe = 0 # Days from Expiry
        if details:
             dfe = greeks_engine.calculate_time_to_expiry(details.get("expiry")) * 365
             
        # New Rule: IF DTE <= 7 AND Long -> Max Hold 30m
        if dfe <= 7.0 and qty > 0:
            if recommended > 30:
                recommended = 30
                adjustments.append(f"Capped at 30m (DTE {dfe:.1f} <= 7)")

        # 5. Calculate Final Recommended Hold Time
        # recommended = base_patience + patience_score ... (Already calculated above, we just capped it)
        # Clamp Logic checks
        recommended = max(10, min(recommended, 120))
        
        # LOGIC MATRIX
        safe_regime = ("TRENDING" in regime)
        safe_pnl = (current_pnl_pct > 1.0) # At least 1% buffer
        safe_dte = (dfe >= 2.0) # Not expiring tomorrow/today
        
        if not safe_dte:
            overnight_decision = "AVOID OVERNIGHT"
            overnight_reason = f"Expiry too close ({dfe:.1f} days). Gamma/Theta risk."
        elif "SIDEWAYS" in regime:
            overnight_decision = "AVOID OVERNIGHT"
            overnight_reason = "Market is Sideways/Range-bound. Decay risk."
        elif current_pnl_pct < -2.0:
            overnight_decision = "AVOID OVERNIGHT"
            overnight_reason = f"Negative PnL ({current_pnl_pct:.1f}%). Thesis failing."
        else:
            # Regime is Trending or Volatile, DTE is safe, PnL is decent or flat
            if safe_regime and safe_pnl:
                overnight_decision = "HOLD OVERNIGHT"
                overnight_reason = f"Strong Regime ({regime}) + Profit Buffer ({current_pnl_pct:.1f}%)."
            elif safe_regime and (current_pnl_pct > -2.0 and current_pnl_pct <= 1.0):
                 overnight_decision = "CONDITIONAL HOLD"
                 overnight_reason = "Trend exists but PnL buffer is thin."
                 overnight_conditions = "Requires strong opening or Gap Up tomorrow."
            else:
                 overnight_reason = "Mixed signals."
                 overnight_conditions = "Verify Global cues before carry."

        # --------------------------------------------------------
        # NEW RULE: FORCE EXIT IF LONG AND TIME >= 15:15
        # --------------------------------------------------------
        now = datetime.datetime.now()
        current_time_str = now.strftime("%H:%M")
        
        if qty > 0 and current_time_str >= "15:15":
            overnight_decision = "FORCE EXIT (DO NOT CARRY)"
            overnight_reason = "Mandatory Intraday Exit Rule (Time > 3:15 PM)."
            overnight_conditions = "Close Immediately."
            recommended = 0 # Force intraday expiry
            remaining = 0

        return {
            "symbol": symbol,
            "regime": regime,
            "time_held": time_held_min,
            "recommended_hold": recommended,
            "remaining": remaining,
            "confidence": confidence,
            "adjustments": adjustments,
            "overnight": {
                "decision": overnight_decision,
                "reason": overnight_reason,
                "conditions": overnight_conditions
            }
        }

    def run_report(self):
        print("\n[*] Fetching Positions for Time Analysis...")
        try:
             positions = self.kite.positions()['net']
        except:
             print("[!] Error fetching positions.")
             return

        if not positions:
            print("[i] No open positions.")
            return

        print("\n" + "="*60)
        print(" ⏳ HOLD-TIME & OVERNIGHT ADVISOR")
        print("="*60)
        
        for pos in positions:
            if pos['quantity'] == 0: continue
            # Filter options
            if "CE" not in pos['tradingsymbol'] and "PE" not in pos['tradingsymbol']: continue
            
            res = self.analyze_position(pos)
            
            color = "\033[92m" # Green
            if res['remaining'] < 5: color = "\033[91m" # Red
            elif res['remaining'] < 15: color = "\033[93m" # Yellow
            RESET = "\033[0m"
            
            print(f"Symbol: {res['symbol']}")
            print(f"Regime: {res['regime']}")
            print(f"Time Held: {res['time_held']}m")
            print(f"{color}Intraday Hold: {res['recommended_hold']}m (Remaining: {res['remaining']}m){RESET}")
            if res['adjustments']:
                print(f"Notes: {', '.join(res['adjustments'])}")
            
            # Overnight Section
            od = res['overnight']
            ocolor = "\033[91m" # Red (Avoid)
            if "HOLD" in od['decision']: ocolor = "\033[92m"
            if "CONDITIONAL" in od['decision']: ocolor = "\033[93m"
            
            print(f"{ocolor}Overnight: {od['decision']}{RESET}")
            print(f"   Reason: {od['reason']}")
            if od['conditions']:
                print(f"   Condition: \033[3m{od['conditions']}{RESET}")
            print("-" * 40)

# ------------------------------------------------------------------------
# MAIN ENTRY
# ------------------------------------------------------------------------
def main():
    print("\n--- ZERODHA ALGO TRADER ---")
    while True:
        print("\n1. Suggest New Trade (Scanner)")
        print("2. Analyze Open Positions (Hold-Time Advisor)")
        print("3. Exit")
        
        choice = input("Select Option: ")
        
        if choice == "1":
            try:
                capital = float(input("Enter Your Capital (INR): "))
                margin = float(input("Enter Available Margin (INR): "))
                suggest_trade(capital, margin)
            except ValueError as e:
                print(f"[!] Invalid input: {e}")
        
        elif choice == "2":
            advisor = HoldTimeAdvisor()
            advisor.run_report()
            
        elif choice == "3":
            print("Exiting...")
            break
        else:
            print("Invalid Choice.")
            
if __name__ == "__main__":
    main()
