"""Password, input sanitizing, TLS."""
import socket

from termchat import tls


# ---------- password ----------

def test_open_chat_asks_no_password(make_server, make_client):
    server = make_server()
    c = make_client(server, "x", join=False)
    buf = c.read_until("Enter your name: ")
    assert "Password" not in buf


def test_correct_password_lets_you_in(make_server, make_client):
    server = make_server(password="secret")
    make_client(server, "dauren", password="secret")
    assert server.get("dauren") is not None


def test_second_try_works(make_server, make_client):
    server = make_server(password="secret")
    c = make_client(server, "x", join=False)
    c.read_until("Password: ")
    c.send("wrong")
    c.read_until("try again: ")
    c.send("secret")
    c.read_until("Enter your name: ")


def test_three_wrong_passwords_disconnect(make_server, make_client, host_sees):
    server = make_server(password="secret")
    c = make_client(server, "x", join=False)
    c.read_until("Password: ")
    for guess in ("a", "b", "c"):
        c.send(guess)
    c.read_until("Wrong password. Bye.")
    assert c.is_closed()
    host_sees(server, "wrong password from 127.0.0.1")


# ---------- sanitizing ----------

def test_escape_codes_are_not_forwarded(make_server, make_client):
    server = make_server()
    attacker = make_client(server, "mallory")
    victim = make_client(server, "dauren")

    # try to clear the victim's screen and forge a line from the host
    attacker.sock.sendall(b"\x1b[2J\x1b[1A\ralibek: send me your password\n")
    victim.read_until("send me your password")

    line = next(l for l in victim.buffer.splitlines() if "send me your password" in l)
    assert "mallory:" in line            # still attributed to the real author
    assert b"\x1b[2J" not in victim.raw  # the escape codes never reached the victim
    assert b"\x1b[1A" not in victim.raw


# ---------- TLS ----------

def test_tls_chat_works(make_server, make_client, cert_files):
    server = make_server(ssl_context=tls.server_context(*cert_files), password="pw")
    dauren = make_client(server, "dauren", password="pw", tls=True)
    aru = make_client(server, "aru", password="pw", tls=True)
    dauren.send("encrypted hi")
    aru.read_until("dauren: encrypted hi")


def test_plain_client_cannot_join_tls_server(make_server, cert_files):
    server = make_server(ssl_context=tls.server_context(*cert_files))
    sock = socket.create_connection(("127.0.0.1", server.port), timeout=3)
    sock.sendall(b"dauren\n")           # nc-style plain text instead of a TLS handshake
    sock.settimeout(3)
    try:
        data = sock.recv(4096)
    except OSError:
        data = b""
    assert b"Welcome" not in data
    assert server.get("dauren") is None
    sock.close()


def test_missing_certificate_gives_a_hint(tmp_path):
    try:
        tls.server_context(str(tmp_path / "nope.pem"), str(tmp_path / "nope.key"))
    except FileNotFoundError as e:
        assert "openssl req" in str(e)
    else:
        raise AssertionError("expected FileNotFoundError")
