"""Slash commands: /who, /msg, /kick, /help."""


def test_who_lists_everyone(make_server, make_client):
    server = make_server()
    make_client(server, "dauren")
    aru = make_client(server, "aru")
    aru.send("/who")
    aru.read_until("online (3): alibek, dauren, aru")


def test_private_message_only_reaches_the_target(make_server, make_client, host_sees):
    server = make_server()
    dauren = make_client(server, "dauren")
    aru = make_client(server, "aru")
    bob = make_client(server, "bob")

    dauren.send("/msg aru secret")
    aru.read_until("(private) dauren: secret")
    dauren.read_until("(private → aru) secret")
    assert "secret" not in bob.received_within(0.3)
    assert not any("secret" in line for line in server.host_screen)


def test_private_message_to_host(make_server, make_client, host_sees):
    server = make_server()
    dauren = make_client(server, "dauren")
    dauren.send("/msg alibek psst")
    host_sees(server, "(private) dauren: psst")


def test_private_message_to_unknown_name(make_server, make_client):
    server = make_server()
    dauren = make_client(server, "dauren")
    dauren.send("/msg ghost hi")
    dauren.read_until("no one named ghost")


def test_host_can_kick(make_server, make_client):
    server = make_server()
    dauren = make_client(server, "dauren")
    aru = make_client(server, "aru")

    server.handle_host_input("/kick dauren")
    dauren.read_until("you were kicked by the host")
    assert dauren.is_closed()
    aru.read_until("dauren was kicked")
    assert server.get("dauren") is None


def test_participant_cannot_kick(make_server, make_client):
    server = make_server()
    dauren = make_client(server, "dauren")
    make_client(server, "aru")
    dauren.send("/kick aru")
    dauren.read_until("only the host can kick")
    assert server.get("aru") is not None


def test_help_shows_kick_only_to_host(make_server, make_client, host_sees):
    server = make_server()
    dauren = make_client(server, "dauren")
    dauren.send("/help")
    assert "/kick" not in dauren.read_until("/msg name text")
    server.handle_host_input("/help")
    host_sees(server, "/kick name")


def test_unknown_command(make_server, make_client):
    server = make_server()
    dauren = make_client(server, "dauren")
    dauren.send("/dance")
    dauren.read_until("unknown command /dance")
