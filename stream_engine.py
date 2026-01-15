from kiteconnect import KiteTicker
from config import API_KEY, ACCESS_TOKEN
import logging
import threading
import time

# Global cache for LTP
LTP_CACHE = {}

class StreamEngine:
    def __init__(self):
        self.kws = None
        self.tokens = []
        self.is_connected = False
        self.lock = threading.Lock()
        
    def start(self, tokens_list):
        """
        Starts the KiteTicker in a separate thread.
        """
        self.tokens = tokens_list
        # In a real scenario, we would initialize KiteTicker here
        # self.kws = KiteTicker(API_KEY, ACCESS_TOKEN)
        # self.kws.on_ticks = self.on_ticks
        # self.kws.on_connect = self.on_connect
        # self.kws.connect(threaded=True)
        
        # For now, we simulate a streamer or just rely on API polling
        # as we cannot open a real WebSocket without valid tokens/network in this env.
        print(f"[StreamEngine] Broker Ticker Simulation Started for {len(tokens_list)} tokens.")
        self.is_connected = True
        
    def on_ticks(self, ws, ticks):
        with self.lock:
            for tick in ticks:
                LTP_CACHE[tick['instrument_token']] = tick['last_price']
                
    def on_connect(self, ws, response):
        ws.subscribe(self.tokens)
        ws.set_mode(ws.MODE_LTP, self.tokens)
        
    def get_ltp(self, token):
        start_time = time.time()
        # Return cached if available, else None
        return LTP_CACHE.get(token, None)
        
    def stop(self):
        if self.kws:
            self.kws.close()
            
stream_bot = StreamEngine()
