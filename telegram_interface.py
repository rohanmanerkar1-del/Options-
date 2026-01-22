import requests
import config
import logging

# Setup a local logger for this module to avoid recursion loops 
# (if we used the main logger which uses this module)
logging.basicConfig(level=logging.INFO)
local_logger = logging.getLogger("TelegramInterface")

def send_telegram_message(message):
    """
    Sends a message to the configured Telegram Chat.
    Swallows exceptions to prevent bot crashes.
    """
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        local_logger.warning("Telegram credentials missing in config.py")
        return

    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown" # Optional: Use 'HTML' or None if characters like _ * are issues
    }
    
    try:
        # Timeout is important to avoid hanging the main thread
        response = requests.post(url, json=payload, timeout=5)
        if response.status_code != 200:
            local_logger.error(f"Failed to send Telegram message: {response.text}")
    except Exception as e:
        local_logger.error(f"Telegram connection error: {e}")
