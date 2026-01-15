import logging
from kiteconnect import KiteConnect
from config import Config
from broker_interface import BrokerInterface
from utils import logger, exchange_rate_limiter

class ZerodhaAdapter(BrokerInterface):
    def __init__(self):
        self.kite = KiteConnect(api_key=Config.ZERODHA_API_KEY)
        self.access_token = None

    def login(self):
        """
        Zerodha login is interactive (Request Token -> Access Token).
        For automated login, user typically needs to handle the Request Token flow freshly
        or use a stored access token if validity persists (1 day).
        """
        try:
            print("To login to Zerodha:")
            print(f"1. Login to: {self.kite.login_url()}")
            request_token = input("2. Enter the 'request_token' from the redirect URL: ").strip()
            
            data = self.kite.generate_session(request_token, api_secret=Config.ZERODHA_API_SECRET)
            self.kite.set_access_token(data["access_token"])
            self.access_token = data["access_token"]
            
            logger.info("Zerodha Login Successful")
            return True
        except Exception as e:
            logger.error(f"Zerodha Login Failed: {e}")
            return False

    def logout(self):
        try:
            # self.kite.invalidate_access_token() # Optional
            logger.info("Zerodha Session Closed (Local)")
        except Exception as e:
            logger.error(f"Logout Failed: {e}")

    def get_ltp(self, exchange, symbol_token, symbol_name):
        """
        Zerodha uses 'Exchange:Symbol' format for fetching LTP.
        Example: 'NSE:NIFTY 50', 'NFO:NIFTY24JAN21500CE'
        """
        exchange_rate_limiter.wait_for_token()
        try:
            # Construct instrument id
            # If symbol_name is "NIFTY 50", we use "NSE:NIFTY 50"
            # If it's an option like "NIFTY 21000 CE", we need "NFO:..."
            # For simplicity, assuming symbol_name is passed in correct Kite format or we prepend
            
            instrument = f"{exchange}:{symbol_name}"
            quote = self.kite.ltp(instrument)
            
            if instrument in quote:
                return quote[instrument]['last_price']
            else:
                logger.warning(f"LTP not found for {instrument}")
                return None
        except Exception as e:
            logger.error(f"Error fetching LTP for {symbol_name}: {e}")
            return None

    def place_order(self, transaction_type, exchange, symbol_token, qty, product_type, order_type="MARKET", price=0, symbol_name=""):
        """
        transaction_type: 'BUY' or 'SELL'
        """
        exchange_rate_limiter.wait_for_token()
        
        # Kite Constants
        trans_type = self.kite.TRANSACTION_TYPE_BUY if transaction_type == "BUY" else self.kite.TRANSACTION_TYPE_SELL
        prod_type = self.kite.PRODUCT_MIS if product_type == "INTRADAY" else self.kite.PRODUCT_NRML
        ord_type = self.kite.ORDER_TYPE_MARKET if order_type == "MARKET" else self.kite.ORDER_TYPE_LIMIT
        
        try:
            order_id = self.kite.place_order(
                tradingsymbol=symbol_name,
                exchange=exchange,
                transaction_type=trans_type,
                quantity=qty,
                variety=self.kite.VARIETY_REGULAR,
                order_type=ord_type,
                product=prod_type,
                price=price,
                validity=self.kite.VALIDITY_DAY,
                tag=Config.ALGO_ID
            )
            logger.info(f"Order Placed: {transaction_type} {qty} x {symbol_name}. Order ID: {order_id}")
            return order_id
        except Exception as e:
            logger.error(f"Order Placement Failed: {e}")
            return None

    def get_positions(self):
        exchange_rate_limiter.wait_for_token()
        try:
            # Kite returns {'net': [], 'day': []}
            kite_pos = self.kite.positions()
            
            # Adapt to internal contract (list of positions under 'data')
            # Angel One uses 'netqty', Kite uses 'quantity' (for net positions)
            adapted_data = []
            if 'net' in kite_pos:
                for pos in kite_pos['net']:
                    adapted_pos = {
                        'tradingsymbol': pos['tradingsymbol'],
                        'symboltoken': pos['instrument_token'], # Kite uses instrument_token
                        'exchange': pos['exchange'],
                        'netqty': pos['quantity'], # Net quantity
                        'ltp': pos['last_price'],
                        'producttype': pos['product']
                    }
                    adapted_data.append(adapted_pos)
            
            return {"data": adapted_data}
        except Exception as e:
            logger.error(f"Error fetching positions: {e}")
            return None

    def get_option_chain_data(self, symbol, expiry):
        # Zerodha api doesn't directly give full chain.
        return {}
