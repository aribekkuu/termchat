"""Default settings in one place."""
import re

DEFAULT_PORT = 33000
BIND_ADDRESS = "0.0.0.0"          # listen on every network interface

MAX_PASSWORD_TRIES = 3
PASSWORD_DELAY = 1.0              # seconds to wait after a wrong password (slows brute force)
HANDSHAKE_TIMEOUT = 10            # seconds allowed for the TLS handshake

# 1-20 letters (any alphabet), digits, "_" or "-". No spaces, so "/msg name text" parses.
NAME_RE = re.compile(r"[\w-]{1,20}")

# ANSI color codes handed out to nicknames in turn
COLORS = [32, 33, 34, 35, 36, 91, 92, 93, 94, 95, 96, 31]
