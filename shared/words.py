import random

WORD_POOL = [
    "rain", "cloud", "storm", "thunder", "puddle", "umbrella", "drizzle",
    "shower", "lightning", "breeze", "wind", "flood", "splash", "droplet",
    "mist", "fog", "monsoon", "forecast", "weather", "climate", "sunshine",
    "rainbow", "hail", "sleet", "frost", "snow", "humid", "damp", "wet",
    "gray", "gloomy", "cozy", "shelter", "boots", "jacket", "window",
    "river", "stream", "ocean", "wave", "tide", "current", "harbor",
    "python", "socket", "server", "client", "packet", "thread", "queue",
    "score", "match", "player", "typing", "keyboard", "screen", "cursor",
    "coffee", "candle", "blanket", "book", "music", "garden", "forest",
    "mountain", "valley", "meadow", "island", "desert", "canyon", "cave",
]


def generate_word_set(count: int = 15) -> list:
    """Return a set of unique random words for one match."""
    count = min(count, len(WORD_POOL))
    return random.sample(WORD_POOL, count)
