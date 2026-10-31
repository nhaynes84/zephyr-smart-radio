"""Audible driver for satd: the Audible web player in BACKGROUND tabs of the kiosk
Chromium, driven over its loopback DevTools port.

Why it looks like this (all measured on the Pi, 2026-10-16):
  * Audible has no Linux app. Its Cloud Player plays fine in this Chromium:
    Widevine licence "Granted", AAC over MSE, keys attach, audio advances.
  * BUT the player will not start streaming while document.visibilityState is
    "hidden" -- which a background tab always is. So every page load gets a
    script that makes the page believe it is visible. That is the whole trick.
  * Its play/±30 controls are unlabelled custom elements; clicking them would be
    brittle. The <audio> element is driven directly instead (play/pause, seek,
    playbackRate) -- the player follows it and still syncs his position.
  * Chapters come from the licenserequest response, captured off the wire.
  * Two tabs: LIBRARY (scraped for books) and PLAYER, so browsing never stops
    playback.
"""
from __future__ import annotations

import asyncio
import json
import time

DEVTOOLS = "http://127.0.0.1:9222"
LIBRARY_URL = "https://www.audible.com/library/titles"
PLAYER_PREFIX = "https://www.audible.com/webplayer"

VISIBLE = r"""(() => {
  if (window.__satVisible) return;
  window.__satVisible = true;
  const def = (o, k, v) => { try { Object.defineProperty(o, k, { configurable: true, get: () => v }); } catch (e) {} };
  def(Document.prototype, 'visibilityState', 'visible');
  def(Document.prototype, 'hidden', false);
  def(Document.prototype, 'webkitVisibilityState', 'visible');
  def(Document.prototype, 'webkitHidden', false);
  Document.prototype.hasFocus = () => true;
  const stop = e => e.stopImmediatePropagation();
  for (const ev of ['visibilitychange', 'webkitvisibilitychange']) document.addEventListener(ev, stop, true);
  window.addEventListener('blur', stop, true);
})()"""

SCRAPE = r"""(async () => {
  const rows = [...document.querySelectorAll('[id^=adbl-library-content-row-]')];
  const out = [];
  const realOpen = window.open;
  for (const r of rows) {
    const asin = r.id.replace('adbl-library-content-row-', '');
    const t = r.innerText.replace(/\s+/g, ' ');
    const by = (t.match(/By: (.+?) Narrated by:/) || [])[1] || '';
    const title = (r.querySelector('.bc-size-headline3, h2, h3, [class*=title] a, a.bc-link') || {}).innerText || t.split(' By: ')[0];
    const left = (t.match(/(\d+h(?: \d+m)? left|\d+m left|Finished)/) || [])[1] || '';
    const img = (r.querySelector('img') || {}).src || '';
    let url = null;
    const btn = [...r.querySelectorAll('a,button')].find(e => /Listen now/.test(e.innerText));
    if (btn) { window.open = u => { url = String(u); return null; }; try { btn.click(); } catch (e) {} window.open = realOpen; }
    out.push({ asin, title: (title || '').trim().slice(0, 120), author: by.trim(), left, cover: img, url });
  }
  return { url: location.href, books: out };
})()"""

STATUS = r"""(() => {
  const m = document.querySelector('audio');
  if (!m) return null;
  return { paused: m.paused, t: m.currentTime, dur: m.duration || 0, rate: m.playbackRate,
           ready: m.readyState, keys: !!m.mediaKeys, ended: m.ended };
})()"""


def _seek(to_expr):
    """JS that seeks the <audio> and KEEPS a paused book paused.

    ⚠️ Audible's player resumes playback after any seek -- measured: ±30 and
    chapter skips on a paused book left it reading aloud. If it was paused,
    pause it again as soon as it starts.
    """
    return ("(() => { const a = document.querySelector('audio'); const was = a.paused;"
            f" a.currentTime = {to_expr};"
            " if (was) { const stop = () => a.pause(); a.addEventListener('playing', stop, {once: true});"
            " setTimeout(() => { a.removeEventListener('playing', stop); a.pause(); }, 1500); }"
            " return 1; })()")


