"""Slash commands. Each handler gets (server, sender, args) and returns a reply for the sender or None."""
from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Optional

from .terminal import note, ts

if TYPE_CHECKING:
    from .server import ChatServer, Participant


def handle(server: ChatServer, sender: Participant, line: str) -> Optional[str]:
    """Run the command in `line` (already cleaned, starts with '/')."""
    parts = line.split(maxsplit=2)
    name, args = parts[0].lower(), parts[1:]
    handler = COMMANDS.get(name)
    if handler is None:
        return note(f"unknown command {name}, try /help")
    return handler(server, sender, args)


def who(server: ChatServer) -> str:
    people = server.participants()
    return note(f"online ({len(people)}): " + ", ".join(p.tag for p in people))


def _help(server: ChatServer, sender: Participant, args: list[str]) -> str:
    cmds = ["/who — who's online", "/msg name text — private message"]
    if sender.is_host:
        cmds.append("/kick name — remove someone")
    cmds.append("exit — leave")
    # one line: insert_above draws exactly one line above the input
    return note(" | ".join(cmds))


def _who(server: ChatServer, sender: Participant, args: list[str]) -> str:
    return who(server)


def _msg(server: ChatServer, sender: Participant, args: list[str]) -> str:
    if len(args) < 2:
        return note("usage: /msg name text")
    target = server.get(args[0])
    if target is None:
        return note(f"no one named {args[0]}")
    if target is sender:
        return note("you can't message yourself")
    server.send_line(target, f"[{ts()}] \033[3m(private)\033[0m {sender.tag}: {args[1]}")
    return f"[{ts()}] \033[3m(private → {target.tag})\033[0m {args[1]}"


def _kick(server: ChatServer, sender: Participant, args: list[str]) -> Optional[str]:
    if not sender.is_host:
        return note("only the host can kick")
    if not args:
        return note("usage: /kick name")
    if not server.kick(args[0]):
        return note(f"no one named {args[0]}")
    return None  # the leave notice is broadcast when their connection closes


COMMANDS: dict[str, Callable[..., Optional[str]]] = {
    "/help": _help,
    "/who": _who,
    "/msg": _msg,
    "/kick": _kick,
}
