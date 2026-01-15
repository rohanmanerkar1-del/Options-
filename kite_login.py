import logging
from kiteconnect import KiteConnect
import config

# Configure logging
logging.basicConfig(level=logging.INFO)

def get_login_url():
    kite = KiteConnect(api_key=config.API_KEY)
    return kite.login_url()

def generate_access_token(request_token):
    try:
        kite = KiteConnect(api_key=config.API_KEY)
        data = kite.generate_session(request_token, api_secret=config.API_SECRET)
        access_token = data["access_token"]
        print(f"Success! Access Token: {access_token}")
        
        # Save to config.py
        update_config_file(access_token)
        return access_token
    except Exception as e:
        print(f"Error generating token: {e}")
        return None

def update_config_file(new_token):
    # Read the current config file
    with open("config.py", "r") as f:
        lines = f.readlines()
    
    # Update the ACCESS_TOKEN line
    with open("config.py", "w") as f:
        for line in lines:
            if line.startswith("ACCESS_TOKEN"):
                f.write(f'ACCESS_TOKEN = "{new_token}"\n')
            else:
                f.write(line)
    print("Updated config.py with new Access Token.")

if __name__ == "__main__":
    print("--- Zerodha Login Manager ---")
    print(f"1. Login URL: {get_login_url()}")
    
    req_token = input("\nEnter the 'request_token' from the Redirect URL: ").strip()
    if req_token:
        generate_access_token(req_token)
