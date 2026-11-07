"""TLS (SSL) setup for encrypted mode."""
import ssl

CERT_HINT = (
    "Certificate not found. Create a self-signed one (once, in the current folder):\n"
    '  openssl req -x509 -newkey rsa:2048 -nodes -keyout key.pem -out cert.pem -days 365 -subj "/CN=chat"'
)


def server_context(cert_path: str, key_path: str) -> ssl.SSLContext:
    """TLS context for the server. Raises FileNotFoundError with a helpful hint."""
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    try:
        ctx.load_cert_chain(cert_path, key_path)
    except (OSError, ssl.SSLError) as e:
        raise FileNotFoundError(CERT_HINT) from e
    return ctx