def _flatten(chapters):
    """Audible sends chapter_titles_type "Tree": parts may nest chapters. Leaves only."""
    out = []
    for c in chapters:
        if c.get("chapters"):
            out.extend(_flatten(c["chapters"]))
        else:
            out.append({"title": c.get("title"), "start_ms": c["start_offset_ms"],
                        "length_ms": c["length_ms"]})
    return out


class Tab:
    """One DevTools page session: request/response plus event callbacks."""

    def __init__(self, session, ws_url, on_event=None):
        self.session, self.ws_url, self.on_event = session, ws_url, on_event
        self.ws, self.n, self.pending, self.reader = None, 0, {}, None

    async def connect(self):
        self.ws = await self.session.ws_connect(self.ws_url, max_msg_size=64 << 20, heartbeat=20)
        self.reader = asyncio.create_task(self._read())

    @property
    def alive(self):
        return self.ws is not None and not self.ws.closed

    async def _read(self):
        try:
            async for msg in self.ws:
                data = json.loads(msg.data)
                fut = self.pending.pop(data.get("id"), None)
                if fut and not fut.done():
                    fut.set_result(data)
                elif "method" in data and self.on_event:
                    try:
                        await self.on_event(data["method"], data.get("params", {}))
                    except Exception:
                        pass
        finally:
            for fut in self.pending.values():
                if not fut.done():
                    fut.set_exception(ConnectionError("tab closed"))
            self.pending.clear()

    async def call(self, method, params=None, timeout=15):
        self.n += 1
        fut = asyncio.get_running_loop().create_future()
        self.pending[self.n] = fut
        await self.ws.send_json({"id": self.n, "method": method, "params": params or {}})
        msg = await asyncio.wait_for(fut, timeout)
        if "error" in msg:
            raise RuntimeError(f"{method}: {msg['error'].get('message')}")
        return msg.get("result", {})

    async def eval(self, expr, timeout=20):
        r = await self.call("Runtime.evaluate", {"expression": expr, "returnByValue": True,
                                                 "awaitPromise": True}, timeout=timeout)
        if r.get("exceptionDetails"):
            raise RuntimeError(r["exceptionDetails"].get("text", "eval failed"))
        return r.get("result", {}).get("value")

    async def close(self):
        if self.ws is not None:
            await self.ws.close()


