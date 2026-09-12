"""
Wire protocol for Rainy Words.

Transport is a plain TCP socket (socket.AF_INET/SOCK_STREAM) - no websockets,
no HTTP. Each message is a single JSON object followed by a newline
("JSON-lines" framing), which keeps the socket code trivial while still
letting messages carry structured fields.
"""
import json
import socket

ENCODING = "utf-8"


class ConnectionClosed(Exception):
    """Raised when the peer closes the socket."""


def send_message(sock: socket.socket, message: dict) -> None:
    data = (json.dumps(message) + "\n").encode(ENCODING)
    sock.sendall(data)


def iter_messages(sock: socket.socket):
    """Yield decoded JSON messages read from a raw socket, one per line."""
    buffer = b""
    while True:
        try:
            chunk = sock.recv(4096)
        except OSError:
            return
        if not chunk:
            return
        buffer += chunk
        while b"\n" in buffer:
            line, buffer = buffer.split(b"\n", 1)
            if not line.strip():
                continue
            try:
                yield json.loads(line.decode(ENCODING))
            except json.JSONDecodeError:
                continue
