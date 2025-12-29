from fastapi import Request
from app.settings import defaults, username_not_allowed

import os

def followers_obj (followers, version, blocked = False):
    return {
        "followers": followers,
        "version": version,
        **({"error": username_not_allowed} if blocked else {})
    }

def get_var(request: Request, key):
    if get_os_var("INSTAGRAM_USERNAME"):
        return os.getenv(key) or defaults[key]
    return request.cookies.get(key) or defaults[key]

def get_os_var(key, default=None):
    return os.getenv(key) or default

def username_blocked(username):
    allowed_usernames = os.getenv("ALLOWED_USERNAMES")
    allowed = [x.strip() for x in allowed_usernames.split(",")] if allowed_usernames and allowed_usernames.strip() else None
    return bool(allowed) and username not in allowed

def font_color_from_bg_color(bg_hex: str) -> str:
    """
    Given a background hex color like "#a1b2c3",
    return "#000000" or "#FFFFFF".
    If the color is invalid, return "#FFFFFF".
    """
    if not isinstance(bg_hex, str):
        return "#FFFFFF"

    bg_hex = bg_hex.lstrip("#")

    # Validate: must be 6 hex chars
    if len(bg_hex) != 6 or any(c not in "0123456789abcdefABCDEF" for c in bg_hex):
        return "#FFFFFF"

    try:
        r, g, b = tuple(int(bg_hex[i:i+2], 16) for i in (0, 2, 4))
    except ValueError:
        return "#FFFFFF"

    # Convert RGB → relative luminance (WCAG)
    def channel(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    luminance = 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)

    # White for dark backgrounds, black for light backgrounds
    return "#FFFFFF" if luminance < 0.6 else "#000000"