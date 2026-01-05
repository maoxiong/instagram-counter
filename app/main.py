from fastapi import FastAPI, Request, Response
from fastapi.templating import Jinja2Templates
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from app.helpers import followers_obj, get_var, get_os_var, username_blocked, font_color_from_bg_color
from app.settings import defaults, app_name, instagram_url, useragent_string, redis_header_key, \
    maximum_refresh_interval, instagram_username_max_length, maximum_font_size

import redis
import requests

# Used for auto updates
VERSION_CODE = "2.7.0"

app = FastAPI(title=get_os_var("APP_NAME", app_name))
templates = Jinja2Templates(directory="app/templates", trim_blocks=True, lstrip_blocks=True)

load_dotenv()

app.mount("/static", StaticFiles(directory="app/static"), name="static")

# So that instagram doesn't block your scraping IP
# Can be overridden with MINIMUM_REFRESH_INTERVAL
minimum_refresh_interval = int(get_os_var("MINIMUM_REFRESH_INTERVAL", 5)) or 5

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse("app/static/favicon.ico")

@app.get("/", response_class=HTMLResponse)
def home(request: Request, response: Response):
    interval = max(minimum_refresh_interval, int(get_var(request, "REFRESH_INTERVAL")))

    pad_character = get_var(request, "PAD_CHARACTER")
    digits = int(get_var(request, "MINIMUM_DIGITS"))

    padding = pad_character * digits
    skip_animation = get_var(request, "SKIP_ANIMATION") == "1"
    transform = f"arrive(.2) -&gt; round -&gt; pad('{ padding }') -&gt; split -&gt; delay(rtl, 100, 150)" if not skip_animation else f"pad('{ padding }')"

    show_ig_logo = get_var(request,"SHOW_IG_LOGO") == "1"

    start_value = followers(request, response).get("followers", 0)
    # if the start value is divisible by 10, subtract 10 from it so that there will be a change on boot up
    if start_value > 0 and start_value % 10 == 0:
        start_value -= 10
    # round down to the nearest 10 (giving us a nice animation run-up)
    start_value = (start_value // 10) * 10

    # now build the form components
    settings = [
        {"name": "INSTAGRAM_USERNAME", "label": "Instagram username", "type": "text", "maxlength": instagram_username_max_length, "value": get_var(request, "INSTAGRAM_USERNAME"), "default": defaults["INSTAGRAM_USERNAME"]},
        {"name": "FONT_SIZE", "label": "Font size", "type": "slider", "min": 1, "max": maximum_font_size, "step": 1, "value": get_var(request, "FONT_SIZE"), "default": defaults["FONT_SIZE"]},
        {"name": "FONT_FAMILY", "label": "Font family", "type": "text", "maxlength": 50, "value": get_var(request, "FONT_FAMILY"), "default": defaults["FONT_FAMILY"]},
        {"name": "PAD_CHARACTER", "label": "Padding character", "type": "text", "maxlength": 1, "value": pad_character, "default": defaults["PAD_CHARACTER"]},
        {"name": "MINIMUM_DIGITS", "label": "Minimum digits", "type": "slider", "min": 1, "max": 10, "step": 1, "value": digits, "default": defaults["MINIMUM_DIGITS"]},
        {"name": "FLIP_BG", "label": "Flipper background", "type": "color", "value": get_var(request, "FLIP_BG"), "default": defaults["FLIP_BG"]},
        {"name": "FLIP_FG", "label": "Flipper digit", "type": "color", "value": get_var(request, "FLIP_FG"), "default": defaults["FLIP_FG"]},
        {"name": "PAGE_BG", "label": "Page background", "type": "color", "value": get_var(request, "PAGE_BG"), "default": defaults["PAGE_BG"]},
        {"name": "SHOW_IG_LOGO", "label": "Show Instagram logo", "type": "checkbox", "value": show_ig_logo, "default": defaults["SHOW_IG_LOGO"]},
        {"name": "SKIP_ANIMATION", "label": "Skip animation", "type": "checkbox", "value": skip_animation, "default": defaults["SKIP_ANIMATION"]},
        {"name": "REFRESH_INTERVAL", "label": "Refresh Interval (mins)", "type": "slider", "min": minimum_refresh_interval, "max": maximum_refresh_interval, "step": 1, "value": interval, "default": defaults["REFRESH_INTERVAL"]},
    ]
    settings_by_name = {s["name"]: s for s in settings}
    settings_enabled = bool(get_os_var("INSTAGRAM_USERNAME") or request.cookies.get("LOCK_SETTINGS") == "1") is False

    return templates.TemplateResponse(
        "home.html",
        {
            "request": request,  # required
            "version_code": VERSION_CODE,
            "app_name":get_os_var("APP_NAME", app_name),
            "start_value": start_value,
            "transform": transform,
            "text_color": font_color_from_bg_color(get_var(request, "PAGE_BG")),
            "settings": settings,
            "settings_by_name": settings_by_name,
            "settings_enabled": settings_enabled
        }
    )

@app.get("/api/followers")
def followers(request: Request, response: Response):

    username = get_var(request, "INSTAGRAM_USERNAME")

    if username_blocked(username):
        return followers_obj(0, VERSION_CODE, True)

    # use redis if supplied
    redis_url = get_os_var("REDIS_URL")
    redis_key = f"instagram_counter_${username}"

    # if redis url, try getting the followers from that first
    if redis_url:
        try:
            r = redis.from_url(redis_url)
            follower_count = r.get(redis_key)
            if follower_count:
                response.headers[redis_header_key] = "HIT"
                return followers_obj(int(follower_count), VERSION_CODE)

        except Exception as e:
            print(f"Redis error (Get): {e}")

    headers = {
        "User-Agent": useragent_string
    }

    try:
        resp = requests.get(instagram_url, headers=headers, params={"username": username})
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
                response.headers[redis_header_key] = "MISS"
                # make cache expire 5 seconds less than the minimum refresh interval, so each javascript update will get the latest.
                # otherwise it might still get the cached version, so need to wait 2 refreshes for an update!
                r.set(redis_key, followers, ex=(minimum_refresh_interval * 60) - 5)
            except Exception as e:
                print(f"Redis error (Set): {e}")

        return followers_obj(followers, VERSION_CODE)

    except Exception as e:
        return {"error": str(e)}
