# Headless deployment of the Rainy Words game server (no admin GUI - use
# this if you don't need the Tkinter status window, e.g. behind SSH-only
# access). For the GUI you can view over VNC, run server/main.py directly
# on a desktop-enabled VM instead - see deploy/DEPLOY.md.
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY shared/ shared/
COPY server/ server/

ENV RAINY_WORDS_DB=/data/rainy_words.db
VOLUME ["/data"]
EXPOSE 5555

CMD ["python", "-m", "server.main", "--headless"]
