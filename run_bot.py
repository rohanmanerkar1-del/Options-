import sys
import telegram_interface

def run():
    print("--- ZERODHA TRADING BOT (TELEGRAM CONTROLLED) ---")
    print("[-] Bot listener starting...")
    print("[-] Open your Telegram App and use:")
    print("    /scan  - to Run Analysis")
    print("    /auto  - to Start Loop")
    print("    /start - for Help")
    
    try:
        # We just run the polling in the main thread now, no need for background threads
        # since we don't have a console input loop anymore.
        telegram_interface.run_telegram_bot()
    except KeyboardInterrupt:
        print("\n[!] Stopping Bot...")
        sys.exit(0)
    except Exception as e:
        print(f"[!] Error: {e}")

if __name__ == "__main__":
    run()
