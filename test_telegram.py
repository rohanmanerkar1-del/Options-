import config
import requests
import sys

def test_alert():
    print(f"Testing Telegram Alert...")
    print(f"Token: {config.TELEGRAM_BOT_TOKEN[:10]}...")
    print(f"Chat ID: {config.TELEGRAM_CHAT_ID}")

    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "text": "✅ *Test Message from Zerodha Bot*\nIf you see this, integration is working!",
        "parse_mode": "Markdown"
    }
    
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            print("TEST_RESULT: PASS")
        else:
            print(f"TEST_RESULT: FAIL ({response.status_code})")
            print(response.text)
    except Exception as e:
        print(f"TEST_RESULT: ERROR {e}")

if __name__ == "__main__":
    test_alert()
