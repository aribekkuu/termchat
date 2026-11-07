"""Text and terminal helpers: timestamps, colors, sanitizing, the input-line trick."""
import re
from datetime import datetime

ANSI_RE = re.compile(r"\x1b(\[[0-9;]*[A-Za-z]|[78DM])")


def ts() -> str:
    """Current time as HH:MM."""
    return datetime.now().strftime("%H:%M")


def paint(text: str, color: int) -> str:
    """Bold, colored text."""
    return f"\033[1;{color}m{text}\033[0m"


def note(text: str) -> str:
    """A system notice: timestamp + dimmed text."""
    return f"[{ts()}] \033[2m*** {text}\033[0m"


def clean(text: str) -> str:
    """Drop control characters (ESC, \\r, \\b, ...) and surrounding whitespace.

    Everything a participant sends goes through this. Without it, a message
    containing ANSI escape codes could clear other people's screens or move
    the cursor to forge a line that looks like it came from someone else.
    """
    return "".join(ch for ch in text if ch.isprintable()).strip()


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences (for logs and tests)."""
    return ANSI_RE.sub("", text)


def insert_above(text: str) -> str:
    """Escape sequence that prints `text` on a new line ABOVE the input line.

    nc and openssl have no UI of their own, so the server draws one remotely.
    Whatever the person has half-typed stays where it is:

      ESC D, ESC M   make sure there is a line below (scrolls if at the bottom)
      ESC 7          save the cursor position
      \\r ESC [1L     go to column 0 and insert an empty line (input line moves down)
      text           print the message into the freed line
      ESC 8, ESC D   restore the cursor and move one line down, back to the input
    """
    return f"\033D\033M\0337\r\033[1L{text}\0338\033D"
