import logging
import threading
import asyncio
import requests
import time
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler
import config
from logger import TelegramLogger
import suggestion_engine

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Global variable to store the bot application
application = None
auto_thread = None
stop_auto_event = threading.Event()

def send_alert(message):
    """
    Sends a message to the configured Telegram user.
    Uses requests for synchronous compatible sending from anywhere in the bot.
    """
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        print("[!] Telegram credentials missing in config.py")
        return

    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"[!] Error sending Telegram alert: {e}")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="🤖 *Zerodha Trading Bot Active*\n\nCommands:\n/scan - Run Instant Analysis\n/auto <min> - Start Auto Loop\n/stop - Stop Auto Loop\n/status - Check Status\n/pnl - Check PnL",
        parse_mode='Markdown'
    )

async def scan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="🔍 *Scanning Market... Please Wait.*", parse_mode='Markdown')
    
    # Run analysis in a separate thread to not block the bot
    def run_scan():
        logger = TelegramLogger()
        try:
            # Use defaults from config or hardcoded for now since no input
            # If config.MARGIN is not set, we might default to CAPITAL (assuming full cash)
             # or we can read from config.py if I add a MARGIN plain var there.
             # For now, let's assume CAPITAL is the limit.
            margin = config.CAPITAL 
            suggestion_engine.suggest_trade(config.CAPITAL, margin, logger=logger)
            
            # Send the captured log as a message
            full_log = logger.get_logs()
            # Split into chunks if too long (Telegram limit 4096)
            if len(full_log) > 4000:
                full_log = full_log[:4000] + "\n...[Truncated]"
            
            send_alert(f"📝 *Analysis Report*\n```\n{full_log}\n```")
        except Exception as e:
            send_alert(f"❌ Error during scan: {str(e)}")

    threading.Thread(target=run_scan).start()

async def auto_loop(interval_min):
    global stop_auto_event
    send_alert(f"🔄 *Auto-Mode Started*. Running every {interval_min} minutes.")
    
    while not stop_auto_event.is_set():
        # Run Scan
        logger = TelegramLogger()
        try:
            suggestion_engine.suggest_trade(config.CAPITAL, config.CAPITAL, logger=logger)
            # Only send alerts on trades (logic inside suggestion_engine does this)
            # But the user might want a heartbeat ??
            # For now, let's stay silent unless trade suggested (which suggestion_engine handles via send_alert)
            # OR we can send the log if we want full verbose mode.
            # Let's send a short heartbeat
            # send_alert(f"✅ Auto-Scan Completed at {time.strftime('%H:%M')}")
            pass
        except Exception as e:
            send_alert(f"❌ Auto-Scan Error: {e}")
            
        # Wait for interval
        stop_auto_event.wait(interval_min * 60)

async def auto_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global auto_thread, stop_auto_event
    
    if auto_thread and auto_thread.is_alive():
        await context.bot.send_message(chat_id=update.effective_chat.id, text="⚠️ Auto-mode is already running. Use /stop first.")
        return

    try:
        minutes = int(context.args[0]) if context.args else 15
        if minutes < 1: minutes = 1
    except:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="ℹ️ Usage: /auto <minutes>\nDefaulting to 15 mins.")
        minutes = 15

    stop_auto_event.clear()
    # We need to run the loop in a thread, but the async loop helper is internal. 
    # Actually we can just run a standard threading Thread that calls a synchronous wrapper.
    # But wait, my auto_loop above is async. Let's make it sync for threading.
    
    def sync_auto_loop_wrapper(interval):
         asyncio.run(auto_loop(interval)) # This might conflict with existing loop.
         # Better: Make auto_loop synchronous.
         
    # RE-DEFINING auto_loop as sync for simplicity in thread
    def sync_auto_loop(interval):
        send_alert(f"🔄 *Auto-Mode Started* (Interval: {interval}m)")
        while not stop_auto_event.is_set():
             logger = TelegramLogger()
             try:
                 suggestion_engine.suggest_trade(config.CAPITAL, config.CAPITAL, logger=logger)
             except Exception as e:
                 send_alert(f"❌ Auto-Scan Error: {e}")
             stop_auto_event.wait(interval * 60)
        send_alert("🛑 Auto-Mode Stopped.")

    auto_thread = threading.Thread(target=sync_auto_loop, args=(minutes,))
    auto_thread.start()
    
    await context.bot.send_message(chat_id=update.effective_chat.id, text=f"✅ background thread started.")

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global stop_auto_event
    stop_auto_event.set()
    await context.bot.send_message(chat_id=update.effective_chat.id, text="🛑 Stopping auto-mode...")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # This is a placeholder. In a real app, you'd fetch state from a shared object or database.
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="✅ Bot is running properly.\nMode: Monitoring\nCapital: ₹" + str(config.CAPITAL)
    )

