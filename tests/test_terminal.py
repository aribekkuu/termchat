from termchat.terminal import clean, insert_above, paint, strip_ansi


def test_clean_removes_escape_codes():
    assert clean("\x1b[2Jhello") == "[2Jhello"   # ESC is gone, so it's harmless text


def test_clean_removes_carriage_return_and_backspace():
    assert clean("abc\r\bdef\n") == "abcdef"


def test_clean_keeps_unicode():
    assert clean("  привет 👋 ") == "привет 👋"


def test_insert_above_wraps_text_with_cursor_save_and_restore():
    seq = insert_above("hi")
    assert "hi" in seq
    assert seq.index("\0337") < seq.index("hi") < seq.index("\0338")


def test_paint_and_strip_ansi_roundtrip():
    assert strip_ansi(paint("dauren", 32)) == "dauren"
