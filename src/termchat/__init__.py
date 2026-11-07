"""termchat — a multi-user terminal chat that participants join with nc or openssl."""

from .server import ChatServer, Participant

__all__ = ["ChatServer", "Participant"]
__version__ = "1.0.0"
