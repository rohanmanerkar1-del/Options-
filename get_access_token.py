from kiteconnect import KiteConnect
import config
import os

def generate_token():
    print("Initializing KiteConnect...")
    try:
        kite = KiteConnect(api_key=config.API_KEY)
        
        url = kite.login_url()
        print("\n" + "="*50)
        print("STEP 1: LOGIN")
        print("="*50)
        print("Open this URL in your browser to login:")
        print(f"\n{url}\n")
        print("="*50)
        
        print("\nSTEP 2: GET REQUEST TOKEN")
        print("After login, you will be redirected to a URL (e.g. 127.0.0.1).")
        print("Copy the 'request_token' parameter from that URL.")
        
        req_token = input("\nPaste the 'request_token' here: ").strip()
        
        print("\nSTEP 3: GENERATING SESSION...")
        data = kite.generate_session(req_token, api_secret=config.API_SECRET)
        access_token = data["access_token"]
        
        print("\n" + "="*50)
        print("SUCCESS! NEW ACCESS TOKEN")
        print("="*50)
        print(f"\n{access_token}\n")
        
        # Auto-update config.py
        update = input("Do you want me to update config.py automatically? (Y/N): ").upper()
        if update == "Y":
            new_lines = []
            with open("config.py", "r") as f:
                lines = f.readlines()
                for line in lines:
                    if line.startswith("ACCESS_TOKEN"):
                        new_lines.append(f'ACCESS_TOKEN = "{access_token}"\n')
                    else:
                        new_lines.append(line)
            
            with open("config.py", "w") as f:
                f.writelines(new_lines)
            print("Updated config.py successfully!")
            
    except Exception as e:
        print(f"\n[ERROR] Failed to generate token: {e}")

if __name__ == "__main__":
    generate_token()
