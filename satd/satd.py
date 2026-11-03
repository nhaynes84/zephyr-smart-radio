#!/usr/bin/env python3
"""satd -- the voice satellite's local service.

Serves the round UI (../ui) on :8080 and fronts everything it talks to, so the
page only ever calls same-origin /api/*:

  /api/spotify/*   login tokens for the Web Playback SDK (the page is the Connect
                   device) + a whitelisted Spotify Web API proxy
  /api/radio/*     mpv over its JSON IPC socket + the radio-browser.info directory
  /api/weather     Open-Meteo (no key); location from config, else IP geolocation
  /api/timers      kitchen timers, alarm tone through mpv when one runs out
  /api/ha/*        Home Assistant REST, once ha_url + ha_token are in the config
  /api/backlight   the Waveshare panel MCU (ws-panel-on)
  /api/knob/*      the EC11 radio dial: decoded turns/presses as an SSE stream
  /api/volume      master volume (ALSA softvol "Master" in front of the dmix)
  /api/audio/state what is playing (from the page) -> the satellite's wake word

and, on the LAN (:8081, bearer token), the remote Home Assistant drives the
speaker with as a media player: ha/custom_components/satellite_speaker.

Spotify and radio share one speaker: starting one stops the other.

Config: /etc/satd.json (see satd.example.json). Everything is optional.
"""
import asyncio
import difflib
import hmac
import json
import math
import os
import re
import struct
import subprocess
import time
import uuid
import wave
from pathlib import Path

from aiohttp import ClientSession, ClientTimeout, WSMsgType, web

from books import Books

UI_DIR = Path(os.environ.get("SATD_UI", Path(__file__).resolve().parent.parent / "ui"))
CONFIG_PATH = Path(os.environ.get("SATD_CONFIG", "/etc/satd.json"))
STATE_DIR = Path(os.environ.get("SATD_STATE", "/var/lib/satd"))
MPV_SOCK = "/run/satd/mpv.sock"
BOOKS_SOCK = "/run/satd/mpv-books.sock"      # audiobooks get their own mpv
RADIO_BROWSER = "https://de1.api.radio-browser.info"
UA = "satd/0.1 (voice satellite)"

DEFAULT_CONFIG = {
    "units": "imperial",          # imperial | metric
    "latitude": None,             # null -> IP geolocation, cached in state
    "longitude": None,
    "place": None,
    "spotify_client_id": None,    # from developer.spotify.com (PKCE, no secret)
    "spotify_device_name": "Zephyr",
    "spotify_volume": 1.0,     # the master does the turning down
    "ha_url": "http://192.168.86.56:8123",
    "ha_token": None,
    "radio_presets": [
        {"name": "KEXP 90.3 Seattle", "url": "https://kexp.streamguys1.com/kexp160.aac"},
        {"name": "WFMU", "url": "https://stream0.wfmu.org/freeform-128k"},
        {"name": "SomaFM Groove Salad", "url": "https://ice2.somafm.com/groovesalad-128-mp3"},
        {"name": "SomaFM Secret Agent", "url": "https://ice2.somafm.com/secretagent-128-mp3"},
        {"name": "Radio Paradise", "url": "https://stream.radioparadise.com/aac-128"},
        {"name": "BBC World Service", "url": "https://stream.live.vc.bbcmedia.co.uk/bbc_world_service"},
    ],
    "radio_genres": ["jazz", "classical", "lofi", "oldies", "news", "rock", "ambient", "country"],
    "assist_satellite": "assist_satellite.satellite_voice_assist_satellite",   # knob hold = talk
    "wake_word_select": "select.satellite_voice_wake_word",   # set to none while audio plays
}


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    try:
        cfg.update(json.loads(CONFIG_PATH.read_text()))
    except FileNotFoundError:
        pass
    return cfg


# --------------------------------------------------------------------- helpers

def http(app):
    return app["http"]


async def get_json(app, url, **kw):
    async with http(app).get(url, **kw) as r:
        if r.status == 204:
            return None
        r.raise_for_status()
        return await r.json(content_type=None)


def ok(data=None, status=200):
    return web.json_response(data if data is not None else {"ok": True}, status=status)


# --------------------------------------------------------------------- spotify
#
# Spotify plays through the official Web Playback SDK inside the kiosk page, so
# the page itself is the "Satellite" Connect device. satd only holds the login:
# a PKCE refresh token (no client secret) in STATE_DIR/spotify.json, mode 600,
# and hands the page short-lived access tokens. Web API calls the page needs
# (browse, start playback on this device) go through a whitelisted proxy.

SP_ACCOUNTS = "https://accounts.spotify.com/api/token"
SP_API = "https://api.spotify.com/v1"
SP_STORE = STATE_DIR / "spotify.json"
SP_WEB_ALLOWED = ("me", "me/player", "me/player/", "me/top/", "me/tracks", "me/albums",
                  "me/playlists", "me/player/recently-played", "search", "albums/", "playlists/")


def sp_load():
    try:
        return json.loads(SP_STORE.read_text())
    except Exception:
        return {}


def sp_save(data):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = SP_STORE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data))
    os.chmod(tmp, 0o600)
    tmp.replace(SP_STORE)


async def sp_token_request(app, form):
    async with http(app).post(SP_ACCOUNTS, data=form) as r:
        body = await r.json(content_type=None)
        if r.status != 200:
            raise RuntimeError(body.get("error_description") or body.get("error") or str(r.status))
        return body


async def sp_access_token(app):
    """A valid access token, refreshed when within a minute of expiry; None if not logged in."""
    async with app["sp_lock"]:
        store = sp_load()
        cid = app["config"].get("spotify_client_id")
        if not cid or not store.get("refresh_token"):
            return None
        if store.get("access_token") and store.get("expires_at", 0) - time.time() > 60:
            return store["access_token"]
        body = await sp_token_request(app, {
            "grant_type": "refresh_token", "refresh_token": store["refresh_token"], "client_id": cid})
        store["access_token"] = body["access_token"]
        store["expires_at"] = time.time() + body.get("expires_in", 3600)
        if body.get("refresh_token"):             # Spotify rotates them for PKCE clients
            store["refresh_token"] = body["refresh_token"]
        sp_save(store)
        return store["access_token"]


async def sp_token(request):
    if not request.app["config"].get("spotify_client_id"):
        return ok({"configured": False})
    try:
        tok = await sp_access_token(request.app)
    except Exception as e:
        return ok({"configured": True, "error": f"token refresh failed: {e}"}, 502)
    if not tok:
        return ok({"configured": True, "logged_in": False})
    return ok({"configured": True, "logged_in": True, "access_token": tok,
               "expires_at": sp_load().get("expires_at")})


async def sp_exchange(request):
    """One-time login: the PKCE code from the redirect URL + its verifier."""
    data = await request.json()
    cid = request.app["config"].get("spotify_client_id")
    if not cid:
        return ok({"error": "spotify_client_id missing from /etc/satd.json"}, 400)
    try:
        body = await sp_token_request(request.app, {
            "grant_type": "authorization_code", "code": data["code"],
            "redirect_uri": data["redirect_uri"], "client_id": cid,
            "code_verifier": data["code_verifier"]})
    except Exception as e:
        return ok({"error": str(e)}, 400)
    sp_save({"refresh_token": body["refresh_token"], "access_token": body["access_token"],
             "expires_at": time.time() + body.get("expires_in", 3600), "scope": body.get("scope")})
    return ok({"logged_in": True, "scope": body.get("scope")})


async def sp_web(request):
    path = request.match_info["path"]
    if not any(path == p or (p.endswith("/") and path.startswith(p)) for p in SP_WEB_ALLOWED):
        return ok({"error": "not allowed"}, 404)
    try:
        tok = await sp_access_token(request.app)
    except Exception as e:
        return ok({"error": str(e)}, 502)
    if not tok:
        return ok({"error": "not logged in"}, 401)
    if request.method == "PUT" and path.startswith("me/player/play"):
        await radio_stop(request.app)
    body = await request.read() if request.method in ("PUT", "POST") else None
    async with http(request.app).request(
            request.method, f"{SP_API}/{path}", params=request.query, data=body,
            headers={"Authorization": f"Bearer {tok}",
                     **({"Content-Type": "application/json"} if body else {})}) as r:
        payload = await r.read()
        if r.status == 204 or not payload:
            return web.Response(status=204 if r.status < 300 else r.status)
        return web.Response(status=r.status, body=payload,
                            content_type=r.content_type or "application/json")


