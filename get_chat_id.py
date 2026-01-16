import config
import requests
import json

def get_chat_id():
    print("--- FETCHING CHAT ID ---")
    token = config.TELEGRAM_BOT_TOKEN
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    
    try:
        print(f"[*] Polling {url}...")
        res = requests.get(url)
        data = res.json()
        
        if not data.get("ok"):
            print(f"❌ Error fetching updates: {data}")
            return

        updates = data.get("result", [])
        if not updates:
            print("[-] No messages found. Please send 'Hello' to your bot again.")
            return

        # Get last message
        last_update = updates[-1]
        if "message" in last_update:
            chat = last_update["message"]["chat"]
            chat_id = chat["id"]
            username = chat.get("username", "Unknown")
            first_name = chat.get("first_name", "Unknown")
            
            print(f"\n✅ FOUND MESSAGE FROM:")
            print(f"   Name: {first_name}")
            print(f"   Username: @{username}")
            print(f"   Chat ID: {chat_id}")
            print(f"   Text: {last_update['message'].get('text', '')}")
            
            print(f"\n[+] Recommended Action: Update config.py with TELEGRAM_CHAT_ID = {chat_id}")
            return chat_id
        else:
            print("[-] Last update was not a text message.")
            
    except Exception as e:
        print(f"❌ Connection Error: {e}")

if __name__ == "__main__":
    get_chat_id()
