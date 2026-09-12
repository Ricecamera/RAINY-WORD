import os

HOST = "0.0.0.0"
PORT = int(os.environ.get("RAINY_WORDS_PORT", 5555))

DB_PATH = os.environ.get(
    "RAINY_WORDS_DB",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "rainy_words.db"),
)

MATCH_DURATION_SECONDS = int(os.environ.get("RAINY_WORDS_MATCH_SECONDS", 60))
WORDS_PER_MATCH = 20        # size of the unique word pool generated per match
MAX_CONCURRENT_WORDS = 8    # how many words fall at once
REPLENISH_LOW_WATER = 2.0   # stop spawning new words this close to time running out
TICK_INTERVAL_SECONDS = 1.0
