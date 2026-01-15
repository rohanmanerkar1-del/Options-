from abc import ABC, abstractmethod

class BrokerInterface(ABC):
    """
    Abstract Interface for Brokerage APIs to ensure modularity.
    """
    
    @abstractmethod
    def login(self):
        """Authenticates the session."""
        pass
    
    @abstractmethod
    def logout(self):
        """Closes the session safely."""
        pass
        
    @abstractmethod
    def get_ltp(self, exchange: str, symbol_token: str):
        """Fetches Last Traded Price."""
        pass
        
    @abstractmethod
    def place_order(self, transaction_type: str, exchange: str, symbol_token: str, qty: int, order_type: str, price: float = 0):
        """Places a buy/sell order."""
        pass
        
    @abstractmethod
    def get_positions(self):
        """Fetches current open positions."""
        pass
        
    @abstractmethod
    def get_option_chain_data(self, symbol: str, expiry: str):
        """Fetches option chain relevant data (LTP, OI, Volume)."""
        pass
