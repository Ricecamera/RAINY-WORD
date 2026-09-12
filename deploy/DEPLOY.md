# Deploying Rainy Words to a cloud instance

The game server (`server/main.py`) shows its live status - connected
players, active matches, the current word set, and a reset button - in a
Tkinter window. To "view server status or play the game on" your cloud
instance as requested, that window needs a display, so the recommended
setup gives the cloud VM a lightweight desktop you reach over VNC.

This guide is generic - it works on any Ubuntu 22.04 VM from AWS EC2,
DigitalOcean, GCP, Azure, Linode, etc. Substitute your provider's own
steps for creating the VM and opening firewall ports.

## 1. Provision the VM

- Ubuntu 22.04 LTS, 1-2 vCPU / 2 GB RAM is plenty.
- Open these ports in your provider's firewall / security group:
  - **5555/tcp** - the game protocol (raw sockets). Open to the internet
    (or to your players' IPs) so remote clients can connect.
  - **22/tcp** - SSH, open only to your own IP if possible.
  - Do **not** open 5901 (VNC) publicly - you'll reach it through an SSH
    tunnel instead (step 4), which is both simpler and safer.

## 2. Install a desktop + VNC server

```bash
sudo apt update
sudo apt install -y xfce4 xfce4-goodies tigervnc-standalone-server \
    python3 python3-pip python3-venv git \
    libsdl2-2.0-0 libsdl2-image-2.0-0 libsdl2-mixer-2.0-0 libsdl2-ttf-2.0-0
```

Set a VNC password and start a session:

```bash
vncpasswd
vncserver :1 -geometry 1280x800
```

Make the XFCE desktop actually load in that session:

```bash
cat > ~/.vnc/xstartup <<'EOF'
#!/bin/sh
startxfce4 &
EOF
chmod +x ~/.vnc/xstartup
vncserver -kill :1
vncserver :1 -geometry 1280x800
```

## 3. Deploy the code

```bash
sudo mkdir -p /opt/rainy-words
sudo chown $USER /opt/rainy-words
git clone <your-repo-url> /opt/rainy-words
cd /opt/rainy-words
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

The SQLite database file lives at `data/rainy_words.db` by default (see
`server/config.py` / `RAINY_WORDS_DB`) - it's created automatically and
persists match state across restarts and reconnects.

## 4. Connect to the desktop over VNC (via SSH tunnel)

From your own computer:

```bash
ssh -L 5901:localhost:5901 <user>@<cloud-instance-ip>
```

Then point any VNC viewer (TigerVNC Viewer, RealVNC, etc.) at
`localhost:5901`. You now see the cloud instance's desktop.

## 5. Run the server inside the VNC desktop

Open a terminal in the VNC session:

```bash
cd /opt/rainy-words
.venv/bin/python -m server.main
```

The Tkinter admin window appears right there in the VNC desktop, showing
connected clients, active matches, the current word set, and a **Reset
All Games** button. Leave this terminal/window running - closing it stops
the server.

To have it start automatically whenever the VNC session starts, append to
`~/.vnc/xstartup` (before the final `startxfce4 &`):

```bash
cd /opt/rainy-words && .venv/bin/python -m server.main &
```

### Optional: headless mode instead

If you don't need the GUI (e.g. you only care about players connecting,
and you're fine checking status over SSH), run it without a desktop at
all:

```bash
.venv/bin/python -m server.main --headless
```

This prints the same status information to the console on a timer and
works with the provided `deploy/rainy-words-server.service` systemd unit
or `deploy/docker-compose.yml`/`Dockerfile` for auto-restart.

## 6. Playing on the cloud instance itself

Since you're already in a VNC desktop with a display, you can also run a
game client directly on the cloud instance - open another terminal:

```bash
cd /opt/rainy-words
.venv/bin/python -m client.main
```

## 7. Playing from other computers

On each player's own machine:

1. Copy the repo (or just the `client/` and `shared/` folders) locally.
2. Edit `client/config.py` (or set the `RAINY_WORDS_SERVER_HOST`
   environment variable) to your cloud instance's public IP.
3. `pip install -r requirements.txt`
4. `python -m client.main`

Each player logs in (or registers) with their own account - the server
only lets authenticated users past the login screen (see
`server/server.py`). Multiple players on multiple screens/computers can
connect at once; the server pairs up waiting players into matches
automatically.

## Reconnecting without losing progress

If a player's connection drops mid-match, the match keeps running
server-side (state is persisted to SQLite after every score change). When
they relaunch the client and log back in with the same account, the
server detects their in-progress match and resumes it with the current
scores, word set, and time remaining - even if the server itself was
restarted in between.