async def sp_config(request):
    cfg = request.app["config"]
    return ok({"device_name": cfg["spotify_device_name"], "volume": cfg["spotify_volume"]})


async def spotify_pause(app):
    """Radio is starting: pause Spotify only if it is playing HERE (not on a phone)."""
    try:
        tok = await sp_access_token(app)
        if not tok:
            return
        auth = {"Authorization": f"Bearer {tok}"}
        async with http(app).get(f"{SP_API}/me/player", headers=auth) as r:
            if r.status != 200:
                return
            st = await r.json(content_type=None)
        dev = st.get("device") or {}
        if st.get("is_playing") and dev.get("name") == app["config"]["spotify_device_name"]:
            async with http(app).put(f"{SP_API}/me/player/pause", headers=auth):
                pass
    except Exception:
        pass


# ----------------------------------------------------------------------- radio

class Mpv:
    """One long-lived mpv --idle, driven over its JSON IPC socket."""

    def __init__(self, sock):
        self.sock = sock
        self.proc = None
        self.req = 0
        self.lock = asyncio.Lock()

    async def ensure(self):
        # ⚠️ Locked: a radio start and the page's status poll used to arrive
        # together on a cold start, each spawn an mpv, and the loser kept
        # playing as an orphan nobody could stop (the socket belonged to the
        # other one) -- radio under Spotify with no way to turn it off.
        async with self.lock:
            await self._ensure()

    async def _ensure(self):
        if self.proc and self.proc.returncode is None and os.path.exists(self.sock):
            return
        if self.proc and self.proc.returncode is None:      # alive but lost its socket
            self.proc.kill()
            await self.proc.wait()
        os.makedirs(os.path.dirname(self.sock), exist_ok=True)
        if os.path.exists(self.sock):
            os.unlink(self.sock)
        self.proc = await asyncio.create_subprocess_exec(
            "mpv", "--idle=yes", "--no-video", "--no-terminal", "--volume=100",
            "--cache=yes", "--demuxer-max-bytes=4MiB", f"--input-ipc-server={self.sock}",
            # The dmix runs at 48k; most streams are 44.1k. Resample here (good
            # quality) rather than in ALSA's plug, whose built-in converter is linear.
            "--audio-samplerate=48000",
            stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL)
        for _ in range(50):
            if os.path.exists(self.sock):
                return
            await asyncio.sleep(0.1)
        raise RuntimeError("mpv did not start")

    async def cmd(self, *args):
        await self.ensure()
        self.req += 1
        rid = self.req
        reader, writer = await asyncio.wait_for(asyncio.open_unix_connection(self.sock), 2)
        try:
            writer.write((json.dumps({"command": list(args), "request_id": rid}) + "\n").encode())
            await writer.drain()
            while True:
                line = await asyncio.wait_for(reader.readline(), 2)
                if not line:
                    return None
                msg = json.loads(line)
                if msg.get("request_id") == rid:
                    return msg.get("data") if msg.get("error") == "success" else None
        finally:
            writer.close()

    async def prop(self, name):
        try:
            return await self.cmd("get_property", name)
        except Exception:
            return None


async def radio_stop(app):
    if app["radio"]["station"]:
        app["radio"]["station"] = None
        try:
            await app["mpv"].cmd("stop")
        except Exception:
            pass


async def radio_start(app, station):
    # Station first, so a status poll during the pauses below already reports it.
    app["radio"]["station"] = app["radio"]["last"] = station
    await spotify_pause(app)
    await audible_pause(app)
    await app["mpv"].cmd("loadfile", station["url"], "replace")


async def radio_play(request):
    data = await request.json()
    url = data.get("url")
    if not url:
        return ok({"error": "url required"}, 400)
    await radio_start(request.app, {"name": data.get("name") or url, "url": url,
                                    "favicon": data.get("favicon")})
    return ok()


async def radio_stop_h(request):
    await radio_stop(request.app)
    return ok()


async def radio_status(request):
    app = request.app
    st = app["radio"]["station"]
    if not st:
        return ok({"playing": False})
    mpv = app["mpv"]
    title = await mpv.prop("media-title")
    meta = await mpv.prop("metadata") or {}
    now = meta.get("icy-title") or (title if title and title != st["url"] else None)
    vol = await mpv.prop("volume")
    idle = await mpv.prop("idle-active")
    buffering = await mpv.prop("paused-for-cache")
    return ok({"playing": not idle, "buffering": bool(buffering), "station": st,
               "now": now, "volume": vol})


async def radio_volume(request):
    data = await request.json()
    v = max(0, min(100, float(data.get("volume", 70))))
    await request.app["mpv"].cmd("set_property", "volume", v)
    return ok({"volume": v})


async def radio_presets(request):
    cfg = request.app["config"]
    return ok({"presets": cfg["radio_presets"], "genres": cfg["radio_genres"]})


async def radio_genre(request):
    tag = request.match_info["tag"]
    cache = request.app["radio"]["genre_cache"]
    hit = cache.get(tag)
    if hit and time.time() - hit[0] < 3600:
        return ok({"stations": hit[1]})
    try:
        rows = await get_json(request.app, f"{RADIO_BROWSER}/json/stations/bytag/{tag}", params={
            "order": "clickcount", "reverse": "true", "hidebroken": "true", "limit": "40"})
    except Exception as e:
        return ok({"error": f"directory unreachable: {e}"}, 502)
    seen, out = set(), []
    for s in rows or []:
        name = (s.get("name") or "").strip()
        url = s.get("url_resolved") or s.get("url")
        if not name or not url or name.lower() in seen:
            continue
        seen.add(name.lower())
        out.append({"name": name, "url": url, "favicon": s.get("favicon") or None,
                    "country": s.get("countrycode"), "codec": s.get("codec"),
                    "bitrate": s.get("bitrate")})
        if len(out) >= 20:
            break
    cache[tag] = (time.time(), out)
    return ok({"stations": out})


# --------------------------------------------------------------------- weather

async def location(app):
    cfg = app["config"]
    if cfg.get("latitude") is not None and cfg.get("longitude") is not None:
        return cfg["latitude"], cfg["longitude"], cfg.get("place")
    cached = STATE_DIR / "location.json"
    try:
        loc = json.loads(cached.read_text())
        return loc["lat"], loc["lon"], loc.get("place")
    except Exception:
        pass
    loc = await get_json(app, "http://ip-api.com/json/?fields=status,lat,lon,city,regionName")
    if not loc or loc.get("status") != "success":
        raise RuntimeError("no location: set latitude/longitude in /etc/satd.json")
    place = loc.get("city")
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    cached.write_text(json.dumps({"lat": loc["lat"], "lon": loc["lon"], "place": place}))
    return loc["lat"], loc["lon"], place


async def weather(request):
    app = request.app
    w = app["weather"]
    if w["data"] and time.time() - w["at"] < 600:
        return ok(w["data"])
    try:
        lat, lon, place = await location(app)
        imperial = app["config"]["units"] == "imperial"
        data = await get_json(app, "https://api.open-meteo.com/v1/forecast", params={
            "latitude": lat, "longitude": lon, "timezone": "auto",
            "current": "temperature_2m,apparent_temperature,relative_humidity_2m,"
                       "weather_code,wind_speed_10m,is_day",
            "hourly": "temperature_2m,weather_code,precipitation_probability,is_day,wind_speed_10m",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,"
                     "precipitation_probability_max,precipitation_sum,wind_speed_10m_max,"
                     "uv_index_max,sunrise,sunset",
            "forecast_days": 7,
            "precipitation_unit": "inch" if imperial else "mm",
            "temperature_unit": "fahrenheit" if imperial else "celsius",
            "wind_speed_unit": "mph" if imperial else "kmh",
        })
    except Exception as e:
        if w["data"]:
            return ok(w["data"])
        return ok({"error": str(e)}, 502)
    data["place"] = place
    data["units"] = "F" if app["config"]["units"] == "imperial" else "C"
    w.update(data=data, at=time.time())
    return ok(data)


# ---------------------------------------------------------------------- timers

