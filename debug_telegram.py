import config
import requests

def debug_bot():
    print("--- TELEGRAM DEBUGGER ---")
    
    # 1. Check Bot Details (getMe)
    url_me = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/getMe"
    try:
        print("[*] Verifying Bot Token...")
        res = requests.get(url_me)
        data = res.json()
        
        if data.get("ok"):
            bot_user = data["result"]["username"]
            bot_name = data["result"]["first_name"]
            print(f"✅ Token Valid.")
            print(f"   Bot Name: {bot_name}")
            print(f"   Bot Username: @{bot_user}") 
            print("\nIMPORTANT: Please make sure you have clicked 'START' on THIS exact bot.")
        else:
            print(f"❌ Invalid Token. Error: {data}")
            return
            
    except Exception as e:
        print(f"❌ Connection Error: {e}")
        return

    # 2. Try Sending Message
    print(f"\n[*] Attempting to send message to Chat ID: {config.TELEGRAM_CHAT_ID}...")
    url_send = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "text": "🔍 Debug Test Message",
    }
    
    res = requests.post(url_send, json=payload)
    data = res.json()
    
    if data.get("ok"):
        print("✅ Message Sent Successfully!")
    else:
        print(f"❌ Failed to send message.")
        print(f"   Error: {data.get('description')}")
        print("   Possible reasons:")
        print("   1. You haven't clicked START on the bot yet.")
        print(f"   2. The Chat ID {config.TELEGRAM_CHAT_ID} is incorrect.")

if __name__ == "__main__":
    debug_bot()
