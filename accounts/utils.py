"""
Utility functions for account operations.
"""
import io
import base64

import qrcode


def generate_credentials_qr(
    host: str,
    port: int,
    username: str,
    password: str,
) -> str:
    """
    Generate a base64-encoded PNG QR code containing SSH credentials.
    Returns a data-URI string suitable for embedding in HTML/Telegram.
    """
    text = f"ssh://{username}:{password}@{host}:{port}"
    img = qrcode.make(text, box_size=6, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/png;base64,{b64}"


def generate_config_text(
    host: str,
    port: int,
    username: str,
    password: str,
) -> str:
    """Generate a copyable SSH config snippet."""
    return (
        f"Host vpn-{username}\n"
        f"    HostName {host}\n"
        f"    Port {port}\n"
        f"    User {username}\n"
        f"    # Password: {password}\n"
    )
