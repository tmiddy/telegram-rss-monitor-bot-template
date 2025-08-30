
import os
from dotenv import load_dotenv

load_dotenv() 

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_FALLBACK_TOKEN_HERE")

CHECK_INTERVAL_SECONDS = int(os.getenv("CHECK_INTERVAL_SECONDS", 300)) 
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
MAX_FETCH_ERRORS = int(os.getenv("MAX_FETCH_ERRORS", 5)) 
USER_AGENT = "LotNotificationBot/1.0 (+https://your-bot-info-link.com)" # Замените на актуальную информацию


if BOT_TOKEN == "YOUR_FALLBACK_TOKEN_HERE" or not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не установлен")