class Audible:
    def __init__(self, session):
        self.session = session
        self.lib: Tab | None = None
        self.player: Tab | None = None
        self.player_id: str | None = None
        self.adopt_asin: str | None = None      # book in a player tab we inherited
        self.lock = asyncio.Lock()
        self.library = {"at": 0, "books": []}
        self.now = None            # {asin, title, author, cover}
        self.chapters = []         # [{title, start_ms, length_ms}]
        self.lic_req = None

    # -- tabs ----------------------------------------------------------------
    async def _tabs(self):
        async with self.session.get(f"{DEVTOOLS}/json/list") as r:
            return [t for t in await r.json(content_type=None) if t.get("type") == "page"]

    async def adopt(self):
        """At startup: a book left playing under a satd restart is picked up (status adopts it).
        Opens nothing when there is no player tab."""
        if not self.now and any(t["url"].startswith(PLAYER_PREFIX) for t in await self._tabs()):
            await self.status()

    async def _new_tab(self, url):
        async with self.session.get(f"{DEVTOOLS}/json/version") as r:
            browser = (await r.json(content_type=None))["webSocketDebuggerUrl"]
        async with self.session.ws_connect(browser) as ws:
            await ws.send_json({"id": 1, "method": "Target.createTarget",
                                "params": {"url": url, "background": True}})
            while True:
                msg = await ws.receive_json(timeout=10)
                if msg.get("id") == 1:
                    return msg["result"]["targetId"]

    async def _close_tab(self, target_id):
        async with self.session.get(f"{DEVTOOLS}/json/close/{target_id}") as r:
            await r.read()

    async def _attach(self, target_id, on_event=None):
        tab = next(t for t in await self._tabs() if t["id"] == target_id)
        t = Tab(self.session, tab["webSocketDebuggerUrl"], on_event)
        await t.connect()
        await t.call("Page.enable")
        await t.call("Page.addScriptToEvaluateOnNewDocument", {"source": VISIBLE})
        await t.eval(VISIBLE)
        await t.call("Emulation.setFocusEmulationEnabled", {"enabled": True})
        return t

    async def ensure(self):
        """Attach to (or open) the library and player tabs. Safe to call often."""
        async with self.lock:
            tabs = await self._tabs()
            if not (self.lib and self.lib.alive):
                def is_lib(t):
                    u = t["url"]
                    return ((u.startswith("https://www.audible.com/") and not u.startswith(PLAYER_PREFIX))
                            or "amazon.com/ap/" in u)
                found = next((t for t in tabs if is_lib(t)), None)
                tid = found["id"] if found else await self._new_tab(LIBRARY_URL)
                self.lib = await self._attach(tid)
            if not (self.player and self.player.alive):
                # ⚠️ Exactly ONE player tab, and it is ours. Audible streams one
                # title per account; stray player tabs (left by a crash or a
                # restart) fight over it, and attaching to the wrong one reported
                # a different book than the one playing.
                mine = self.player_id and next((t for t in tabs if t["id"] == self.player_id), None)
                players = [t for t in tabs if t["url"].startswith(PLAYER_PREFIX)]
                if not mine and len(players) == 1:
                    # satd restarted under a playing book: adopt it, don't kill it.
                    mine = players[0]
                    self.player_id = mine["id"]
                    self.adopt_asin = (mine["url"].split("asin=")[1].split("&")[0]
                                       if "asin=" in mine["url"] else None)
                for t in tabs:
                    stray = t["url"].startswith(PLAYER_PREFIX) or t["url"] == "about:blank"
                    if stray and (not mine or t["id"] != self.player_id):
                        await self._close_tab(t["id"])
                self.player_id = mine["id"] if mine else await self._new_tab("about:blank")
                self.player = await self._attach(self.player_id, self._player_event)
                await self.player.call("Network.enable")

    async def signed_in(self):
        await self.ensure()
        url = await self.lib.eval("location.href")
        return "/ap/signin" not in url and "audible.com" in url

    # -- network: capture chapters from the licence response -----------------
    async def _player_event(self, method, p):
        if method == "Network.requestWillBeSent" and "/licenserequest" in p["request"]["url"]:
            self.lic_req = p["requestId"]
        elif method == "Network.loadingFinished" and p.get("requestId") == self.lic_req:
            asyncio.create_task(self._read_licence(p["requestId"]))

    async def _read_licence(self, rid):
        try:
            r = await self.player.call("Network.getResponseBody", {"requestId": rid})
            body = r["body"]
            if r.get("base64Encoded"):
                import base64
                body = base64.b64decode(body).decode()
            meta = json.loads(body)["content_license"]["content_metadata"]
            self.chapters = _flatten(meta["chapter_info"]["chapters"])
            print(f"audible: {len(self.chapters)} chapters", flush=True)
        except Exception as e:
            print(f"audible: couldn't read chapters: {e!r}", flush=True)

    # -- library -------------------------------------------------------------
    async def get_library(self, refresh=False):
        if self.library["books"] and not refresh and time.time() - self.library["at"] < 600:
            return self.library["books"]
        await self.ensure()
        if not (await self.lib.eval("location.href")).startswith(LIBRARY_URL):
            await self.lib.call("Page.navigate", {"url": LIBRARY_URL})
        # A freshly opened tab reports the target URL before the page exists:
        # wait for book rows (or the sign-in page), up to ~25 s on a Pi.
        probe = ("({url: location.href, rows: document.querySelectorAll('[id^=adbl-library-content-row-]').length,"
                 " done: document.readyState === 'complete'})")
        for _ in range(50):
            try:
                st = await self.lib.eval(probe, timeout=5)
            except Exception:
                st = None
            if st and ("/ap/signin" in st["url"] or st["rows"] > 0):
                break
            await asyncio.sleep(0.5)
        res = await self.lib.eval(SCRAPE, timeout=40)
        if "/ap/signin" in res["url"]:
            raise PermissionError("not signed in")
        if res["books"]:      # never cache an empty read: it is a page that hadn't drawn yet
            self.library = {"at": time.time(), "books": res["books"]}
        return res["books"]

    # -- playback ------------------------------------------------------------
    async def play(self, asin):
        books = await self.get_library()
        book = next((b for b in books if b["asin"] == asin), None)
        if not book or not book["url"]:           # stale cache, or read before its Listen button drew
            books = await self.get_library(refresh=True)
            book = next((b for b in books if b["asin"] == asin), None)
        if not book or not book["url"]:
            raise LookupError("book not found in library")
        url = book["url"] if book["url"].startswith("http") else "https://www.audible.com" + book["url"]
        self.now = {k: book[k] for k in ("asin", "title", "author", "cover")}
        self.chapters = []
        await self.ensure()
        await self.player.call("Page.navigate", {"url": url})
        landed = False
        for _ in range(40):                       # up to ~20 s for keys + buffer
            await asyncio.sleep(0.5)
            try:
                here = await self.player.eval("location.href")
                st = await self.player.eval(STATUS)
            except Exception:
                continue
            landed = asin in here
            if landed and st and st["ready"] >= 3:
                break
        if not landed:
            self.now = None
            raise RuntimeError("Audible didn't open that book")
        await self.player.eval("document.querySelector('audio') && document.querySelector('audio').play().then(()=>1,()=>0)")

    async def status(self):
        if not self.now and self.player_id is None:
            try:
                await self.ensure()                # may adopt a player tab left playing
            except Exception:
                pass
        if not self.now and self.adopt_asin:
            try:
                book = next((b for b in await self.get_library() if b["asin"] == self.adopt_asin), None)
                if book:
                    # Chapters lived in a licence response this process never saw,
                    # so the chapter line stays blank until the next play() --
                    # better than reloading and interrupting a playing book.
                    self.now = {k: book[k] for k in ("asin", "title", "author", "cover")}
            except Exception:
                pass
            self.adopt_asin = None
        if not self.now:
            return {"active": False}
        if not (self.player and self.player.alive):
            try:                                   # reattach if the socket dropped
                await self.ensure()
            except Exception:
                return {"active": False}
        try:
            st = await self.player.eval(STATUS, timeout=5)
        except Exception:
            st = None
        if not st:
            return {"active": False}
        pos_ms = st["t"] * 1000
        ch = None
        for i, c in enumerate(self.chapters):
            if c["start_ms"] <= pos_ms < c["start_ms"] + c["length_ms"]:
                ch = {"index": i, "count": len(self.chapters), **c}
        return {"active": True, **self.now, **st, "chapter": ch}

    async def cmd(self, action, value=None):
        a = "document.querySelector('audio')"
        if action == "playpause":
            js = f"({a}.paused ? {a}.play() : {a}.pause(), 1)"
        elif action == "pause":
            js = f"({a} && {a}.pause(), 1)"
        elif action in ("back30", "fwd30"):
            d = -30 if action == "back30" else 30
            js = _seek(f"Math.max(0, Math.min({a}.duration - 1, {a}.currentTime + {d}))")
        elif action in ("prevch", "nextch"):
            st = await self.status()
            ch = st.get("chapter")
            if not ch:
                return
            i = ch["index"]
            if action == "prevch":
                # within 3 s of a chapter start -> previous chapter, else restart this one
                i = i - 1 if st["t"] * 1000 - ch["start_ms"] < 3000 and i > 0 else i
            else:
                i = min(i + 1, len(self.chapters) - 1)
            js = _seek(str(self.chapters[i]["start_ms"] / 1000))
        elif action == "rate":
            r = max(0.5, min(3.0, float(value)))
            js = f"({a}.playbackRate = {r}, 1)"
        else:
            raise ValueError("unknown action")
        if not (self.player and self.player.alive):
            await self.ensure()
        await self.player.eval(js)
