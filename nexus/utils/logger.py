"""
Thread-Safe Logging Utilities for NEXUS Suite
"""

import time
from datetime import datetime
from typing import Callable, Optional


class NexusLogger:
    """Dispatches timestamped event logs to terminal and UI signals."""

    def __init__(self, callback: Optional[Callable[[str, str], None]] = None):
        self.callback = callback

    def log(self, message: str, level: str = "INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted = f"[{timestamp}] [{level}] {message}"
        
        if self.callback:
            try:
                self.callback(formatted, level)
            except Exception:
                pass

    def info(self, msg: str):
        self.log(msg, "INFO")

    def success(self, msg: str):
        self.log(msg, "SUCCESS")

    def warn(self, msg: str):
        self.log(msg, "WARNING")

    def error(self, msg: str):
        self.log(msg, "ERROR")
