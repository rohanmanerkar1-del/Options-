from datetime import datetime
from config import Config
from utils import logger

class ShortStraddleStrategy:
    def __init__(self, broker, risk_manager):
        self.broker = broker
        self.risk_manager = risk_manager
        self.state = "WAITING" # WAITING, IN_POSITION, COMPLETED
        self.positions = {} # {symbol: {'entry_price': x, 'sl': y, 'target': z, 'qty': q}}
        self.pnl_locked = 0.0

    def get_atm_strike(self, spot_price, step=50):
        return round(spot_price / step) * step

    def execute(self):
        now = datetime.now()
        current_time_str = now.strftime("%H:%M")

        if self.state == "WAITING":
            # If Mock mode, we might want to trigger immediately for testing
            if Config.USE_MOCK_BROKER or current_time_str == Config.STRATEGY_TIME:
                self.enter_positions()
        
        elif self.state == "IN_POSITION":
            self.monitor_positions()
            
            # End of day exit (e.g., 15:15)
            if current_time_str >= "15:15":
                self.exit_all_positions("EOD Exit")

    def enter_positions(self):
        logger.info("Strategy Triggered: 9:20 Short Straddle")
        
        # Get Nifty Spot Price (Symbol token for Nifty 50 might vary, using dummy logic or broker call)
        # Note: Implement get_ltp accordingly. Assuming "NIFTY" works or we pass token.
        # Here we mock for logic flow or assume broker handles name resolution
        nifty_ltp = self.broker.get_ltp("NSE", "99926000", "Nifty 50") # Example token
        
        if not nifty_ltp:
            logger.error("Could not fetch Nifty Spot. Strategy Aborted.")
            return

        atm_strike = self.get_atm_strike(nifty_ltp)
        logger.info(f"Nifty Spot: {nifty_ltp}, ATM Strike: {atm_strike}")

        # Construct Symbols (Pseudo-code logic for symbol construction)
        # In real API you need to lookup tokens for "NIFTY 24JAN26 21000 CE"
        # We will assume we found them
        ce_symbol = f"NIFTY {atm_strike} CE" 
        pe_symbol = f"NIFTY {atm_strike} PE"
        # You would need a symbol mapper to get tokens here.
        # For this framework, let's pretend we have them.
        ce_token = "12345" 
        pe_token = "12346"

        qty = Config.MAX_POSITION_SIZE # Or define specific lot size logic

        # Place Orders via Risk Manager
        if self.risk_manager.check_trade_limits(qty):
            ce_order = self.broker.place_order("SELL", "NFO", ce_token, qty, "INTRADAY", "MARKET", 0, ce_symbol)
            pe_order = self.broker.place_order("SELL", "NFO", pe_token, qty, "INTRADAY", "MARKET", 0, pe_symbol)
            
            if ce_order and pe_order:
                self.state = "IN_POSITION"
                # Fetch entry prices to set SL/TP
                ce_entry_price = self.broker.get_ltp("NFO", ce_token, ce_symbol) or 0
                pe_entry_price = self.broker.get_ltp("NFO", pe_token, pe_symbol) or 0
                
                self.positions[ce_symbol] = {
                    'token': ce_token, 'type': 'CE', 'qty': qty, 'entry': ce_entry_price,
                    'sl': ce_entry_price + Config.STOP_LOSS_PER_LOT, # Simplified point based SL
                    'target': ce_entry_price - Config.TARGET_PROFIT_PER_LOT # Shorting, so lower is better
                }
                self.positions[pe_symbol] = {
                    'token': pe_token, 'type': 'PE', 'qty': qty, 'entry': pe_entry_price,
                    'sl': pe_entry_price + Config.STOP_LOSS_PER_LOT, 
                    'target': pe_entry_price - Config.TARGET_PROFIT_PER_LOT 
                }
                logger.info(f"Entered Positions. CE Entry: {ce_entry_price}, PE Entry: {pe_entry_price}")

    def monitor_positions(self):
        if not self.positions:
            self.state = "COMPLETED"
            return
            
        total_mtm = 0
        keys_to_remove = []
        
        for symbol, pos in self.positions.items():
            ltp = self.broker.get_ltp("NFO", pos['token'], symbol)
            if not ltp: continue
            
            # Update MTM (Short position: Entry - LTP)
            # This is per unit. Total MTM = (Entry - LTP) * Qty
            pnl = (pos['entry'] - ltp) * pos['qty']
            total_mtm += pnl
            
            # Check SL
            if ltp >= pos['sl']:
                logger.info(f"SL Hit for {symbol}. LTP: {ltp}, SL: {pos['sl']}")
                self.broker.place_order("BUY", "NFO", pos['token'], pos['qty'], "INTRADAY", "MARKET", 0, symbol)
                keys_to_remove.append(symbol)
            
            # Check Target
            elif ltp <= pos['target']:
                logger.info(f"Target Hit for {symbol}. LTP: {ltp}, Target: {pos['target']}")
                self.broker.place_order("BUY", "NFO", pos['token'], pos['qty'], "INTRADAY", "MARKET", 0, symbol)
                keys_to_remove.append(symbol)
                
        # Clean up closed positions
        for k in keys_to_remove:
            del self.positions[k]
            
        self.risk_manager.update_pnl(total_mtm + self.pnl_locked)

    def exit_all_positions(self, reason="Force Exit"):
        logger.info(f"Exiting all positions: {reason}")
        for symbol, pos in self.positions.items():
             self.broker.place_order("BUY", "NFO", pos['token'], pos['qty'], "INTRADAY", "MARKET", 0, symbol)
        self.positions.clear()
        self.state = "COMPLETED"
