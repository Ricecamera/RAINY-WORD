import socket
import threading

from server import auth
from shared.protocol import iter_messages, send_message


class ClientHandler:
    """One per connected TCP socket. Owns login-gating: nothing but
    register/login is accepted until the client has authenticated, which is
    what keeps unauthorized users out of the game.
    """

    def __init__(self, sock, addr, db, game_manager):
        self.sock = sock
        self.addr = addr
        self.db = db
        self.game_manager = game_manager
        self.send_lock = threading.Lock()
        self.user_id = None
        self.username = None

    def send(self, message: dict):
        with self.send_lock:
            send_message(self.sock, message)

    def run(self):
        try:
            for message in iter_messages(self.sock):
                self._dispatch(message)
        finally:
            self.game_manager.disconnect(self)
            try:
                self.sock.close()
            except OSError:
                pass

    def _dispatch(self, message: dict):
        msg_type = message.get("type")

        if self.user_id is None:
            if msg_type == "register":
                self._handle_register(message)
            elif msg_type == "login":
                self._handle_login(message)
            else:
                self.send({"type": "error", "message": "You must log in first."})
            return

        if msg_type == "type_word":
            self.game_manager.claim_word(message.get("match_id"), self.user_id, message.get("word", ""))
        elif msg_type == "rematch_vote":
            self.game_manager.rematch_vote(message.get("match_id"), self.user_id)
        elif msg_type == "ping":
            self.send({"type": "pong"})
        else:
            self.send({"type": "error", "message": f"Unknown message type: {msg_type}"})

    def _handle_register(self, message: dict):
        username = (message.get("username") or "").strip()
        password = message.get("password") or ""
        if not username or not password:
            self.send({"type": "register_fail", "reason": "Username and password are required."})
            return
        if self.db.get_user_by_username(username):
            self.send({"type": "register_fail", "reason": "Username already taken."})
            return
        password_hash = auth.hash_password(password)
        user_id = self.db.create_user(username, password_hash)
        self.send({"type": "register_ok"})
        self._complete_login(user_id, username)

    def _handle_login(self, message: dict):
        username = (message.get("username") or "").strip()
        password = message.get("password") or ""
        user = self.db.get_user_by_username(username)
        if not user or not auth.verify_password(password, user["password_hash"]):
            self.send({"type": "login_fail", "reason": "Invalid username or password."})
            return
        self._complete_login(user["id"], username)

    def _complete_login(self, user_id: int, username: str):
        self.send({"type": "login_ok", "username": username})
        self.send({"type": "welcome", "message": f"Welcome, {username}."})
        self.game_manager.on_login(self, user_id, username)


class RainyWordsServer:
    def __init__(self, host, port, db, game_manager):
        self.host = host
        self.port = port
        self.db = db
        self.game_manager = game_manager
        self._sock = None

    def start(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((self.host, self.port))
        self._sock.listen()
        threading.Thread(target=self._accept_loop, daemon=True).start()

    def _accept_loop(self):
        while True:
            try:
                client_sock, addr = self._sock.accept()
            except OSError:
                return
            handler = ClientHandler(client_sock, addr, self.db, self.game_manager)
            threading.Thread(target=handler.run, daemon=True).start()

    def stop(self):
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
