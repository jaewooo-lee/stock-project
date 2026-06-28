import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Gemini Config
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Kakao Config
KAKAO_REST_API_KEY = os.getenv("KAKAO_REST_API_KEY", "")
KAKAO_REDIRECT_URI = os.getenv("KAKAO_REDIRECT_URI", "http://localhost:8000/api/kakao/callback")
KAKAO_REFRESH_TOKEN = os.getenv("KAKAO_REFRESH_TOKEN", "")

# App Config
BASE_URL = os.getenv("BASE_URL", "http://localhost").rstrip("/")
REPORTS_DIR = os.getenv("REPORTS_DIR", "./reports")
CLEANUP_DAYS = int(os.getenv("CLEANUP_DAYS", "90"))
DATABASE_FILE = os.getenv("DATABASE_FILE", "stock_tracker.db")

# Ensure reports directory exists
os.makedirs(REPORTS_DIR, exist_ok=True)
