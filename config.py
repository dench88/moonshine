import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_PATH = os.path.join(BASE_DIR, "topic_loop.db")
TOPIC_FILE = os.path.join(BASE_DIR, "topic.txt")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
LOGS_DIR = os.path.join(BASE_DIR, "logs")

OLLAMA_URL = "http://localhost:11434"
MODEL_NAME = "gpt-oss:20b"

MAX_CYCLES = 40
SOURCES_PER_CYCLE = 2
RETRY_COUNT = 2

MIN_RELEVANCE_SCORE = 3   # out of 10
MIN_QUALITY_SCORE = 3     # out of 10

# Fetch settings
FETCH_TIMEOUT = 20        # seconds
MAX_TEXT_CHARS = 12000    # characters to extract from a page before truncating

# Search settings
# Set SEARCH_PROVIDER to "mock" for testing, "searxng" or "brave" for real use
SEARCH_PROVIDER = "mock"
SEARXNG_URL = "http://localhost:8080"
BRAVE_API_KEY = os.environ.get("BRAVE_API_KEY", "")
