"""Command-line entry point: `uv run termchat` or `python -m termchat`."""
import argparse
import getpass
import socket
import sys

from . import config, tls
from .server import ChatServer
from .terminal import clean


def local_ip() -> str:
    """This machine's address in the local network (a UDP 'connect' sends nothing)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="termchat", description="Multi-user terminal chat server")
    p.add_argument("--port", type=int, default=config.DEFAULT_PORT, help="port to listen on (default 33000)")
    p.add_argument("--ssl", action="store_true", help="encrypt connections with TLS")
    p.add_argument("--cert", default="cert.pem", help="TLS certificate (default cert.pem)")
    p.add_argument("--key", default="key.pem", help="TLS private key (default key.pem)")
    p.add_argument("--password", help="chat password (otherwise asked at startup; empty = open chat)")
    return p.parse_args(argv)


def main(argv=None) -> None:
    args = parse_args(argv)

    ssl_context = None
    if args.ssl:
        try:
            ssl_context = tls.server_context(args.cert, args.key)
        except FileNotFoundError as e:
            sys.exit(str(e))

    while True:
        name = clean(input("Your name: "))
        if config.NAME_RE.fullmatch(name):
            break
        print("Name must be 1-20 letters/digits/_/-, no spaces.")

    password = args.password
    if password is None:
        password = getpass.getpass("Chat password (Enter = no password): ")

    server = ChatServer(name, password, ssl_context, port=args.port)
    try:
        server.start()
    except OSError as e:
        sys.exit(f"Can't listen on port {args.port}: {e}")

    ip = local_ip()
    if ssl_context:
        print(f"Chat is open (TLS). Join: openssl s_client -quiet -connect {ip}:{server.port}")
    else:
        print(f"Chat is open. Join: nc {ip} {server.port}")
    print("Password: " + ("on" if password else "off — anyone who can reach the port can join"))
    print("/help for commands, exit to close the chat")

    server.run_console()
    print("\nChat closed.")


if __name__ == "__main__":
    main()
