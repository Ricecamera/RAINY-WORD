# Rainy Words game server - no desktop/VNC needed, the admin dashboard is
# a plain website served by the process itself. See deploy/DEPLOY.md.
FROM python:3.11-slim

WORKDIR /app

COPY shared/ shared/
COPY server/ server/

ENV RAINY_WORDS_DB=/data/rainy_words.db
# Bind the dashboard to all interfaces inside the container so Docker's
# port mapping can actually reach it. Restrict exposure at the `docker run
# -p` / compose level (or put a TLS reverse proxy in front) instead.
ENV RAINY_WORDS_WEB_HOST=0.0.0.0

VOLUME ["/data"]
EXPOSE 5555 8080

CMD ["python", "-m", "server.main", "--print-status"]
