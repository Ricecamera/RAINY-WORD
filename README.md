# Rainy Words

A two-player online typing race: random words fall from the top of the
screen and players race to type them first. Built around the original
"Rainy Words" socket-programming assignment, extended for a persistent,
authenticated, cloud-hosted setup:

- **Server**: pure Python, raw TCP sockets (`socket` + `threading`, no
  websockets). Authoritative game logic - word generation, scoring, the
  60-second timer, rematches - all live on the server.
- **Client**: Pygame desktop app. Multiple instances (one per player, on
  any number of computers/screens) connect to the same server.
- **Login**: every connection must register/log in before it can do
  anything else - unauthenticated sockets are rejected.
- **Persistence**: SQLite stores users, matches, and live scores. If a
  client disconnects (or the server restarts), a player who logs back in
  is dropped straight back into their in-progress match with their score
  and remaining time intact.
- **Admin/status UI**: a Tkinter window on the server shows connected
  clients, active matches, the current word set, and a reset button - see
  `deploy/DEPLOY.md` for viewing it on a cloud VM over VNC.

## Project layout

```
shared/    protocol (JSON-lines over TCP) + word list, used by both sides
server/    socket server, game logic, SQLite persistence, admin GUI
client/    pygame desktop client
deploy/    Dockerfile, systemd unit, and the cloud deployment guide
```

## Running locally (for development/testing)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# terminal 1
python -m server.main            # opens the Tkinter admin window
# or: python -m server.main --headless   # console status instead

# terminal 2 and 3 (two players)
python -m client.main
python -m client.main
```

Each client logs in or registers its own account, then the server pairs
the first two waiting players into a match automatically.

## Deploying to the cloud

See [`deploy/DEPLOY.md`](deploy/DEPLOY.md) for a step-by-step guide to
running the server on a cloud VM with the admin GUI reachable over VNC,
opening the game port for remote players, and pointing client installs at
your instance.

## Protocol

See `shared/protocol.py` for the framing (one JSON object per line over a
plain TCP socket) and `server/server.py` / `client/app.py` for the message
types exchanged (`login`, `register`, `match_found`, `type_word`,
`state_update`, `match_end`, `rematch_vote`, etc).
