class SimpleLogger:
    def __init__(self):
        self.logs = []

    def log(self, message):
        """
        Prints to console and appends to the internal log list.
        """
        print(message)
        self.logs.append(str(message))

    def get_logs(self):
        """
        Returns the accumulated logs as a single string.
        """
        return "\n".join(self.logs)

    def clear(self):
        """
        Clears the accumulated logs.
        """
        self.logs = []

    def flush_to_telegram(self):
        """
        Sends accumulated logs to Telegram and clears buffer.
        """
        if not self.logs: return
        
        import telegram_interface
        
        # Join logs
        full_msg = "\n".join(self.logs)
        
        # Send via Wrapper (handles splitting if needed, though interface handles simple send)
        # We wrap in code block for better formatting in Telegram
        formatted_msg = f"```\n{full_msg}\n```"
        
        telegram_interface.send_telegram_message(formatted_msg)
        self.clear()
