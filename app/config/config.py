import os
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from .env file
load_dotenv()

# Bot configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN is not set in environment variables")

# MongoDB configuration
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "insurance_bot")

# OpenAI configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Google configuration
GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
USE_GOOGLE_GEMINI = os.getenv("USE_GOOGLE_GEMINI", "False").lower() in ("true", "1", "t")
GOOGLE_GEMINI_API_KEY = os.getenv("GOOGLE_GEMINI_API_KEY")

# OCR configuration
TESSERACT_CMD = os.getenv("TESSERACT_CMD", "tesseract")
USE_GOOGLE_VISION = os.getenv("USE_GOOGLE_VISION", "False").lower() in ("true", "1", "t")

# File storage configuration
TEMP_DOWNLOAD_PATH = Path(os.getenv("TEMP_DOWNLOAD_PATH", "temp_downloads"))
TEMP_DOWNLOAD_PATH.mkdir(exist_ok=True)

# Admin user IDs (comma-separated list of Telegram user IDs)
ADMIN_USER_IDS = [int(uid.strip()) for uid in os.getenv("ADMIN_USER_IDS", "").split(",") if uid.strip()]

# Constants
DEFAULT_LANGUAGE = "en"
MAX_FILE_SIZE_MB = 20
SUPPORTED_FILE_TYPES = ("application/pdf", "image/jpeg", "image/png")
