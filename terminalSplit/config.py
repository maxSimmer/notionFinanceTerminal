import os
import sys

# Load .env file if python-dotenv is installed (optional)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ══════════════════════════════════════════════════
# CONFIGURATION — Database IDs from Notion setup
# ══════════════════════════════════════════════════
NOTION_API_KEY     = os.environ.get("NOTION_API_KEY", "")

ACCOUNTS_DB_ID     = os.environ.get("ACCOUNTS_DB_ID", "")
TRANSACTIONS_DB_ID = os.environ.get("TRANSACTIONS_DB_ID", "")
RECURRING_DB_ID    = os.environ.get("RECURRING_DB_ID", "")
GOALS_DB_ID        = os.environ.get("GOALS_DB_ID", "")
MONTHLY_DB_ID      = os.environ.get("MONTHLY_DB_ID", "")

NOTION_VERSION = "2022-06-28"
BASE_URL = "https://api.notion.com/v1"


def _sanitize(text):
    """Scrub the API key from any uncaught exception tracebacks."""
    if NOTION_API_KEY:
        return text.replace(NOTION_API_KEY, "***REDACTED***")
    return text


def _safe_excepthook(exc_type, exc_value, exc_tb):
    import traceback
    output = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    sys.stderr.write(_sanitize(output))


sys.excepthook = _safe_excepthook
