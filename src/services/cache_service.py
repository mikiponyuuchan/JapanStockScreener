from pathlib import Path
from datetime import datetime
import pickle


CACHE_DIR = Path("data/cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

CACHE_FILE = CACHE_DIR / "history_cache.pkl"


def load_cache():

    if not CACHE_FILE.exists():
        return {}

    try:

        with open(CACHE_FILE, "rb") as f:
            return pickle.load(f)

    except Exception:
        return {}


def save_cache(cache):

    with open(CACHE_FILE, "wb") as f:
        pickle.dump(cache, f)


def is_today():

    if not CACHE_FILE.exists():
        return False

    today = datetime.now().date()

    file_day = datetime.fromtimestamp(
        CACHE_FILE.stat().st_mtime
    ).date()

    return today == file_day