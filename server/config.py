import os

HOST = "0.0.0.0"
PORT = int(os.environ.get("RAINY_WORDS_PORT", 5555))

# Admin web dashboard. Bound to localhost by default - reach it through an
# SSH tunnel on a cloud box, or explicitly set WEB_HOST=0.0.0.0 (ideally
# behind a TLS reverse proxy) if you want it open to the internet.
WEB_HOST = os.environ.get("RAINY_WORDS_WEB_HOST", "127.0.0.1")
WEB_PORT = int(os.environ.get("RAINY_WORDS_WEB_PORT", 8080))
ADMIN_USERNAME = os.environ.get("RAINY_WORDS_ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("RAINY_WORDS_ADMIN_PASSWORD")  # None -> generate one at startup

DB_PATH = os.environ.get(
    "RAINY_WORDS_DB",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "rainy_words.db"),
)

MATCH_DURATION_SECONDS = int(os.environ.get("RAINY_WORDS_MATCH_SECONDS", 60))
WORDS_PER_MATCH = 20        # size of the unique word pool generated per match
MAX_CONCURRENT_WORDS = 8    # how many words fall at once
REPLENISH_LOW_WATER = 2.0   # stop spawning new words this close to time running out
TICK_INTERVAL_SECONDS = 1.0
