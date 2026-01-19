import time
import logging
import threading
from collections import deque
import config

# Setup Logging with Algo ID
logging.basicConfig(
    level=logging.INFO,
    format=f'%(asctime)s - [%(levelname)s] - [AlgoID:{config.ALGO_ID}] - %(message)s',
    handlers=[
        logging.FileHandler("trading_bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("OptionsBot")

class RateLimiter:
    """
    Token Bucket or Sliding Window implementation to ensure OPS < 10.
    """
    def __init__(self, max_calls: int, period: float):
        self.max_calls = max_calls
        self.period = period
        self.calls = deque()
        self.lock = threading.Lock()

    def wait_for_token(self):
        with self.lock:
            now = time.time()
            # Remove calls older than the period
            while self.calls and now - self.calls[0] >= self.period:
                self.calls.popleft()
            
            if len(self.calls) >= self.max_calls:
                sleep_time = self.period - (now - self.calls[0])
                logger.warning(f"Rate limit reached. Sleeping for {sleep_time:.2f}s")
                time.sleep(sleep_time)
                # Re-check or just assume we are good now is a simple approach
                # For strictness, we recurse or re-evaluate, but sleep is usually enough
                self.calls.popleft() 
            
            self.calls.append(time.time())

# Global Rate Limiter Instance
exchange_rate_limiter = RateLimiter(max_calls=config.EXCHANGE_MAX_OPS - 1, period=1.0) # Buffer of 1

def validate_ip(current_ip: str):
    """
    Checks if the current machine's IP matches the whitelisted IP.
    """
    if current_ip != config.WHITELISTED_IP:
        logger.critical(f"IP Mismatch! Current: {current_ip}, Allowed: {config.WHITELISTED_IP}")
        return False
    return True
