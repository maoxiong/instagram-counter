from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

import os
import requests

app = FastAPI(title="Instagram Follower Counter")
templates = Jinja2Templates(directory="app/templates")

load_dotenv()

app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    interval = max(5, int(os.getenv("REFRESH_INTERVAL", 10)))

    padding = os.getenv("PADDING", "00000")
    transform = f"arrive(.2) -&gt; round -&gt; pad('{ padding }') -&gt; split -&gt; delay(rtl, 100, 150)" if os.getenv("SKIP_ANIMATION", "0") == "0" else f"pad('{ padding }')"

    start_value = followers().get("followers", 0)
    # if the start value is divisible by 10, subtract 10 from it so that there will be a change on boot up
    if start_value > 0 and start_value % 10 == 0:
        start_value -= 10
    # round down to the nearest 10 (giving us a nice animation run-up)
    start_value = (start_value // 10) * 10

    return templates.TemplateResponse(
        "home.html",
        {
            "request": request,  # required
            "instagram_username": os.getenv("INSTAGRAM_USERNAME", "softcatmemes"),
            "refresh_interval": interval * 60000,
            "start_value": start_value,
            "transform": transform,
            "font_size": os.getenv("FONT_SIZE", "4"),
            "font_family": os.getenv("FONT_FAMILY", ""),
            "page_bg": os.getenv("PAGE_BG", "#000000"),
            "flip_bg": os.getenv("FLIP_BG", "#333232"),
            "flip_fg": os.getenv("FLIP_FG", "#edebeb"),
            "ig_logo": os.getenv("IG_LOGO", "1"),
        }
    )

@app.get("/api/followers")
def followers():
    url = "https://i.instagram.com/api/v1/users/web_profile_info/"

    headers = {
        "User-Agent": "Instagram 76.0.0.15.395 Android (24/7.0; 640dpi; 1440x2560; samsung; SM-G930F; herolte; samsungexynos8890; en_US; 138226743)"
    }

    try:
        resp = requests.get(url, headers=headers, params={"username": os.getenv("INSTAGRAM_USERNAME", "softcatmemes")})
        resp.raise_for_status()         # raises error on 4xx/5xx

        json_data = resp.json()

        followers = (
            json_data.get("data", {})
            .get("user", {})
            .get("edge_followed_by", {})
            .get("count", 0)
        )

        return {"followers": followers}

    except Exception as e:
        return {"error": str(e)}
