import logging
from datetime import datetime
import os

# Setup logging
class ColoredLevelFormatter(logging.Formatter):
    COLOR_CODE = {
        'DEBUG':    "\x1b[34m",  # Blue
        'INFO':     "\x1b[32m",  # Green
        'WARNING':  "\x1b[33m",  # Yellow
        'ERROR':    "\x1b[31m",  # Red
        'CRITICAL': "\x1b[41m",  # Red background
    }
    
    TIMESTAMP_COLOR = "\x1b[36m"  # Cyan for timestamp
    RESET_COLOR = "\x1b[0m"       # Reset color

    def format(self, record):
        levelname = record.levelname
        levelname_color = self.COLOR_CODE.get(levelname, "")
        
        # Format timestamp, level, and message separately
        timestamp = f"{self.TIMESTAMP_COLOR}{self.formatTime(record, self.datefmt)}{self.RESET_COLOR}"
        levelname = f"{levelname_color}{levelname}{self.RESET_COLOR}"
        message = f"{record.getMessage()}"

        # Return the formatted log with consistent message color and different level/timestamp color
        formatted_log = f"{timestamp} [{levelname}] {message}"
        return formatted_log

# Setup Logging with colors and custom format
logging.getLogger().setLevel(logging.INFO)
formatter = ColoredLevelFormatter(datefmt='%Y-%m-%d %H:%M:%S')
console = logging.StreamHandler()
console.setFormatter(formatter)
logger = logging.getLogger()
logger.addHandler(console)
