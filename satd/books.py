"""Audiobook driver for satd: the owner's Audiobookshelf server, played by a
dedicated mpv. Replaces the Audible web-player driver (audible.py, kept for reference).

Same interface the rest of satd and the UI already use -- get_library / play /
status / cmd / now -- so the ring app, voice "play X on Audible" and the Home
Assistant media player work unchanged. A book's "asin" is its Audiobookshelf
library-item id.

Progress is his, not Zephyr's: playback opens an Audiobookshelf session on his
account and syncs it every SYNC_S, so a book stopped in the car resumes here
and vice versa. Resuming after a long pause re-reads the server's position
first, in case another device moved on in the meantime.

Config (/etc/satd.json): abs_url, abs_token (an Audiobookshelf API key).
"""
from __future__ import annotations

import asyncio
import json
import time

SYNC_S = 15             # how often a playing book reports its position
STALE_PAUSE_S = 60      # paused longer than this: check the server before resuming
LIBRARY_TTL_S = 300


class Books:
    def __init__(self, session, mpv, config):
        self.session = session
        self.mpv = mpv              # its own mpv, separate from the radio's
        self.config = config        # callable -> current satd config
        self.lock = asyncio.Lock()
        self.library = {"at": 0, "books": []}
        self.lib_id = None
        self.now = None             # {asin, title, author, cover}
        self.chapters = []          # [{title, start_ms, length_ms}]
        self.tracks = []            # [{start, dur}] -- seconds, in book time
        self.sid = None             # Audiobookshelf playback session
        self.dur = 0.0
        self.listened = 0.0         # seconds since the last sync
        self.last_t = None
        self.paused_at = None
        self.synced_at = 0.0
        self.sync_task = None

    # -- server --------------------------------------------------------------
    def _base(self):
        return (self.config().get("abs_url") or "http://192.168.86.58:13378").rstrip("/")

    def _hdr(self):
        tok = self.config().get("abs_token")
        if not tok:
            raise PermissionError("no Audiobookshelf token in /etc/satd.json")
        return {"Authorization": f"Bearer {tok}"}

    async def _req(self, method, path, **kw):
        async with self.session.request(method, self._base() + path, headers=self._hdr(), **kw) as r:
            if r.status == 401:
                raise PermissionError("Audiobookshelf rejected the token")
            r.raise_for_status()
            body = await r.text()
            return json.loads(body) if body.strip()[:1] in ("{", "[") else None

    def cover(self, item_id):
        # Covers are public on Audiobookshelf, so HA and the page can load them directly.
        return f"{self._base()}/api/items/{item_id}/cover?width=400"

    async def signed_in(self):
        try:
            await self._req("GET", "/api/me")
            return True
        except PermissionError:
            return False

    async def adopt(self):
        """Nothing to adopt: the books mpv is satd's child and stops with it."""

    # -- library -------------------------------------------------------------
    async def get_library(self, refresh=False):
        if self.library["books"] and not refresh and time.time() - self.library["at"] < LIBRARY_TTL_S:
            return self.library["books"]
        if not self.lib_id:
            libs = (await self._req("GET", "/api/libraries"))["libraries"]
            book_libs = [l for l in libs if l.get("mediaType") == "book"]
            if not book_libs:
                raise LookupError("no audiobook library on the server")
            self.lib_id = book_libs[0]["id"]
        items = (await self._req("GET", f"/api/libraries/{self.lib_id}/items",
                                 params={"limit": 0, "minified": 1}))["results"]
        me = await self._req("GET", "/api/me")
        prog = {p["libraryItemId"]: p for p in me.get("mediaProgress", []) if not p.get("episodeId")}
        books = []
        for it in items:
            md = it["media"]["metadata"]
            dur = it["media"].get("duration") or 0
            p = prog.get(it["id"])
            if p and p.get("isFinished"):
                left = "Finished"
            elif p and p.get("currentTime"):
                left = _hm(dur - p["currentTime"]) + " left"
            else:
                left = ""
            books.append({"asin": it["id"], "title": (md.get("title") or "")[:120],
                          "author": md.get("authorName") or "", "left": left,
                          "cover": self.cover(it["id"]), "url": None,
                          # in progress first (most recent), then newest added
                          "_k": (1 if p and not p.get("isFinished") and p.get("currentTime") else 0,
                                 (p or {}).get("lastUpdate") or 0, it.get("addedAt") or 0)})
        books.sort(key=lambda b: b["_k"], reverse=True)
        for b in books:
            del b["_k"]
        if books:
            self.library = {"at": time.time(), "books": books}
        return books

    # -- playback ------------------------------------------------------------
    async def play(self, asin):
        async with self.lock:
            await self._close_session()
            s = await self._req("POST", f"/api/items/{asin}/play", json={
                "deviceInfo": {"clientName": "Zephyr", "deviceId": "zephyr"},
                "forceDirectPlay": True, "forceTranscode": False, "mediaPlayer": "mpv",
                "supportedMimeTypes": ["audio/mp4", "audio/x-m4b", "audio/aac", "audio/mpeg",
                                       "audio/flac", "audio/ogg", "audio/x-m4a"]})
            self.sid = s["id"]
            self.dur = float(s.get("duration") or 0)
            self.chapters = [{"title": c.get("title"), "start_ms": int(c["start"] * 1000),
                              "length_ms": int((c["end"] - c["start"]) * 1000)}
                             for c in s.get("chapters") or []]
            self.tracks = [{"start": float(t.get("startOffset") or 0), "dur": float(t.get("duration") or 0),
                            "url": self._base() + t["contentUrl"]} for t in s["audioTracks"]]
            md = (s.get("mediaMetadata") or {})
            self.now = {"asin": asin, "title": s.get("displayTitle") or md.get("title") or "",
                        "author": s.get("displayAuthor") or md.get("authorName") or "",
                        "cover": self.cover(asin)}
            start = float(s.get("currentTime") or 0)
            if self.dur and start >= self.dur - 5:      # finished book: from the top
                start = 0.0
            tok = self.config().get("abs_token")
            await self.mpv.cmd("playlist-clear")
            first, off = self._locate(start)
            for i, t in enumerate(self.tracks):
                opts = f"start={off:.1f}" if i == first else ""
                await self.mpv.cmd("loadfile", f"{t['url']}?token={tok}",
                                   "replace" if i == 0 else "append", -1, opts)
            if first:
                await self.mpv.cmd("set_property", "playlist-pos", first)
            await self.mpv.cmd("set_property", "pause", False)
            self.listened, self.last_t, self.paused_at = 0.0, start, None
            self.synced_at = time.time()
            if not self.sync_task or self.sync_task.done():
                self.sync_task = asyncio.create_task(self._sync_loop())

    def _locate(self, t):
        """Book time -> (track index, offset into that track)."""
        for i, tr in enumerate(self.tracks):
            if t < tr["start"] + tr["dur"] or i == len(self.tracks) - 1:
                return i, max(0.0, t - tr["start"])
        return 0, 0.0

    async def _ended(self):
        """Ran off the end of the last track. Not the same as no position yet:
        for the first second or so of a play mpv is still opening the file, and
        treating that as the end closed the session before a single sync."""
        return bool(await self.mpv.prop("idle-active"))

    async def _pos(self):
        """Book-time position, or None while nothing is playing yet (or at all)."""
        if await self.mpv.prop("idle-active"):
            return None
        i = await self.mpv.prop("playlist-pos")
        tp = await self.mpv.prop("time-pos")
        if i is None or i < 0 or tp is None or i >= len(self.tracks):
            return None
        return self.tracks[i]["start"] + tp

    async def _seek(self, t):
        t = max(0.0, min(self.dur - 1 if self.dur else t, t))
        i, off = self._locate(t)
        if i != await self.mpv.prop("playlist-pos"):
            await self.mpv.cmd("set_property", "playlist-pos", i)
            for _ in range(30):                 # wait for the track to open before seeking in it
                await asyncio.sleep(0.1)
                if await self.mpv.prop("time-pos") is not None:
                    break
        await self.mpv.cmd("seek", off, "absolute")
        self.last_t = t

    async def status(self):
        if not self.now:
            return {"active": False}
        t = await self._pos()
        paused = bool(await self.mpv.prop("pause"))
        ended = False
        if t is None:
            ended = await self._ended()
            t = self.dur if ended else (self.last_t or 0.0)
            paused = paused or ended
        rate = await self.mpv.prop("speed") or 1.0
        pos_ms = t * 1000
        ch = None
        for i, c in enumerate(self.chapters):
            if c["start_ms"] <= pos_ms < c["start_ms"] + c["length_ms"]:
                ch = {"index": i, "count": len(self.chapters), **c}
        return {"active": True, **self.now, "paused": paused, "t": t, "dur": self.dur, "rate": rate,
                "ready": 4, "keys": False, "ended": ended, "chapter": ch}

    async def cmd(self, action, value=None):
        if not self.now:
            return
        if action in ("playpause", "pause", "play"):
            paused = bool(await self.mpv.prop("pause"))
            if action == "pause" or (action == "playpause" and not paused):
                if not paused:
                    await self.mpv.cmd("set_property", "pause", True)
                    self.paused_at = time.time()
                    await self._sync()
                return
            if await self._ended():              # finished: start again from the server's idea
                return await self.play(self.now["asin"])
            if self.paused_at and time.time() - self.paused_at > STALE_PAUSE_S:
                await self._catch_up()
            await self.mpv.cmd("set_property", "pause", False)
            self.paused_at = None
            return
        t = await self._pos()
        if t is None:
            return
        if action in ("back30", "fwd30"):
            await self._seek(t + (-30 if action == "back30" else 30))
        elif action in ("prevch", "nextch"):
            st = await self.status()
            ch = st.get("chapter")
            if not ch:
                return
            i = ch["index"]
            if action == "prevch":
                # within 3 s of a chapter start -> previous chapter, else restart this one
                i = i - 1 if t * 1000 - ch["start_ms"] < 3000 and i > 0 else i
            else:
                i = min(i + 1, len(self.chapters) - 1)
            await self._seek(self.chapters[i]["start_ms"] / 1000)
        elif action == "rate":
            await self.mpv.cmd("set_property", "speed", max(0.5, min(3.0, float(value))))
        else:
            raise ValueError("unknown action")

    async def _catch_up(self):
        """Another device may have listened on while this one sat paused."""
        try:
            p = await self._req("GET", f"/api/me/progress/{self.now['asin']}")
        except Exception:
            return
        if p and (p.get("lastUpdate") or 0) / 1000 > self.synced_at + 1:
            await self._seek(float(p.get("currentTime") or 0))

    # -- progress sync -------------------------------------------------------
    async def _sync(self, final=False):
        if not self.sid:
            return
        t = await self._pos()
        if t is None:
            t = self.dur if self.last_t and self.dur - self.last_t < 30 else self.last_t
        if t is None:
            return
        body = {"currentTime": t, "timeListened": round(self.listened, 1), "duration": self.dur}
        try:
            await self._req("POST", f"/api/session/{self.sid}/{'close' if final else 'sync'}", json=body)
            self.listened = 0.0
            self.synced_at = time.time()
        except Exception as e:
            print(f"books: sync failed: {e!r}", flush=True)

    async def _sync_loop(self):
        tick = 1.0
        while self.sid:
            await asyncio.sleep(tick)
            try:
                t = await self._pos()
                if t is not None and not await self.mpv.prop("pause"):
                    # count real listening only (a seek is not listening)
                    if self.last_t is not None and 0 < t - self.last_t < 5 * tick * 3:
                        self.listened += (t - self.last_t) / (await self.mpv.prop("speed") or 1.0)
                    self.last_t = t
                    if time.time() - self.synced_at >= SYNC_S:
                        await self._sync()
                elif t is None and await self._ended():   # ran off the end
                    await self._sync(final=True)
                    self.sid = None
            except Exception as e:
                print(f"books: {e!r}", flush=True)

    async def _close_session(self):
        if self.sid:
            await self._sync(final=True)
            self.sid = None

    async def close(self):
        await self._close_session()


def _hm(sec):
    sec = max(0, int(sec))
    h, m = sec // 3600, sec // 60 % 60
    return f"{h}h {m}m" if h else f"{m}m"
