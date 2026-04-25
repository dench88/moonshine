import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path.home() / ".secrets.env")
except ImportError:
    pass  # dotenv not installed; fall back to shell environment

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_PATH = os.path.join(BASE_DIR, "topic_loop.db")
TOPIC_FILE = os.path.join(BASE_DIR, "topic.txt")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
REPORTS_DIR = os.path.join(BASE_DIR, "outputs", "reports")
LOGS_DIR = os.path.join(BASE_DIR, "logs")

OLLAMA_URL = "http://localhost:11434"

# Per-role model selection.
# Use a short alias (see MODEL_ALIASES) or a full "provider/model-name" string.
RESEARCHER_MODEL  = "gptoss"
SYNTHESISER_MODEL = "qwen"

# Short aliases usable on the CLI and in the settings above.
MODEL_ALIASES: dict[str, str] = {
    # Local (Ollama)
    "gptoss":   "ollama/gpt-oss:20b",
    "qwen":     "ollama/qwen2.5:32b",
    "huihui":   "ollama/huihui_ai/glm-4.7-flash-abliterated:q4_K",
    # Online
    "claude":   "anthropic/claude-sonnet-4-6",
    "chatgpt":  "openai/gpt-4o",
    "deepseek": "deepseek/deepseek-chat",
}


def resolve_model(name: str) -> str:
    """Expand a short alias to its full provider/model string, or pass through as-is."""
    return MODEL_ALIASES.get(name.lower(), name)

# API keys for online providers (read from environment)
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY    = os.environ.get("OPENAI_API_KEY", "")
DEEPSEEK_API_KEY  = os.environ.get("DEEPSEEK_API_KEY", "")

MAX_CYCLES = 50
SOURCES_PER_CYCLE = 2
RETRY_COUNT = 2

MIN_RELEVANCE_SCORE = 3   # out of 10
MIN_QUALITY_SCORE = 3     # out of 10

# Fetch settings
FETCH_TIMEOUT = 8         # seconds
MAX_TEXT_CHARS = 12000    # characters to extract from a page before truncating

# Search settings
# Set SEARCH_PROVIDER to "tavily", "searxng", "brave", or "mock"
SEARCH_PROVIDER = "tavily"
SEARXNG_URL = "http://localhost:8080"
BRAVE_API_KEY = os.environ.get("BRAVE_API_KEY", "")
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")
