import os

# Point this at your cloud server's public IP/hostname before deploying.
# Players never have to type an address themselves - it's baked in here.
SERVER_HOST = os.environ.get("RAINY_WORDS_SERVER_HOST", "127.0.0.1")
SERVER_PORT = int(os.environ.get("RAINY_WORDS_SERVER_PORT", 5555))

WINDOW_WIDTH = 900
WINDOW_HEIGHT = 650
FPS = 60
