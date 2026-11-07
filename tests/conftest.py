"""Shared fixtures: a real server on a free port and simple socket clients."""
import shutil
import socket
import ssl
import subprocess
import time

import pytest

from termchat import ChatServer
from termchat.terminal import strip_ansi


class Client:
    """A test participant — a raw socket, exactly what nc would be."""

    def __init__(self, port: int, tls: bool = False):
        sock = socket.create_connection(("127.0.0.1", port), timeout=3)
        if tls:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE   # self-signed test certificate
            sock = ctx.wrap_socket(sock)
        self.sock = sock
        self.buffer = ""                      # everything received, ANSI codes stripped
        self.raw = b""                        # everything received, exactly as sent

    def _feed(self, data: bytes) -> None:
        self.raw += data
        self.buffer += strip_ansi(data.decode("utf-8", "replace"))

    def send(self, line: str) -> None:
        self.sock.sendall((line + "\n").encode())

    def read_until(self, text: str, timeout: float = 3.0) -> str:
        """Wait until `text` has arrived. Returns the whole buffer."""
        deadline = time.monotonic() + timeout
        while text not in self.buffer:
            left = deadline - time.monotonic()
            if left <= 0:
                raise AssertionError(f"timed out waiting for {text!r}; got:\n{self.buffer}")
            self.sock.settimeout(left)
            try:
                data = self.sock.recv(4096)
            except socket.timeout:
                continue
            if not data:
                raise AssertionError(f"connection closed before {text!r}; got:\n{self.buffer}")
            self._feed(data)
        return self.buffer

    def received_within(self, seconds: float = 0.3) -> str:
        """Everything that arrives in the next `seconds` (to check something did NOT arrive)."""
        end = time.monotonic() + seconds
        start = len(self.buffer)
        while (left := end - time.monotonic()) > 0:
            self.sock.settimeout(left)
            try:
                data = self.sock.recv(4096)
            except socket.timeout:
                break
            if not data:
                break
            self._feed(data)
        return self.buffer[start:]

    def is_closed(self, timeout: float = 3.0) -> bool:
        """True if the server closes the connection within `timeout`."""
        self.sock.settimeout(timeout)
        try:
            while True:
                data = self.sock.recv(4096)
                if not data:
                    return True
                self._feed(data)
        except socket.timeout:
            return False
        except OSError:  # reset / TLS shutdown — also closed
            return True

    def close(self) -> None:
        self.sock.close()


@pytest.fixture
def make_server():
    """Factory: make_server(password="...", ssl_context=...) -> started ChatServer.

    The host's screen output is collected in server.host_screen.
    """
    servers = []

    def factory(**kwargs) -> ChatServer:
        screen: list[str] = []
        kwargs.setdefault("password_delay", 0)
        server = ChatServer("alibek", bind="127.0.0.1", port=0, output=screen.append, **kwargs)
        server.host_screen = screen
        server.start()
        servers.append(server)
        return server

    yield factory
    for s in servers:
        s.stop()


@pytest.fixture
def make_client():
    """Factory: make_client(server, "dauren", password=None, tls=False) -> joined Client."""
    clients = []

    def factory(server: ChatServer, name: str, password=None, tls: bool = False, join: bool = True) -> Client:
        c = Client(server.port, tls=tls)
        clients.append(c)
        if not join:
            return c
        if password is not None:
            c.read_until("Password: ")
            c.send(password)
        c.read_until("Enter your name: ")
        c.send(name)
        c.read_until(f"{name}: ")      # the input prompt means we're in
        return c

    yield factory
    for c in clients:
        c.close()


@pytest.fixture
def host_sees():
    """host_sees(server, "text") — wait until the host's console shows text."""

    def wait(server: ChatServer, text: str, timeout: float = 3.0) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if any(text in strip_ansi(line) for line in server.host_screen):
                return
            time.sleep(0.02)
        raise AssertionError(f"host never saw {text!r}; screen:\n" + "\n".join(map(strip_ansi, server.host_screen)))

    return wait


@pytest.fixture(scope="session")
def cert_files(tmp_path_factory):
    """A throwaway self-signed certificate (needs the openssl command)."""
    if shutil.which("openssl") is None:
        pytest.skip("openssl not installed")
    d = tmp_path_factory.mktemp("tls")
    cert, key = d / "cert.pem", d / "key.pem"
    subprocess.run(
        ["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
         "-keyout", str(key), "-out", str(cert), "-days", "1", "-subj", "/CN=test"],
        check=True, capture_output=True,
    )
    return str(cert), str(key)
