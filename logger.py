class TelegramLogger:
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
