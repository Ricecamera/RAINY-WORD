# Deploying Rainy Words to a cloud instance

The game server (`server/main.py`) is fully headless - no desktop, no
VNC. It serves its live status (connected players, active matches, the
current word set, a reset button) as a small website on its own, in
addition to listening for game clients on a raw TCP socket. This guide
works on any plain Ubuntu 22.04 VM from AWS EC2, DigitalOcean, GCP,
Azure, Linode, etc. - substitute your provider's own steps for creating
the VM and opening firewall ports.

The server has **no third-party Python dependencies** - it's pure
standard library (`socket`, `sqlite3`, `http.server`, `threading`).
`pygame` (in `requirements.txt`) is only needed on the machines running
the desktop *client*.

## 1. Provision the VM

- Ubuntu 22.04 LTS, 1 vCPU / 1 GB RAM is plenty.
- Open this port in your provider's firewall / security group:
  - **5555/tcp** - the game protocol (raw sockets). Open to the internet
    (or to your players' IPs) so remote clients can connect.
  - **22/tcp** - SSH, open only to your own IP if possible.
  - Leave **8080/tcp** (the admin dashboard) closed for now - by default
    the server only binds it to `127.0.0.1` on the VM itself, and you'll
    reach it through an SSH tunnel (step 4). Only open it publicly if you
    deliberately choose to in step 5.

## 2. Deploy the code

```bash
sudo mkdir -p /opt/rainy-words
sudo chown $USER /opt/rainy-words
git clone <your-repo-url> /opt/rainy-words
cd /opt/rainy-words
```

Nothing to `pip install` for the server itself - it only needs Python 3
(already on Ubuntu 22.04 as `python3`).

The SQLite database lives at `data/rainy_words.db` by default (see
`server/config.py` / `RAINY_WORDS_DB`) - created automatically, and it's
what makes match state survive client disconnects, reconnects, and even
server restarts.

## 3. Run the server

```bash
python3 -m server.main --print-status
```

You'll see something like:

```
Rainy Words game server listening on 0.0.0.0:5555
No RAINY_WORDS_ADMIN_PASSWORD set - generated a one-time admin password for this run: 7xQ2f...
Admin dashboard: http://127.0.0.1:8080/  (user: admin)
```

Set `RAINY_WORDS_ADMIN_PASSWORD` to a password of your choice if you
don't want a new random one generated on every restart:

```bash
export RAINY_WORDS_ADMIN_PASSWORD='choose-a-strong-password'
python3 -m server.main --print-status
```

To keep it running after you log out and restart it if it crashes, use
the provided systemd unit instead of running it by hand - see
`deploy/rainy-words-server.service` (set `RAINY_WORDS_ADMIN_PASSWORD`
there, then `sudo systemctl enable --now rainy-words-server` and watch
`journalctl -u rainy-words-server -f`), or use
`deploy/Dockerfile`/`docker-compose.yml`.

## 4. View the admin dashboard

The dashboard binds to `127.0.0.1:8080` on the VM by default - it isn't
reachable from the internet unless you change that (step 5). From your
own computer:

```bash
ssh -L 8080:localhost:8080 <user>@<cloud-instance-ip>
```

Then open `http://localhost:8080` in your browser and log in with
username `admin` and whichever password the server printed/you set. You
get a live view of connected clients, active matches (scores, word pool,
currently-falling words, time left), and a **Reset All Games** button.

## 5. Optional: open the dashboard directly to the browser

If you'd rather not SSH-tunnel every time (e.g. you want teammates to
check status too), you can expose it directly:

```bash
export RAINY_WORDS_WEB_HOST=0.0.0.0
```

...then open port 8080 in your firewall. **Do this behind HTTPS if the
VM is reachable from the open internet** - the dashboard uses HTTP Basic
Auth, which only hides your password from casual snooping, not from
anyone who can see the raw traffic. The easiest way is
[Caddy](https://caddyserver.com/), which gets you free automatic TLS in
a 3-line config:

```
# /etc/caddy/Caddyfile
your-domain.example.com {
    reverse_proxy 127.0.0.1:8080
}
```

(`sudo apt install -y caddy`, then `sudo systemctl restart caddy`.) Point
your DNS at the VM, visit `https://your-domain.example.com`, done.

## 6. Playing from players' own computers

On each player's machine:

1. Copy the repo (or just `client/` and `shared/`).
2. Point it at your server - either edit `client/config.py`, or set an
   environment variable before launching:
   ```bash
   export RAINY_WORDS_SERVER_HOST=<cloud-instance-ip>
   ```
3. `pip install -r requirements.txt` (this is what installs `pygame`).
4. `python -m client.main`

Each player logs in (or registers) with their own account - the server
rejects any socket that hasn't authenticated (see `server/server.py`).
Multiple players on multiple screens/computers can connect at once; the
server pairs up waiting players into matches automatically.

## Reconnecting without losing progress

If a player's connection drops mid-match, the match keeps running
server-side (state is persisted to SQLite after every score change).
When they relaunch the client and log back in with the same account, the
server detects their in-progress match and resumes it with the current
scores, word set, and time remaining - even if the server itself was
restarted in between.
