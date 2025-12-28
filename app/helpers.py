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