import base64
import json
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DASHBOARD_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Rainy Words - Admin</title>
<style>
  :root { color-scheme: dark; }
  body { margin:0; padding:24px; background:#10141f; color:#ebebf0; font-family: system-ui, -apple-system, sans-serif; }
  h1 { color:#5a92e6; margin-top:0; }
  h2 { color:#c7cbe0; font-size:16px; text-transform:uppercase; letter-spacing:0.05em; margin-top:28px; }
  .summary { display:flex; gap:16px; margin-bottom:12px; flex-wrap:wrap; align-items:stretch; }
  .stat { background:#1a2038; border-radius:10px; padding:14px 20px; min-width:120px; }
  .stat .value { font-size:28px; font-weight:700; }
  .stat .label { font-size:12px; color:#8c91ab; }
  .stat.action { display:flex; align-items:center; justify-content:center; }
  button#reset { background:#c0392b; color:white; border:none; padding:12px 20px; border-radius:8px; cursor:pointer; font-size:14px; font-weight:600; }
  button#reset:hover { background:#a93226; }
  .match { background:#1a2038; border-radius:10px; padding:16px; margin-bottom:14px; }
  .match h3 { margin:0 0 10px; font-size:15px; }
  .players { display:flex; gap:12px; margin-bottom:10px; flex-wrap:wrap; }
  .player { background:#232a48; padding:6px 12px; border-radius:6px; font-size:14px; }
  .words { font-family: ui-monospace, Consolas, monospace; color:#9fb3d9; word-break: break-word; font-size:13px; margin:6px 0; }
  .online { color:#6edc96; }
  .offline { color:#e07a7a; }
  ul#clientsList { list-style:none; padding:0; margin:0; }
  ul#clientsList li { padding:4px 0; }
  .empty { color:#8c91ab; font-style: italic; }
</style>
</head>
<body>
<h1>Rainy Words - Server Admin</h1>

<div class="summary">
  <div class="stat"><div class="value" id="connectedCount">-</div><div class="label">Connected Clients</div></div>
  <div class="stat"><div class="value" id="waitingCount">-</div><div class="label">Waiting For Opponent</div></div>
  <div class="stat"><div class="value" id="matchCount">-</div><div class="label">Active Matches</div></div>
  <div class="stat action"><button id="reset">Reset All Games</button></div>
</div>

<h2>Connected Clients</h2>
<ul id="clientsList"><li class="empty">Loading...</li></ul>

<h2>Matches</h2>
<div id="matches"><p class="empty">Loading...</p></div>

<script>
function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

async function refresh() {
  let data;
  try {
    const res = await fetch('/api/status', { cache: 'no-store' });
    if (!res.ok) return;
    data = await res.json();
  } catch (e) {
    return; // transient network hiccup - next poll retries
  }

  document.getElementById('connectedCount').textContent = data.connected_count;
  document.getElementById('waitingCount').textContent = data.waiting_count;
  document.getElementById('matchCount').textContent = data.matches.length;

  const clientsList = document.getElementById('clientsList');
  clientsList.replaceChildren();
  if (data.connected_usernames.length === 0) {
    clientsList.appendChild(el('li', 'empty', '(none)'));
  } else {
    for (const name of data.connected_usernames) {
      clientsList.appendChild(el('li', null, name));
    }
  }

  const matchesDiv = document.getElementById('matches');
  matchesDiv.replaceChildren();
  if (data.matches.length === 0) {
    matchesDiv.appendChild(el('p', 'empty', '(no active matches)'));
  } else {
    for (const m of data.matches) {
      const card = el('div', 'match');
      card.appendChild(el('h3', null, `Match #${m.id} [${m.status}] - time left: ${m.time_left}s`));

      const playersRow = el('div', 'players');
      for (const p of m.players) {
        const tag = el('span', 'player', `${p.username}: ${p.score} pts `);
        tag.appendChild(el('span', p.connected ? 'online' : 'offline', p.connected ? '(online)' : '(offline)'));
        playersRow.appendChild(tag);
      }
      card.appendChild(playersRow);

      card.appendChild(el('p', 'words', 'Word pool: ' + m.word_pool.join(', ')));
      card.appendChild(el('p', 'words', 'Currently falling: ' + (m.words_remaining.join(', ') || '(none)')));

      matchesDiv.appendChild(card);
    }
  }
}

document.getElementById('reset').addEventListener('click', async () => {
  if (!confirm('Reset all active games and scores?')) return;
  await fetch('/api/reset', { method: 'POST' });
  refresh();
});

refresh();
setInterval(refresh, 1000);
</script>
</body>
</html>
"""


class DashboardHandler(BaseHTTPRequestHandler):
    game_manager = None
    admin_username = ""
    admin_password = ""

    def _authorized(self) -> bool:
        header = self.headers.get("Authorization", "")
        if not header.startswith("Basic "):
            return False
        try:
            decoded = base64.b64decode(header[len("Basic "):]).decode("utf-8")
            username, _, password = decoded.partition(":")
        except (ValueError, UnicodeDecodeError):
            return False
        return (
            secrets.compare_digest(username, self.admin_username)
            and secrets.compare_digest(password, self.admin_password)
        )

    def _require_auth(self):
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="Rainy Words Admin"')
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _send_bytes(self, status: int, content_type: str, body: bytes):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, status: int, html: str):
        self._send_bytes(status, "text/html; charset=utf-8", html.encode("utf-8"))

    def _send_json(self, status: int, payload: dict):
        self._send_bytes(status, "application/json", json.dumps(payload).encode("utf-8"))

    def do_GET(self):
        if self.path == "/healthz":
            self._send_html(200, "ok")
            return
        if not self._authorized():
            self._require_auth()
            return
        if self.path in ("/", "/index.html"):
            self._send_html(200, DASHBOARD_HTML)
        elif self.path == "/api/status":
            self._send_json(200, self.game_manager.get_status_snapshot())
        else:
            self._send_html(404, "Not found")

    def do_POST(self):
        if not self._authorized():
            self._require_auth()
            return
        if self.path == "/api/reset":
            self.game_manager.reset_all()
            self._send_json(200, {"ok": True})
        else:
            self._send_html(404, "Not found")

    def log_message(self, fmt, *args):
        pass  # keep the console focused on game status, not HTTP access logs


class DashboardServer:
    """A small admin website: live server status plus a reset button, so
    there's no need for a desktop/VNC session on a headless cloud VM.
    """

    def __init__(self, host: str, port: int, game_manager, username: str, password: str):
        handler_cls = type("BoundDashboardHandler", (DashboardHandler,), {
            "game_manager": game_manager,
            "admin_username": username,
            "admin_password": password,
        })
        self.httpd = ThreadingHTTPServer((host, port), handler_cls)
        self.host = host
        self.port = port

    def start(self):
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def stop(self):
        self.httpd.shutdown()
