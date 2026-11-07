"""Joining, messaging, leaving."""


def test_join_is_announced_to_others(make_server, make_client, host_sees):
    server = make_server()
    dauren = make_client(server, "dauren")
    make_client(server, "aru")
    dauren.read_until("aru joined the chat")
    host_sees(server, "aru joined the chat")


def test_message_reaches_everyone_but_the_author(make_server, make_client, host_sees):
    server = make_server()
    dauren = make_client(server, "dauren")
    aru = make_client(server, "aru")

    dauren.send("salam")
    aru.read_until("dauren: salam")
    host_sees(server, "dauren: salam")
    assert "dauren: salam" not in dauren.received_within(0.3)


def test_host_message_reaches_participants(make_server, make_client):
    server = make_server()
    dauren = make_client(server, "dauren")
    server.handle_host_input("hello from host")
    dauren.read_until("alibek: hello from host")


def test_messages_have_timestamps(make_server, make_client):
    server = make_server()
    dauren = make_client(server, "dauren")
    aru = make_client(server, "aru")
    dauren.send("hi")
    buf = aru.read_until("dauren: hi")
    line = next(l for l in buf.splitlines() if "dauren: hi" in l)
    assert line.lstrip().startswith("[") and line.split("]")[0].count(":") == 1   # "[HH:MM]"


def test_exit_announces_leave(make_server, make_client):
    server = make_server()
    dauren = make_client(server, "dauren")
    aru = make_client(server, "aru")
    dauren.send("exit")
    aru.read_until("dauren left the chat")
    assert server.get("dauren") is None


def test_closing_terminal_announces_leave(make_server, make_client):
    server = make_server()
    dauren = make_client(server, "dauren")
    aru = make_client(server, "aru")
    dauren.close()                      # like closing the nc window
    aru.read_until("dauren left the chat")


def test_taken_name_is_rejected(make_server, make_client):
    server = make_server()
    make_client(server, "dauren")
    other = make_client(server, "x", join=False)
    other.read_until("Enter your name: ")
    other.send("dauren")
    other.read_until("not taken. Try another")


def test_host_name_is_taken_too(make_server, make_client):
    server = make_server()
    c = make_client(server, "x", join=False)
    c.read_until("Enter your name: ")
    c.send("alibek")
    c.read_until("Try another")


def test_name_with_spaces_is_rejected(make_server, make_client):
    server = make_server()
    c = make_client(server, "x", join=False)
    c.read_until("Enter your name: ")
    c.send("two words")
    c.read_until("Try another")


def test_host_stop_disconnects_everyone(make_server, make_client):
    server = make_server()
    dauren = make_client(server, "dauren")
    server.stop()
    dauren.read_until("alibek closed the chat")
    assert dauren.is_closed()
