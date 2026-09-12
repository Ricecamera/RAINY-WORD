import queue
import socket
import threading

from shared.protocol import iter_messages, send_message


class ServerConnection:
    """Background-threaded TCP client. The pygame main loop calls poll()
    once per frame to drain whatever arrived since the last frame, so the
    render loop never blocks on socket I/O.
    """

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.sock = None
        self.connected = False
        self._incoming = queue.Queue()
        self._thread = None

    def connect(self, timeout: float = 5.0):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(timeout)
        self.sock.connect((self.host, self.port))
        self.sock.settimeout(None)
        self.connected = True
        self._thread = threading.Thread(target=self._recv_loop, daemon=True)
        self._thread.start()

    def _recv_loop(self):
        try:
            for message in iter_messages(self.sock):
                self._incoming.put(message)
        finally:
            self.connected = False
            self._incoming.put({"type": "_disconnected"})

    def send(self, message: dict):
        if not self.sock:
            return
        try:
            send_message(self.sock, message)
        except OSError:
            self.connected = False

    def poll(self):
        messages = []
        while True:
            try:
                messages.append(self._incoming.get_nowait())
            except queue.Empty:
                break
        return messages

    def close(self):
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass
