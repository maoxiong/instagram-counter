from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

import os
import redis
import requests

app = FastAPI(title="Instagram Follower Counter")
templates = Jinja2Templates(directory="app/templates")

load_dotenv()

app.mount("/static", StaticFiles(directory="app/static"), name="static")

defaults = {
    "INSTAGRAM_USERNAME": "softcatmemes",
    "REFRESH_INTERVAL": 10,
    "MINIMUM_DIGITS": 5,
    "PAD_CHARACTER": "0",
    "FONT_SIZE": "4",
    "FONT_FAMILY": "",
    "PAGE_BG": "#000000",
    "FLIP_BG": "#333232",
    "FLIP_FG": "#edebeb",
    "SHOW_IG_LOGO": "1",
    "SKIP_ANIMATION": "0",
}

# use redis if supplied
redis_url = os.getenv("REDIS_URL")

# So that instagram doesn't block your scraping IP
# It's really not advised to set this below 5
refresh_fallback = 5
minimum_refresh_interval = int(os.getenv("MINIMUM_REFRESH_INTERVAL") or refresh_fallback) or refresh_fallback

def get_var(request: Request, key):
    if os.getenv("INSTAGRAM_USERNAME"):
        return os.getenv(key) or defaults[key]
    else:
        return request.cookies.get(key) or defaults[key]


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    interval = max(minimum_refresh_interval, int(get_var(request, "REFRESH_INTERVAL")))

    pad_character = get_var(request, "PAD_CHARACTER")
    digits = int(get_var(request, "MINIMUM_DIGITS"))

    padding = pad_character * digits
    skip_animation = get_var(request, "SKIP_ANIMATION") == "1"
    transform = f"arrive(.2) -&gt; round -&gt; pad('{ padding }') -&gt; split -&gt; delay(rtl, 100, 150)" if not skip_animation else f"pad('{ padding }')"

    start_value = followers(request).get("followers", 0)
    # if the start value is divisible by 10, subtract 10 from it so that there will be a change on boot up
    if start_value > 0 and start_value % 10 == 0:
        start_value -= 10
    # round down to the nearest 10 (giving us a nice animation run-up)
    start_value = (start_value // 10) * 10

    settings_enabled = bool(os.getenv("INSTAGRAM_USERNAME") or request.cookies.get("LOCK_SETTINGS") == "1") is False

    return templates.TemplateResponse(
        "home.html",
        {
            "request": request,  # required
            "instagram_username": get_var(request,"INSTAGRAM_USERNAME"),
            "refresh_interval": interval,
            "minimum_refresh_interval": minimum_refresh_interval,
            "start_value": start_value,
            "transform": transform,
            "font_size": get_var(request,"FONT_SIZE"),
            "font_family": get_var(request,"FONT_FAMILY"),
            "page_bg": get_var(request,"PAGE_BG"),
            "flip_bg": get_var(request,"FLIP_BG"),
            "flip_fg": get_var(request,"FLIP_FG"),
            "show_ig_logo": get_var(request,"SHOW_IG_LOGO") == "1",
            "skip_animation": skip_animation,
            "pad_character": pad_character,
            "minimum_digits": digits,
            "defaults": defaults,
            "settings_enabled": settings_enabled
        }
    )

@app.get("/api/followers")
def followers(request: Request):

    return {"followers":360}

    username = get_var(request, "INSTAGRAM_USERNAME")
    redis_key = f"instagram_counter_${username}"

    # if redis url, try getting the followers from that first
    if redis_url:
        try:
            r = redis.from_url(redis_url)
            follower_count = r.get(redis_key)
            if follower_count:
                return {"followers": int(follower_count), "redis": True}

        except Exception as e:
            print(f"Redis error (Get): {e}")

    url = "https://i.instagram.com/api/v1/users/web_profile_info/"

    headers = {
        "User-Agent": "Instagram 76.0.0.15.395 Android (24/7.0; 640dpi; 1440x2560; samsung; SM-G930F; herolte; samsungexynos8890; en_US; 138226743)"
    }

    try:
        resp = requests.get(url, headers=headers, params={"username": username})
        resp.raise_for_status()         # raises error on 4xx/5xx

        json_data = resp.json()

        followers = (
            json_data.get("data", {})
            .get("user", {})
            .get("edge_followed_by", {})
            .get("count", 0)
        )

        if redis_url:
            try:
                r.set(redis_key, followers, ex=minimum_refresh_interval * 60)
            except Exception as e:
                print(f"Redis error (Set): {e}")

        return {"followers": followers, "redis": False}

    except Exception as e:
        return {"error": str(e)}
