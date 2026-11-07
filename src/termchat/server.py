"""The chat server: accepts connections, authenticates, routes messages.

Threads:
  * accept thread      — accepts new connections, starts a client thread for each
  * one client thread  — per participant: password, name, then reads their messages
  * main thread        — the host's keyboard (run_console)
"""
from __future__ import annotations

import hmac
import socket
import ssl
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional

from . import commands, config
from .terminal import clean, insert_above, note, paint, ts


@dataclass(eq=False)
class Participant:
    name: str
    color: int
    conn: Optional[socket.socket] = None   # None means this is the host (types in the server console)
    kicked: bool = False

    @property
    def is_host(self) -> bool:
        return self.conn is None

    @property
    def tag(self) -> str:
        return paint(self.name, self.color)


def print_above_input(text: str) -> None:
    """Default host output: print above the host's own input line."""
    print(insert_above(text), end="", flush=True)


class ChatServer:
    def __init__(
        self,
        host_name: str,
        password: str = "",
        ssl_context: Optional[ssl.SSLContext] = None,
        bind: str = config.BIND_ADDRESS,
        port: int = config.DEFAULT_PORT,
        output: Callable[[str], None] = print_above_input,
        password_delay: float = config.PASSWORD_DELAY,
    ):
        self.password = password
        self.ssl_context = ssl_context
        self.bind = bind
        self.port = port
        self.output = output              # where the host's screen output goes (a list in tests)
        self.password_delay = password_delay

        self._participants: dict[str, Participant] = {}
        self._lock = threading.Lock()      # guards _participants
        self._send_lock = threading.Lock() # one write to a socket at a time
        self._color_i = 0
        self._sock: Optional[socket.socket] = None
        self._running = threading.Event()

        with self._lock:
            self.host = self._register(host_name, None)

    # ---------- lifecycle ----------

    def start(self) -> int:
        """Open the listening socket and start accepting. Returns the actual port."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.bind, self.port))
        sock.listen()
        self._sock = sock
        self.port = sock.getsockname()[1]   # port 0 → the OS picks a free one (used in tests)
        self._running.set()
        threading.Thread(target=self._accept_loop, daemon=True).start()
        return self.port

    def stop(self) -> None:
        """Say goodbye, disconnect everyone, close the listening socket."""
        if not self._running.is_set():
            return
        self._running.clear()
        self.broadcast(note(f"{self.host.tag} closed the chat"), exclude=self.host)
        for p in self.participants():
            if not p.is_host:
                self._hard_close(p.conn)
        if self._sock:
            self._sock.close()

    # ---------- participants ----------

    def _register(self, name: str, conn: Optional[socket.socket]) -> Participant:
        """Add a participant. Caller must hold self._lock."""
        p = Participant(name, config.COLORS[self._color_i % len(config.COLORS)], conn)
        self._color_i += 1
        self._participants[name] = p
        return p

    def participants(self) -> list[Participant]:
        with self._lock:
            return list(self._participants.values())

    def get(self, name: str) -> Optional[Participant]:
        with self._lock:
            return self._participants.get(name)

    def kick(self, name: str) -> bool:
        """Disconnect a participant. False if there's no such participant (or it's the host)."""
        p = self.get(name)
        if p is None or p.is_host:
            return False
        p.kicked = True
        self.send_line(p, note("you were kicked by the host"))
        self._hard_close(p.conn)   # their thread sees EOF and cleans up
        return True

    # ---------- output ----------

    def send_line(self, p: Participant, text: str) -> None:
        """Show one line to one participant, above their input line."""
        if p.is_host:
            self.output(text)
            return
        try:
            self._send_raw(p.conn, insert_above(text))
        except OSError:
            self._hard_close(p.conn)  # dead socket: their thread will clean up

    def broadcast(self, text: str, exclude: Optional[Participant] = None) -> None:
        """Show a line to everyone (host included) except `exclude`."""
        for p in self.participants():
            if p is not exclude:
                self.send_line(p, text)

    def _send_raw(self, conn: socket.socket, text: str) -> None:
        with self._send_lock:
            conn.sendall(text.encode())

    def _prompt(self, p: Participant) -> None:
        """Draw a fresh 'name: ' input line for an nc/openssl participant."""
        try:
            self._send_raw(p.conn, f"{p.name}: ")
        except OSError:
            pass

    @staticmethod
    def _hard_close(conn: socket.socket) -> None:
        """Cut a connection from another thread.

        socket.socket.shutdown (not conn.shutdown) so a TLS socket isn't
        unwrapped while its own thread is in the middle of reading.
        """
        try:
            socket.socket.shutdown(conn, socket.SHUT_RDWR)
        except OSError:
            pass

    # ---------- host console ----------

    def handle_host_input(self, line: str) -> bool:
        """Process one line typed by the host. Returns False when the host types exit."""
        text = clean(line)
        if not text:
            return True
        if text.lower() == "exit":
            return False
        if text.startswith("/"):
            reply = commands.handle(self, self.host, text)
            if reply:
                self.output(reply)
            return True
        self.broadcast(f"[{ts()}] {self.host.tag}: {text}", exclude=self.host)
        return True

    def run_console(self) -> None:
        """Read the host's keyboard until exit / Ctrl+C / Ctrl+D, then stop."""
        while True:
            try:
                line = input(f"{self.host.name}: ")
            except (EOFError, KeyboardInterrupt):
                break
            if not self.handle_host_input(line):
                break
        self.stop()

    # ---------- clients ----------

    def _accept_loop(self) -> None:
        while self._running.is_set():
            try:
                conn, addr = self._sock.accept()
            except OSError:
                break  # listening socket closed
            threading.Thread(target=self._serve, args=(conn, addr), daemon=True).start()

    def _serve(self, conn: socket.socket, addr) -> None:
        """Everything for one connection, from handshake to goodbye."""
        self.output(note(f"connection from {addr[0]}"))

        if self.ssl_context:
            try:
                conn.settimeout(config.HANDSHAKE_TIMEOUT)
                conn = self.ssl_context.wrap_socket(conn, server_side=True)
                conn.settimeout(None)
            except OSError:  # ssl.SSLError is an OSError too
                self.output(note(f"{addr[0]}: TLS handshake failed (joined with nc instead of openssl?)"))
                conn.close()
                return

        reader = conn.makefile("r", encoding="utf-8", errors="replace")
        p: Optional[Participant] = None
        try:
            self._send_raw(conn, f"Welcome to {self.host.name}'s chat!\n")
            if self.password and not self._check_password(conn, reader, addr):
                return
            p = self._ask_name(conn, reader)
            if p is None:
                return

            self.send_line(p, note(f"hi {p.tag}! /help for commands, exit to leave"))
            self.send_line(p, commands.who(self))
            self.broadcast(note(f"{p.tag} joined the chat"), exclude=p)
            self._prompt(p)

            for line in reader:            # one line per message, until EOF
                msg = clean(line)
                if msg.lower() == "exit":
                    break
                if msg.startswith("/"):
                    reply = commands.handle(self, p, msg)
                    if reply:
                        self.send_line(p, reply)
                elif msg:
                    self.broadcast(f"[{ts()}] {p.tag}: {msg}", exclude=p)
                self._prompt(p)
        except (OSError, ValueError):
            pass  # connection dropped / socket closed under us
        finally:
            if p is not None:
                with self._lock:
                    self._participants.pop(p.name, None)
                how = "was kicked" if p.kicked else "left the chat"
                self.broadcast(note(f"{p.tag} {how}"))
            try:
                conn.close()
            except OSError:
                pass

    def _check_password(self, conn, reader, addr) -> bool:
        self._send_raw(conn, "Password: ")
        for attempt in range(1, config.MAX_PASSWORD_TRIES + 1):
            line = reader.readline()
            if not line:
                return False
            # constant-time comparison: response time doesn't leak how much of the guess was right
            if hmac.compare_digest(line.rstrip("\r\n").encode(), self.password.encode()):
                return True
            time.sleep(self.password_delay)
            self.output(note(f"wrong password from {addr[0]}"))
            if attempt < config.MAX_PASSWORD_TRIES:
                self._send_raw(conn, "Wrong password, try again: ")
        self._send_raw(conn, "Wrong password. Bye.\n")
        return False

    def _ask_name(self, conn, reader) -> Optional[Participant]:
        self._send_raw(conn, "Enter your name: ")
        while True:
            line = reader.readline()
            if not line:
                return None
            name = clean(line)
            if config.NAME_RE.fullmatch(name):
                with self._lock:
                    if name not in self._participants:
                        return self._register(name, conn)
            self._send_raw(conn, "Name must be 1-20 letters/digits/_/-, no spaces, not taken. Try another: ")