import position_advisor_engine
from zerodha_adapter import ZerodhaAdapter

async def pnl_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
     await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="📊 *PnL Update*\nNo active trades yet."
    )

async def advice_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Triggers the Position Advisor analysis.
    """
    status_msg = await context.bot.send_message(chat_id=update.effective_chat.id, text="🧠 *Analyzing Positions...*")
    
    # Run in thread
    def run_advisor():
        try:
            # 1. Fetch positions
            za = ZerodhaAdapter()
            za.login() # Should use cached token ideally or re-login if needed. 
            # Note: The adapter currently is interactive login. We might need a better way to share session.
            # For now, let's assume session is valid or we use the 'get_kite()' directly if simple.
            # Actually, `zerodha_adapter` is better wrapper.
            # But let's use `kite_data.get_kite()` for the kite instance if we just need market data,
            # and `zerodha_adapter` for positions.
            
            # Using zerodha_adapter might trigger interactive login again if not persistent.
            # Let's try to see if we can use the global kite instance if available.
            import kite_data
            k = kite_data.get_kite()
            if not k:
                send_alert("⚠️ Kite Session invalid. Cannot analyze.")
                return

            # Fetch positions via kite directly to avoid re-login complexity of Adapter class for now
            positions = k.positions()['net']
            
            # 2. Analyze
            report = position_advisor_engine.get_advice_report(k, positions)
            
            send_alert(report)
            
        except Exception as e:
            send_alert(f"❌ Advisor Error: {e}")

    threading.Thread(target=run_advisor).start()

def run_telegram_bot():
    """
    Starts the Telegram bot listener.
    """
    global application
    if not config.TELEGRAM_BOT_TOKEN or "YOUR_" in config.TELEGRAM_BOT_TOKEN:
        print("[!] Invalid Telegram Token. Bot listener will not start.")
        return

    print("--- Starting Telegram Bot Listener ---")
    application = ApplicationBuilder().token(config.TELEGRAM_BOT_TOKEN).build()
    
    start_handler = CommandHandler('start', start_command)
    scan_handler = CommandHandler('scan', scan_command)
    auto_handler = CommandHandler('auto', auto_command)
    stop_handler = CommandHandler('stop', stop_command)
    status_handler = CommandHandler('status', status_command)
    pnl_handler = CommandHandler('pnl', pnl_command)
    
    application.add_handler(start_handler)
    application.add_handler(scan_handler)
    application.add_handler(auto_handler)
    application.add_handler(stop_handler)
    application.add_handler(status_handler)
    application.add_handler(pnl_handler)
    
    advice_handler = CommandHandler('advice', advice_command)
    application.add_handler(advice_handler)
    
    # Run the bot polling
    application.run_polling()

def start_bot_in_thread():
    """
    Helper to run the bot in a separate thread so it doesn't block the main trading loop.
    """
    bot_thread = threading.Thread(target=run_telegram_bot, daemon=True)
    bot_thread.start()