def make_chime(path):
    """A soft two-note chime, written once as a WAV."""
    rate = 44100
    frames = bytearray()
    for freq, dur in ((880, 0.18), (0, 0.06), (1318.5, 0.32), (0, 0.5)):
        n = int(rate * dur)
        for i in range(n):
            env = math.exp(-4 * i / n) if freq else 0
            s = int(14000 * env * math.sin(2 * math.pi * freq * i / rate))
            frames += struct.pack("<h", s)
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(rate)
        f.writeframes(bytes(frames))


async def timer_loop(app):
    chime = STATE_DIR / "chime.wav"
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if not chime.exists():
        make_chime(chime)
    while True:
        now = time.time()
        for t in app["timers"].values():
            if not t["done"] and now >= t["ends"]:
                t["done"] = True
        ringing = [t for t in app["timers"].values() if t["done"] and not t["dismissed"]]
        if ringing:
            subprocess.Popen(["aplay", "-q", str(chime)],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            await asyncio.sleep(1.6)
        else:
            await asyncio.sleep(0.25)


async def timers_list(request):
    now = time.time()
    out = []
    for t in sorted(request.app["timers"].values(), key=lambda t: t["ends"]):
        if t["dismissed"]:
            continue
        out.append({**t, "remaining": max(0.0, t["ends"] - now)})
    return ok({"timers": out, "now": now})


async def timers_add(request):
    data = await request.json()
    secs = float(data.get("seconds", 0))
    if not 1 <= secs <= 24 * 3600:
        return ok({"error": "seconds out of range"}, 400)
    tid = uuid.uuid4().hex[:8]
    request.app["timers"][tid] = {"id": tid, "label": data.get("label") or "",
                                  "total": secs, "ends": time.time() + secs,
                                  "done": False, "dismissed": False}
    return ok({"id": tid})


async def timers_delete(request):
    t = request.app["timers"].pop(request.match_info["id"], None)
    return ok() if t else ok({"error": "no such timer"}, 404)


# ------------------------------------------------------------- home assistant

def ha_ready(cfg):
    return bool(cfg.get("ha_url") and cfg.get("ha_token"))


HA_AREAS_TPL = (
    "{% set ns = namespace(o=[]) %}{% for a in areas() %}"
    "{% set ns.o = ns.o + [{'area': area_name(a), 'entities': area_entities(a)"
    " | select('match', '(light|scene)\\\\.') | list}] %}{% endfor %}{{ ns.o | tojson }}")


async def ha_rooms(request):
    """Lights and Hue scenes grouped by HA area, for the round screen.

    Switches are left out on purpose: in this house they are LED-indicator,
    remote-access, automation and Sonos toggles, not things you tap from a
    kitchen speaker. Unavailable lights are dropped too.
    """
    app, cfg = request.app, request.app["config"]
    if not ha_ready(cfg):
        return ok({"configured": False})
    auth = {"Authorization": f"Bearer {cfg['ha_token']}"}
    cache = app["ha_areas"]
    try:
        if not cache["data"] or time.time() - cache["at"] > 300:
            async with http(app).post(f"{cfg['ha_url']}/api/template", headers=auth,
                                      json={"template": HA_AREAS_TPL}) as r:
                r.raise_for_status()
                cache.update(data=json.loads(await r.text()), at=time.time())
        states = await get_json(app, f"{cfg['ha_url']}/api/states", headers=auth)
    except Exception as e:
        return ok({"configured": True, "error": f"Home Assistant unreachable: {e}"}, 502)
    by_id = {s["entity_id"]: s for s in states}
    rooms = []
    for a in cache["data"]:
        area = a["area"]
        lights, scenes = [], []
        for eid in a["entities"]:
            s = by_id.get(eid)
            if not s or s["state"] == "unavailable":
                continue
            name = s["attributes"].get("friendly_name") or eid
            if eid.startswith("scene."):
                short = name[len(area):].strip() if name.lower().startswith(area.lower()) else name
                scenes.append({"entity_id": eid, "name": short or name})
            else:
                modes = s["attributes"].get("supported_color_modes") or []
                lights.append({"entity_id": eid, "name": name, "on": s["state"] == "on",
                               "brightness": s["attributes"].get("brightness"),
                               "dimmable": any(m != "onoff" for m in modes)})
        if lights or scenes:
            lights.sort(key=lambda l: l["name"])
            scenes.sort(key=lambda s: (SCENE_ORDER.get(s["name"], 99), s["name"]))
            rooms.append({"area": area, "lights": lights, "scenes": scenes,
                          "on": sum(l["on"] for l in lights)})
    any_on = [eid for eid, s in by_id.items() if eid.startswith("light.") and s["state"] == "on"]
    return ok({"configured": True, "rooms": rooms, "lights_on": len(any_on)})


SCENE_ORDER = {"Bright": 0, "Read": 1, "Concentrate": 2, "Energize": 3, "Relax": 4,
               "Dimmed": 5, "Nightlight": 6}
HA_SERVICES = {("light", "toggle"), ("light", "turn_on"), ("light", "turn_off"), ("scene", "turn_on")}


async def ha_service(request):
    """{domain, service, entity_id (str or list)[, brightness_pct]} -- only the services above."""
    cfg = request.app["config"]
    if not ha_ready(cfg):
        return ok({"error": "Home Assistant not configured"}, 400)
    data = await request.json()
    domain, service, eid = data.get("domain"), data.get("service"), data.get("entity_id")
    if (domain, service) not in HA_SERVICES or not eid:
        return ok({"error": "not allowed"}, 400)
    ids = eid if isinstance(eid, list) else [eid]
    if not all(isinstance(i, str) and i.startswith(domain + ".") for i in ids):
        return ok({"error": "entity/domain mismatch"}, 400)
    payload = {"entity_id": ids}
    if (domain, service) == ("light", "turn_on") and data.get("brightness_pct") is not None:
        payload["brightness_pct"] = max(1, min(100, int(data["brightness_pct"])))
    async with http(request.app).post(
            f"{cfg['ha_url']}/api/services/{domain}/{service}",
            headers={"Authorization": f"Bearer {cfg['ha_token']}"},
            json=payload) as r:
        return ok({"status": r.status}, 200 if r.status < 400 else 502)


# --------------------------------------------------------------------- audible
#
# "Audible" here is his audiobook library: Audiobookshelf on talos (books.py),
# DRM-free copies of his Audible purchases. The old web-player driver
# (audible.py) is retired; the routes keep their names so nothing else moved.


async def audible_library(request):
    try:
        books = await request.app["audible"].get_library(refresh="refresh" in request.query)
    except PermissionError:
        return ok({"signed_in": False, "books": []})
    except Exception as e:
        return ok({"error": str(e)}, 502)
    return ok({"signed_in": True, "books": books})


async def audible_play(request):
    asin = (await request.json()).get("asin", "")
    await radio_stop(request.app)
    await spotify_pause(request.app)
    try:
        await request.app["audible"].play(asin)
    except Exception as e:
        return ok({"error": str(e)}, 502)
    return ok()


async def audible_status(request):
    return ok(await request.app["audible"].status())


async def audible_cmd(request):
    data = await request.json()
    try:
        await request.app["audible"].cmd(data.get("action"), data.get("value"))
    except Exception as e:
        return ok({"error": str(e)}, 400)
    return ok()


async def audible_pause(app):
    """Another source is starting: pause Audible if it is playing."""
    aud = app["audible"]
    try:
        if aud.now:
            await aud.cmd("pause")
    except Exception:
        pass


# -------------------------------------------------------------------- calendar
#
# Events come from Home Assistant's calendar entities (his Google calendar via
# HA's remote_calendar/ICS), so the round screen and the Claude satellite read
# the same source. ⚠️ remote_calendar only re-downloads its ICS once a DAY, so
# every CAL_REFRESH_S we ask HA to refresh them (update_entity) before reading.
# ⚠️ His own feed only carries Family events he's invited to: the Family
# calendar is its own HA calendar ("Family"), added 2026-10-20.

CAL_REFRESH_S = 300


async def calendar(request):
    app, cfg = request.app, request.app["config"]
    if not ha_ready(cfg):
        return ok({"configured": False})
    cache = app["calendar"]
    if cache["data"] and time.time() - cache["at"] < 120:
        return ok(cache["data"])
    auth = {"Authorization": f"Bearer {cfg['ha_token']}"}
    try:
        cals = await get_json(app, f"{cfg['ha_url']}/api/calendars", headers=auth)
    except Exception:
        return ok({"configured": False})
    if cals and time.time() - cache.get("refreshed", 0) > CAL_REFRESH_S:
        cache["refreshed"] = time.time()
        try:
            async with http(app).post(f"{cfg['ha_url']}/api/services/homeassistant/update_entity",
                                        headers=auth, timeout=ClientTimeout(total=30),
                                        json={"entity_id": [c["entity_id"] for c in cals]}) as r:
                await r.read()
        except Exception as e:
            print(f"calendar refresh: {e}", flush=True)       # stale beats nothing
    start = time.strftime("%Y-%m-%dT00:00:00", time.localtime())
    end = time.strftime("%Y-%m-%dT00:00:00", time.localtime(time.time() + 8 * 86400))
    events = []
    for c in cals or []:
        try:
            rows = await get_json(app, f"{cfg['ha_url']}/api/calendars/{c['entity_id']}",
                                  headers=auth, params={"start": start, "end": end})
        except Exception:
            continue
        for e in rows or []:
            s, en = e.get("start", {}), e.get("end", {})
            events.append({"summary": e.get("summary") or "(busy)", "location": e.get("location"),
                           "calendar": c.get("name"),
                           "start": s.get("dateTime") or s.get("date"),
                           "end": en.get("dateTime") or en.get("date"),
                           "all_day": "date" in s and "dateTime" not in s})
    events.sort(key=lambda e: e["start"] or "")
    seen, uniq = set(), []                  # Family events he's invited to are on his too
    for e in events:
        key = (e["start"], " ".join(e["summary"].split()).casefold())
        if key not in seen:
            seen.add(key)
            uniq.append(e)
    data = {"configured": bool(cals), "events": uniq}
    cache.update(data=data, at=time.time())
    return ok(data)


# ------------------------------------------------------------------- bluetooth
#
# Bluetooth speaker mode (Audible, or anything else on his phone): bluez-alsa's
# a2dp-sink + bluealsa-aplay play into the same dmix as Spotify and radio. satd
# reads BlueZ over D-Bus with `busctl` (no extra Python deps): paired devices,
# and the phone's AVRCP player for title/artist/play-pause.
#
# ⚠️ Pairing is only open while he asks for it on the screen: discoverable +
# a NoInputNoOutput bt-agent for PAIR_WINDOW seconds, then both close. Paired
# devices are marked Trusted so they reconnect without the agent.

PAIR_WINDOW = 180


def _unvariant(v):
    if isinstance(v, dict) and set(v) == {"type", "data"}:
        return _unvariant(v["data"])
    if isinstance(v, dict):
        return {k: _unvariant(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_unvariant(x) for x in v]
    return v


async def _run(*args, timeout=8):
    proc = await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout)
    except asyncio.TimeoutError:
        proc.kill()
        raise RuntimeError(f"{args[0]} timed out")
    if proc.returncode:
        raise RuntimeError(err.decode().strip() or f"{args[0]} failed")
    return out.decode()


async def bt_objects():
    raw = await _run("busctl", "--system", "--json=short", "call", "org.bluez", "/",
                     "org.freedesktop.DBus.ObjectManager", "GetManagedObjects")
    return _unvariant(json.loads(raw)["data"][0])


async def bt_set(path, iface, prop, sig, value):
    await _run("busctl", "--system", "set-property", "org.bluez", path, iface, prop, sig, value)


async def bt_status(request):
    app = request.app
    try:
        objs = await bt_objects()
    except Exception as e:
        return ok({"error": f"bluetooth unavailable: {e}"}, 503)
    adapter = objs.get("/org/bluez/hci0", {}).get("org.bluez.Adapter1", {})
    devices, player = [], None
    for path, ifaces in sorted(objs.items()):
        dev = ifaces.get("org.bluez.Device1")
        if dev and dev.get("Paired"):
            if not dev.get("Trusted"):          # reconnect later without the agent
                try:
                    await bt_set(path, "org.bluez.Device1", "Trusted", "b", "true")
                except Exception:
                    pass
            devices.append({"path": path, "name": dev.get("Alias") or dev.get("Name") or path[-17:],
                            "connected": bool(dev.get("Connected"))})
        mp = ifaces.get("org.bluez.MediaPlayer1")
        if mp:
            owner = objs.get(mp.get("Device", ""), {}).get("org.bluez.Device1", {})
            if owner.get("Connected"):
                track = mp.get("Track") or {}
                player = {"path": path, "status": mp.get("Status"), "position": mp.get("Position"),
                          "title": track.get("Title"), "artist": track.get("Artist"),
                          "album": track.get("Album"), "duration": track.get("Duration"),
                          "app": mp.get("Name"), "device": owner.get("Alias")}
    pairing = max(0, app["bt"]["pair_until"] - time.time())
    return ok({"alias": adapter.get("Alias"), "discoverable": bool(adapter.get("Discoverable")),
               "pairing_left": round(pairing), "devices": devices, "player": player})


async def bt_pair(request):
    app = request.app
    bt = app["bt"]
    await _run("bluetoothctl", "pairable", "on")
    await _run("bluetoothctl", "discoverable", "on")
    if not bt["agent"] or bt["agent"].returncode is not None:
        bt["agent"] = await asyncio.create_subprocess_exec(
            "bt-agent", "-c", "NoInputNoOutput",
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
    bt["pair_until"] = time.time() + PAIR_WINDOW
    if bt["closer"]:
        bt["closer"].cancel()
    bt["closer"] = asyncio.create_task(_close_pairing(app, PAIR_WINDOW))
    return ok({"pairing_left": PAIR_WINDOW})


async def _close_pairing(app, delay):
    await asyncio.sleep(delay)
    bt = app["bt"]
    for cmd in (("discoverable", "off"), ("pairable", "off")):
        try:
            await _run("bluetoothctl", *cmd)
        except Exception:
            pass
    if bt["agent"] and bt["agent"].returncode is None:
        bt["agent"].terminate()
    bt["pair_until"] = 0


async def bt_cmd(request):
    data = await request.json()
    action = data.get("action")
    path = data.get("path", "")
    if not path.startswith("/org/bluez/hci0/"):
        return ok({"error": "bad path"}, 400)
    if action in ("Play", "Pause", "Next", "Previous", "Stop"):
        await _run("busctl", "--system", "call", "org.bluez", path, "org.bluez.MediaPlayer1", action)
    elif action == "Disconnect":
        await _run("busctl", "--system", "call", "org.bluez", path, "org.bluez.Device1", "Disconnect")
    elif action == "Connect":
        await _run("busctl", "--system", "call", "org.bluez", path, "org.bluez.Device1", "Connect",
                   timeout=20)
    elif action == "Forget":
        await _run("busctl", "--system", "call", "org.bluez", "/org/bluez/hci0", "org.bluez.Adapter1",
                   "RemoveDevice", "o", path)
    else:
        return ok({"error": "unknown action"}, 400)
    return ok()


# ------------------------------------------------------------------- backlight

async def backlight(request):
    level = int((await request.json()).get("level", 255))
    level = max(0, min(255, level))
    proc = await asyncio.create_subprocess_exec(
        "/usr/local/sbin/ws-panel-on", str(level),
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
    await asyncio.wait_for(proc.wait(), 5)
    return ok({"level": level})


# ------------------------------------------------------------------------ knob
#
# The EC11 radio dial (dt/knob-ec11.dts): A, B and the press are three
# gpio-keys lines on one evdev device. satd GRABS it (so cage never sees stray
# BTN_ keys), decodes the quadrature and the press gestures, and streams them
# to the page over SSE. The page decides what a turn or a click means for the
# screen it is showing.

KNOB_NAME = "knob"
KNOB_CW = -1              # A leading B is counter-clockwise on this wiring
KNOB_CLICK_GAP = 0.35     # a second click inside this is a double
KNOB_HOLD_S = 0.6
QUAD = {0b00: 0, 0b10: 1, 0b11: 2, 0b01: 3}   # (A, B) in A-leading order


class Knob:
    def __init__(self):
        self.subs = set()
        self.a = self.b = 0
        self.pos = 0              # last (A, B) state
        self.acc = 0              # quarter-steps since the last detent
        self.down = False
        self.held = False
        self.hold_timer = None
        self.pending = None       # single click waiting to see if a second follows

    def emit(self, ev):
        for q in list(self.subs):
            try:
                q.put_nowait(ev)
            except asyncio.QueueFull:
                pass

    def quad(self):
        new = (self.a << 1) | self.b
        step = (QUAD[new] - QUAD[self.pos]) % 4
        self.pos = new
        if step == 1:
            self.acc += 1
        elif step == 3:
            self.acc -= 1
        if new == 0:                      # every detent rests with both contacts open
            if abs(self.acc) >= 3:
                self.emit({"t": "turn", "d": KNOB_CW * (1 if self.acc > 0 else -1)})
            self.acc = 0

    def press(self, down):
        loop = asyncio.get_running_loop()
        if down and not self.down:
            self.down, self.held = True, False
            self.hold_timer = loop.call_later(KNOB_HOLD_S, self._hold)
        elif not down and self.down:
            self.down = False
            if self.hold_timer:
                self.hold_timer.cancel()
            if self.held:
                return
            if self.pending:
                self.pending.cancel()
                self.pending = None
                self.emit({"t": "double"})
            else:
                self.pending = loop.call_later(KNOB_CLICK_GAP, self._click)

    def _hold(self):
        self.held = True
        if self.pending:
            self.pending.cancel()
            self.pending = None
        self.emit({"t": "hold"})

    def _click(self):
        self.pending = None
        self.emit({"t": "click"})

    async def run(self):
        from evdev import InputDevice, ecodes, list_devices
        while True:
            dev = None
            for path in list_devices():
                d = InputDevice(path)
                if d.name == KNOB_NAME:
                    dev = d
                    break
                d.close()
            if not dev:
                await asyncio.sleep(30)           # overlay not loaded (yet)
                continue
            try:
                dev.grab()
                async for e in dev.async_read_loop():
                    if e.type != ecodes.EV_KEY:
                        continue
                    if e.code == ecodes.BTN_0:
                        self.a = 1 if e.value else 0
                        self.quad()
                    elif e.code == ecodes.BTN_1:
                        self.b = 1 if e.value else 0
                        self.quad()
                    elif e.code == ecodes.BTN_2:
                        self.press(bool(e.value))
            except OSError as err:
                print(f"knob: {err}", flush=True)
            finally:
                dev.close()
            await asyncio.sleep(5)


async def knob_stream(request):
    knob = request.app["knob"]
    resp = web.StreamResponse(headers={"Content-Type": "text/event-stream",
                                       "Cache-Control": "no-cache"})
    await resp.prepare(request)
    q = asyncio.Queue(maxsize=64)
    knob.subs.add(q)
    try:
        while True:
            try:
                ev = await asyncio.wait_for(q.get(), 20)
            except asyncio.TimeoutError:
                await resp.write(b": ping\n\n")
                continue
            if ev is None:                # satd is shutting down
                break
            await resp.write(f"data: {json.dumps(ev)}\n\n".encode())
    except ConnectionResetError:
        pass                              # page went away; CancelledError must propagate (shutdown)
    finally:
        knob.subs.discard(q)
    return resp


async def knob_emit(request):
    """Test hook (satd is loopback-only): inject {t, d} as if the dial sent it."""
    ev = await request.json()
    if ev.get("t") not in ("turn", "click", "double", "hold"):
        return ok({"error": "bad event"}, 400)
    request.app["knob"].emit({"t": ev["t"], "d": int(ev.get("d", 1))} if ev["t"] == "turn" else {"t": ev["t"]})
    return ok()


async def knob_talk(request):
    """Hold the dial: the voice satellite says "Yes?" and listens, as if woken.

    ⚠️ start_message must not be empty: with "" the XVF3800 board sits in
    "responding" forever, playing an announcement that never ends, until its
    ESPHome entry is reloaded in HA.
    """
    cfg = request.app["config"]
    if not ha_ready(cfg) or not cfg.get("assist_satellite"):
        return ok({"error": "Home Assistant not configured"}, 400)
    async with http(request.app).post(
            f"{cfg['ha_url']}/api/services/assist_satellite/start_conversation",
            headers={"Authorization": f"Bearer {cfg['ha_token']}"},
            json={"entity_id": cfg["assist_satellite"], "start_message": "Yes?",
                  "preannounce": False}) as r:
        return ok({"status": r.status}, 200 if r.status < 400 else 502)


# ---------------------------------------------------------------------- volume
#
# One master volume for everything on the speaker: asound.conf puts a softvol
# ("Master") in front of the EQ and the dmix. The control only exists once
# something has opened that PCM, so startup plays a blip of silence first, then
# restores the saved level.
#
# Ducking: while the voice satellite is listening, thinking or talking, the
# music drops to DUCK_FRAC of where he left it, and comes back a moment after
# it goes idle. "base" is always HIS level; the knob moves base, ducked or not.
# The satellite's state arrives over HA's websocket (a state trigger), so the
# dip lands as the wake word does, not on a poll.

VOL_CARD = "max98357a"
VOL_STORE = STATE_DIR / "volume.json"
DUCK_STATES = ("listening", "processing", "responding")
DUCK_FRAC = 0.45          # of the mapped (perceptual) volume, roughly -15 dB
DUCK_HOLD_S = 1.0         # after idle, before the music comes back
DUCK_MAX_S = 90           # a satellite stuck mid-reply never keeps the music down

# Tone for the PC83 in its small sealed box (alsaequal/CAPS Eq10: 0..100,
# 66 = flat, ~0.72 dB a step). Below ~100 Hz it can't play, so don't spend
# excursion there; 125-250 Hz, where the box rolls off, sit ~4 dB above the
# rest; 2-4 kHz eased. CUTS ONLY -- nothing above 66: the EQ runs before the
# master volume (see asound.conf), so a boost would clip on loud masters.
EQ_FILE = STATE_DIR / "alsaequal.bin"
EQ_PC83 = [46, 56, 66, 63, 60, 60, 58, 57, 60, 61]   # 31 Hz .. 16 kHz


async def volume_apply(app):
    v = app["vol"]
    if v["base"] is None:
        return
    pct = round(v["base"] * DUCK_FRAC) if v["ducked"] else v["base"]
    await _run("amixer", "-q", "-M", "-c", VOL_CARD, "sset", "Master", f"{pct}%")


async def volume_set(app, pct):
    app["vol"]["base"] = max(0, min(100, int(round(pct))))
    VOL_STORE.write_text(json.dumps({"volume": app["vol"]["base"]}))
    await volume_apply(app)
    app["knob"].emit({"t": "vol", "v": app["vol"]["base"]})    # the screen follows HA too
    return app["vol"]["base"]


async def volume_init(app):
    silence = STATE_DIR / "silence.wav"
    if not silence.exists():
        with wave.open(str(silence), "wb") as f:
            f.setnchannels(2)
            f.setsampwidth(2)
            f.setframerate(48000)
            f.writeframes(b"\0" * 4 * 4800)
    fresh_eq = not EQ_FILE.exists()
    try:
        saved = json.loads(VOL_STORE.read_text())["volume"]
    except Exception:
        saved = 60
    err = None
    for _ in range(10):
        try:
            await _run("aplay", "-q", str(silence))      # creates Master (and the EQ file)
            await volume_set(app, saved)
            break
        except Exception as e:
            err = e
            await asyncio.sleep(3)
    else:
        print(f"volume: no Master control ({err})", flush=True)
    try:
        if fresh_eq:
            for i, val in enumerate(EQ_PC83, 1):
                await _run("amixer", "-q", "-D", "sateq", "cset", f"numid={i}", f"{val},{val}")
            print("eq: PC83 curve applied", flush=True)
        os.chmod(EQ_FILE, 0o666)          # every player maps it, bluealsa as root
    except Exception as e:
        print(f"eq: {e}", flush=True)


async def duck(app, on):
    v = app["vol"]
    if v["undo"]:
        v["undo"].cancel()
        v["undo"] = None
    if on:
        if not v["ducked"]:
            v["ducked"] = True
            await volume_apply(app)

        # Armed whenever none is running, not only on the first dip: idle ->
        # listening inside DUCK_HOLD_S cancels later() with ducked still True,
        # and the failsafe was already cancelled by that idle (issue #1).
        async def failsafe():
            await asyncio.sleep(DUCK_MAX_S)
            v["failsafe"] = None
            if v["ducked"]:
                print("duck: satellite never went idle, music back up", flush=True)
                await duck(app, False)
        if not v.get("failsafe"):
            v["failsafe"] = asyncio.create_task(failsafe())
    elif not on and v["ducked"]:
        if v.get("failsafe"):
            v["failsafe"].cancel()
            v["failsafe"] = None
        async def later():
            await asyncio.sleep(DUCK_HOLD_S)
            v["ducked"], v["undo"] = False, None
            await volume_apply(app)
        v["undo"] = asyncio.create_task(later())


async def duck_loop(app):
    session = ClientSession(timeout=ClientTimeout(total=None, sock_connect=10))
    try:
        while True:
            cfg = app["config"]
            ent = cfg.get("assist_satellite")
            if not ent or not ha_ready(cfg):
                await asyncio.sleep(60)
                continue
            try:
                async with session.ws_connect(cfg["ha_url"].replace("http", "ws", 1) + "/api/websocket",
                                              heartbeat=30) as ws:
                    await ws.receive_json()                                   # auth_required
                    await ws.send_json({"type": "auth", "access_token": cfg["ha_token"]})
                    if (await ws.receive_json()).get("type") != "auth_ok":
                        raise RuntimeError("HA websocket auth failed")
                    await ws.send_json({"id": 1, "type": "subscribe_trigger",
                                        "trigger": {"platform": "state", "entity_id": ent}})
                    async for msg in ws:
                        if msg.type != WSMsgType.TEXT:
                            break
                        d = json.loads(msg.data)
                        if d.get("type") == "event":
                            trig = (d["event"].get("variables") or {}).get("trigger") or {}
                            await duck(app, (trig.get("to_state") or {}).get("state") in DUCK_STATES)
            except Exception as e:
                print(f"duck: {e}", flush=True)
            await duck(app, False)          # never leave the music down
            await asyncio.sleep(10)
    finally:
        await session.close()


async def volume(request):
    app = request.app
    try:
        if request.method == "POST":
            data = await request.json()
            if "set" in data:
                return ok({"volume": await volume_set(app, float(data["set"]))})
            return ok({"volume": await volume_set(app, (app["vol"]["base"] or 0) + float(data.get("delta", 0)))})
        return ok({"volume": app["vol"]["base"], "ducked": app["vol"]["ducked"]})
    except Exception as e:
        return ok({"error": str(e)}, 503)


# ------------------------------------------------------------------- wake word
#
# Music and audiobooks from the Pi are NOT in the reSpeaker's echo-cancellation
# reference (that is only its own speaker), so to its mics a song is a person
# talking, and lyrics wake it. While anything plays here the satellite's wake
# word is set to none; holding the knob still talks (start_conversation skips
# the wake word). It comes back once playback has been quiet for
# WAKE_RESTORE_S. The page reports what is playing every couple of seconds (it
# sees every source, however it was started); if the reports stop, the wake
# word comes back rather than staying off.
#
# Only a wake word satd itself turned off is ever restored, so a change made
# in HA by hand is left alone. That fact is kept on disk across restarts.

WAKE_OFF = "no_wake_word"
WAKE_RESTORE_S = 6
WAKE_STALE_S = 30
WAKE_AUDIBLE_S = 3        # how often a loaded book is asked whether it plays
WAKE_STORE = STATE_DIR / "wake.json"


async def ha_state(app, entity_id):
    cfg = app["config"]
    return await get_json(app, f"{cfg['ha_url']}/api/states/{entity_id}",
                          headers={"Authorization": f"Bearer {cfg['ha_token']}"})


async def ha_select(app, entity_id, option):
    cfg = app["config"]
    async with http(app).post(f"{cfg['ha_url']}/api/services/select/select_option",
                              headers={"Authorization": f"Bearer {cfg['ha_token']}"},
                              json={"entity_id": entity_id, "option": option}) as r:
        r.raise_for_status()


async def wake_loop(app):
    a = app["audio"]
    try:
        held = json.loads(WAKE_STORE.read_text()).get("restore")   # what we turned off
    except Exception:
        held = None
    try:
        await app["audible"].adopt()           # a book playing through a restart counts
    except Exception:
        pass
    while True:
        await asyncio.sleep(1)
        cfg = app["config"]
        sel = cfg.get("wake_word_select")
        if not sel or not ha_ready(cfg):
            continue
        now = time.time()
        live = now - a["at"] < WAKE_STALE_S
        # Audible is asked here, not taken from the page: the page only polls it
        # while its screen is open, so a book started by voice or from HA never
        # turned the wake word off, and the book woke it.
        aud = app.get("audible")
        if aud is not None and aud.now and now - a.get("aud_at", 0) >= WAKE_AUDIBLE_S:
            try:
                st = await aud.status()
                a["aud_playing"] = bool(st.get("active") and not st.get("paused"))
            except Exception:
                a["aud_playing"] = False
            a["aud_at"] = now
        elif aud is None or not aud.now:
            a["aud_playing"] = False
        playing = (a["playing"] and live) or a.get("aud_playing", False)
        if playing:
            a["quiet_since"] = None
        elif a["quiet_since"] is None:
            a["quiet_since"] = now
        want_off = playing
        try:
            if want_off and held is None:
                cur = (await ha_state(app, sel) or {}).get("state")
                if cur and cur not in (WAKE_OFF, "unavailable", "unknown"):
                    await ha_select(app, sel, WAKE_OFF)
                    held = cur
                    WAKE_STORE.write_text(json.dumps({"restore": held}))
                    src = a["source"] if a["playing"] and live else "audible"
                    print(f"wake word off while {src or 'audio'} plays", flush=True)
            elif not want_off and held is not None and now - (a["quiet_since"] or now) >= WAKE_RESTORE_S:
                if (await ha_state(app, sel) or {}).get("state") == WAKE_OFF:
                    await ha_select(app, sel, held)
                    print(f"wake word back: {held}", flush=True)
                held = None
                WAKE_STORE.unlink(missing_ok=True)
        except Exception as e:
            print(f"wake word: {e}", flush=True)
            await asyncio.sleep(10)


async def audio_state(request):
    data = await request.json()
    a = request.app["audio"]
    a.update(playing=bool(data.get("playing")), source=data.get("source"), at=time.time())
    return ok()


# ---------------------------------------------------------------------- remote
#
# Home Assistant drives the speaker as a media player (custom integration
# satellite_speaker): what's playing, "play <query> [on spotify/the radio/
# audible]", pause/resume/stop/skip, volume. That puts the speaker in front of
# the Claude satellite as ordinary HA media tools, so "play Bob Dylan on the
# radio" works however he asks.
#
# It is the only thing here listening beyond loopback, so it is a separate
# little app on its own port: a bearer token ("remote_token" in
# /etc/satd.json; no token, no listener) and only these routes, never the
# page's API. Playback goes through the same functions the screen uses, so the
# page simply sees it on its next poll.

REMOTE_PORT = 8081


def _norm(text):
    return re.sub(r"[^a-z0-9 ]+", "", (text or "").lower()).strip()


def _ratio(a, b):
    return difflib.SequenceMatcher(None, _norm(a), _norm(b)).ratio()


def _like(name, q):
    """How well q names name: 1.0 if all its words are in it ("dune" -> "Dune:
    Book One"), else fuzzy, for mishearings."""
    a, b = _norm(name).split(), _norm(q).split()
    if not a or not b:
        return 0.0
    if set(b) <= set(a):
        return 1.0
    return _ratio(name, q)


def _strip(q, pattern):
    return re.sub(pattern, " ", q, flags=re.I).strip(" ,.")


async def sp_call(app, method, path, **kw):
    tok = await sp_access_token(app)
    if not tok:
        raise RuntimeError("Spotify isn't signed in")
    async with http(app).request(method, f"{SP_API}/{path}",
                                 headers={"Authorization": f"Bearer {tok}"}, **kw) as r:
        raw = await r.read()
        body = json.loads(raw) if raw else None
        if r.status >= 300:
            raise RuntimeError(((body or {}).get("error") or {}).get("message")
                               or f"Spotify said {r.status}")
        return body


async def sp_here(app):
    """Spotify's player state, if it is playing (or paused) on THIS speaker."""
    st = await sp_call(app, "GET", "me/player")
    dev = (st or {}).get("device") or {}
    if dev and (dev.get("id") == app["sp_dev"] or dev.get("name") == app["config"]["spotify_device_name"]):
        return st
    return None


async def sp_devices(app):
    return [d["id"] for d in (await sp_call(app, "GET", "me/player/devices") or {}).get("devices") or []]


async def sp_device(app):
    """The page's player id, ready to play to. Spotify quietly drops a web player
    that has sat idle for hours (the page still holds its old id), so if it is
    gone from the device list, have the page reconnect and wait for the new id."""
    if app["sp_dev"] and app["sp_dev"] in await sp_devices(app):
        return app["sp_dev"]
    old = app["sp_dev"]
    app["knob"].emit({"t": "sp-reconnect"})
    for _ in range(24):
        await asyncio.sleep(0.5)
        new = app["sp_dev"]
        if new and new != old and new in await sp_devices(app):
            return new
    if app["sp_dev"] and app["sp_dev"] != old:
        return app["sp_dev"]                 # ready but not listed yet: worth a try
    raise RuntimeError("the speaker's Spotify player isn't up (is the screen running?)")


async def sp_device_report(request):
    """The page's Web Playback SDK device id ({id}, null when it drops)."""
    request.app["sp_dev"] = (await request.json()).get("id")
    return ok()


async def remote_spotify(app, q, kind=None):
    for word in ("playlist", "album", "song", "track"):
        if re.search(rf"\b{word}\b", q, re.I):
            kind = kind or {"song": "track"}.get(word, word)
            q = _strip(q, rf"\b(the )?{word}\b")
    if not q:
        raise LookupError("play what on Spotify?")
    res = await sp_call(app, "GET", "search", params={
        "q": q, "type": "artist,album,playlist,track", "limit": "5"})

    def items(t):
        return [i for i in ((res or {}).get(t + "s") or {}).get("items") or [] if i]

    pick = None
    artists = items("artist")
    if kind in (None, "artist") and artists and (kind or _ratio(artists[0]["name"], q) >= 0.85):
        pick = ("artist", artists[0])
    if not pick and kind in ("album", "playlist") and items(kind):
        pick = (kind, items(kind)[0])
    if not pick and items("track"):
        pick = ("track", items("track")[0])
    if not pick:
        raise LookupError(f"nothing on Spotify for {q}")
    kind, it = pick
    if kind == "track":       # the song, then the rest of its album rather than silence
        body = {"context_uri": it["album"]["uri"], "offset": {"uri": it["uri"]}}
    else:
        body = {"context_uri": it["uri"]}
    dev = await sp_device(app)
    await radio_stop(app)
    await audible_pause(app)
    await sp_call(app, "PUT", "me/player/play", params={"device_id": dev}, json=body)
    by = it.get("artists") or (it.get("album") or {}).get("artists") or []
    title = it["name"] + (f" by {by[0]['name']}" if kind in ("track", "album") and by else "")
    return {"source": "spotify", "kind": kind, "title": title}


async def remote_radio(app, q):
    q = _strip(q, r"\b(on )?(the )?radio\b|\bstation\b")
    if not q:
        if not app["radio"]["last"]:
            raise LookupError("which station?")
        st = app["radio"]["last"]
    else:
        presets = app["config"]["radio_presets"]
        best = max(presets, key=lambda x: _like(x["name"], q), default=None)
        if best and _like(best["name"], q) >= 0.75:
            st = best
        else:
            rows = []
            for field in ("name", "tag"):
                rows = await get_json(app, f"{RADIO_BROWSER}/json/stations/search", params={
                    field: q.lower() if field == "tag" else q, "order": "clickcount",
                    "reverse": "true", "hidebroken": "true", "limit": "5"}) or []
                rows = [r for r in rows if r.get("url_resolved") or r.get("url")]
                if rows:
                    break
            # The directory's "working" check is loose: some entries are a short
            # clip, not a stream. Take the first that actually streams.
            for r0 in rows:
                st = {"name": (r0.get("name") or q).strip(),
                      "url": r0.get("url_resolved") or r0["url"], "favicon": r0.get("favicon") or None}
                if await radio_streams(app, st):
                    return {"source": "radio", "title": st["name"]}
            await radio_stop(app)
            raise LookupError(f"no radio station for {q}")
    await radio_start(app, st)
    return {"source": "radio", "title": st["name"]}


async def radio_streams(app, st, wait=8):
    """Start st; True once it plays as a live stream (no duration), else False."""
    await radio_start(app, st)
    mpv = app["mpv"]
    for _ in range(wait * 4):
        await asyncio.sleep(0.25)
        if (await mpv.prop("time-pos") or 0) > 0.5:
            dur = await mpv.prop("duration")
            return not dur or dur > 600
        if await mpv.prop("idle-active"):
            return False
    return False


async def remote_audible(app, q):
    q = _strip(q, r"\b(on |from )?audible\b|\b(the |my )?audio ?book\b")
    aud = app["audible"]
    try:
        books = await aud.get_library()
    except PermissionError:
        raise RuntimeError("the audiobook server rejected Zephyr; check abs_token") from None
    if not q:
        if not aud.now:
            raise LookupError("which book?")
        q = aud.now["title"]
    best = max(books, key=lambda b: max(_like(b["title"], q),
                                        _like(f"{b['title']} {b.get('author') or ''}", q)), default=None)
    if not best or max(_like(best["title"], q), _like(f"{best['title']} {best.get('author') or ''}", q)) < 0.6:
        raise LookupError(f"no book like {q} in the library")
    await radio_stop(app)
    await spotify_pause(app)
    await aud.play(best["asin"])
    return {"source": "audible", "title": best["title"]}


async def remote_play(app, source, query, kind=None):
    q = (query or "").strip()
    source = (source or "").lower()
    # Words he said beat the media class the agent guessed ("Bob Dylan on the radio", artist).
    low = q.lower()
    said = ("audible" if re.search(r"\baudible\b|\baudio ?book\b", low)
            else "radio" if re.search(r"\bradio\b|\bstation\b", low)
            else "spotify" if re.search(r"\bspotify\b", low) else None)
    if said or source not in ("spotify", "radio", "audible"):
        source = said or "spotify"
    if source == "audible":
        return await remote_audible(app, q)
    if source == "radio":
        try:
            return await remote_radio(app, q)
        except LookupError:
            # "Bob Dylan on the radio": no such station -> his music, said so
            rest = _strip(q, r"\b(on )?(the )?radio\b|\bstation\b")
            if not rest:
                raise
            out = await remote_spotify(app, rest, kind)
            return {**out, "note": f"no radio station for {rest}, so Spotify"}
    q = _strip(q, r"\b(on |from )?spotify\b")
    if not q:                                   # "Spotify" as a source: carry on where it was
        dev = await sp_device(app)
        await radio_stop(app)
        await audible_pause(app)
        await sp_call(app, "PUT", "me/player/play", params={"device_id": dev})
        return {"source": "spotify", "title": None}
    return await remote_spotify(app, q, kind)


async def remote_status(app):
    out = {"state": "idle", "source": None, "volume": app["vol"]["base"],
           "ducked": app["vol"]["ducked"]}
    st = app["radio"]["station"]
    if st:
        mpv = app["mpv"]
        meta = await mpv.prop("metadata") or {}
        out.update(state="idle" if await mpv.prop("idle-active") else "playing", source="radio",
                   title=meta.get("icy-title") or st["name"], artist=st["name"],
                   image=st.get("favicon"))
        return out
    try:
        aud = await app["audible"].status()
    except Exception:
        aud = {}
    book = dict(state="paused" if aud.get("paused") else "playing", source="audible",
                title=aud.get("title"), artist=aud.get("author"), image=aud.get("cover"),
                position=aud.get("t"), duration=aud.get("dur"))
    # A paused book stays loaded indefinitely: it must not hide Spotify playing
    # (HA would show the book, and "pause" would go to it, not the music).
    if aud.get("active") and not aud.get("paused"):
        out.update(book)
        return out
    try:
        sp = await sp_here(app)
    except Exception:
        sp = None
    if aud.get("active") and not (sp and sp.get("item") and sp.get("is_playing")):
        out.update(book)
        return out
    if sp and sp.get("item"):
        it = sp["item"]
        album = it.get("album") or {}
        out.update(state="playing" if sp.get("is_playing") else "paused", source="spotify",
                   title=it.get("name"), artist=", ".join(a["name"] for a in it.get("artists") or []),
                   album=album.get("name"), image=((album.get("images") or [{}])[0]).get("url"),
                   position=(sp.get("progress_ms") or 0) / 1000,
                   duration=(it.get("duration_ms") or 0) / 1000)
        return out
    a = app["audio"]
    if a["source"] == "phone" and a["playing"] and time.time() - a["at"] < WAKE_STALE_S:
        out.update(state="playing", source="phone", title="Phone audio")
    return out


async def remote_cmd(app, cmd):
    src = (await remote_status(app))["source"]
    if cmd == "stop" or (cmd == "pause" and src == "radio"):
        await radio_stop(app)
        await audible_pause(app)
        await spotify_pause(app)
    elif src == "audible":
        st = await app["audible"].status()
        if cmd == "pause" or (cmd == "play" and st.get("paused")):
            await app["audible"].cmd("pause" if cmd == "pause" else "playpause")
        elif cmd in ("next", "previous"):
            await app["audible"].cmd("nextch" if cmd == "next" else "prevch")
    elif src == "spotify" or (cmd == "play" and not app["radio"]["last"]):
        if cmd == "pause":
            await sp_call(app, "PUT", "me/player/pause")
        elif cmd == "play":
            await radio_stop(app)
            await sp_call(app, "PUT", "me/player/play", params={"device_id": await sp_device(app)})
        elif cmd in ("next", "previous"):
            await sp_call(app, "POST", f"me/player/{cmd}")
    elif cmd == "play" and src is None:
        await radio_start(app, app["radio"]["last"])
    return await remote_status(app)


def remote_app(main):
    @web.middleware
    async def guard(request, handler):
        tok = main["config"].get("remote_token") or ""
        got = request.headers.get("Authorization", "")
        if not tok or not hmac.compare_digest(got.encode(), f"Bearer {tok}".encode()):
            return ok({"error": "unauthorised"}, 401)
        try:
            return await handler(request)
        except LookupError as e:
            return ok({"error": str(e).strip("'\"")}, 404)
        except Exception as e:
            return ok({"error": str(e)}, 502)

    async def status(request):
        return ok(await remote_status(main))

    async def play(request):
        d = await request.json()
        out = await remote_play(main, d.get("source"), d.get("query"), d.get("kind"))
        main["knob"].emit({"t": "open", "app": out["source"]})     # the screen follows
        return ok(out)

    async def cmd(request):
        return ok(await remote_cmd(main, (await request.json()).get("cmd")))

    async def vol(request):
        return ok({"volume": await volume_set(main, float((await request.json())["set"]))})

    app = web.Application(middlewares=[guard])
    app.router.add_get("/status", status)
    app.router.add_post("/play", play)
    app.router.add_post("/cmd", cmd)
    app.router.add_post("/volume", vol)
    return app


async def remote_start(app):
    if not app["config"].get("remote_token"):
        return
    runner = web.AppRunner(remote_app(app), access_log=None)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", REMOTE_PORT).start()
    app["remote_runner"] = runner


# ------------------------------------------------------------------------- log

async def ui_log(request):
    """The page reports errors and test results here; they land in the journal."""
    text = (await request.text())[:2000]
    print(f"ui: {text}", flush=True)
    return ok()


# ------------------------------------------------------------------------- app

@web.middleware
async def no_cache(request, handler):
    resp = await handler(request)
    if not request.path.startswith("/api/"):
        resp.headers["Cache-Control"] = "no-cache"
    return resp


async def index(request):
    return web.FileResponse(UI_DIR / "index.html")


async def on_startup(app):
    app["http"] = ClientSession(timeout=ClientTimeout(total=8), headers={"User-Agent": UA})
    # Audiobooks (Audiobookshelf on talos). Kept under the "audible" key: the
    # ring app, voice and HA all still say Audible and mean his books.
    app["audible"] = Books(ClientSession(timeout=ClientTimeout(total=15), headers={"User-Agent": UA}),
                           app["books_mpv"], lambda: app["config"])
    app["timer_task"] = asyncio.create_task(timer_loop(app))
    app["knob_task"] = asyncio.create_task(app["knob"].run())
    app["volume_task"] = asyncio.create_task(volume_init(app))
    app["wake_task"] = asyncio.create_task(wake_loop(app))
    app["duck_task"] = asyncio.create_task(duck_loop(app))
    await remote_start(app)


async def on_shutdown(app):
    # Open SSE streams never finish by themselves; aiohttp would wait for them.
    app["knob"].emit(None)


async def on_cleanup(app):
    app["timer_task"].cancel()
    app["knob_task"].cancel()
    app["wake_task"].cancel()
    app["duck_task"].cancel()
    if app.get("remote_runner"):
        await app["remote_runner"].cleanup()
    await http(app).close()
    try:
        await app["audible"].close()        # save his place before going
    except Exception:
        pass
    await app["audible"].session.close()
    for mpv in (app["mpv"], app["books_mpv"]):
        if mpv.proc and mpv.proc.returncode is None:
            mpv.proc.terminate()


def build_app():
    app = web.Application(middlewares=[no_cache])
    app["config"] = load_config()
    app["sp_lock"] = asyncio.Lock()
    app["mpv"] = Mpv(MPV_SOCK)
    app["books_mpv"] = Mpv(BOOKS_SOCK)
    app["radio"] = {"station": None, "last": None, "genre_cache": {}}
    app["weather"] = {"data": None, "at": 0}
    app["timers"] = {}
    app["ha_areas"] = {"data": None, "at": 0}
    app["bt"] = {"agent": None, "pair_until": 0, "closer": None}
    app["calendar"] = {"data": None, "at": 0}
    app["knob"] = Knob()
    app["audio"] = {"playing": False, "source": None, "at": 0, "quiet_since": None}
    app["vol"] = {"base": None, "ducked": False, "undo": None}
    app["sp_dev"] = None
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    app.on_cleanup.append(on_cleanup)
    r = app.router
    r.add_get("/", index)
    r.add_get("/api/spotify/token", sp_token)
    r.add_post("/api/spotify/exchange", sp_exchange)
    r.add_get("/api/spotify/config", sp_config)
    r.add_post("/api/spotify/device", sp_device_report)
    r.add_route("*", "/api/spotify/web/{path:.*}", sp_web)
    r.add_get("/api/radio/status", radio_status)
    r.add_get("/api/radio/presets", radio_presets)
    r.add_get("/api/radio/genre/{tag}", radio_genre)
    r.add_post("/api/radio/play", radio_play)
    r.add_post("/api/radio/stop", radio_stop_h)
    r.add_post("/api/radio/volume", radio_volume)
    r.add_get("/api/weather", weather)
    r.add_get("/api/timers", timers_list)
    r.add_post("/api/timers", timers_add)
    r.add_delete("/api/timers/{id}", timers_delete)
    r.add_get("/api/ha/rooms", ha_rooms)
    r.add_post("/api/ha/service", ha_service)
    r.add_get("/api/calendar", calendar)
    r.add_get("/api/audible/library", audible_library)
    r.add_post("/api/audible/play", audible_play)
    r.add_get("/api/audible/status", audible_status)
    r.add_post("/api/audible/cmd", audible_cmd)
    r.add_get("/api/bt/status", bt_status)
    r.add_post("/api/bt/pair", bt_pair)
    r.add_post("/api/bt/cmd", bt_cmd)
    r.add_post("/api/backlight", backlight)
    r.add_get("/api/knob/stream", knob_stream)
    r.add_post("/api/knob/emit", knob_emit)
    r.add_post("/api/knob/talk", knob_talk)
    r.add_route("*", "/api/volume", volume)
    r.add_post("/api/audio/state", audio_state)
    r.add_post("/api/log", ui_log)
    r.add_static("/", UI_DIR)
    return app


if __name__ == "__main__":
    web.run_app(build_app(), host="127.0.0.1", port=int(os.environ.get("SATD_PORT", 8080)),
                shutdown_timeout=5)
