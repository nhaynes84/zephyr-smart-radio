#!/usr/bin/env python3
"""Drive the kiosk Chromium over its loopback DevTools port (run ON THE PI).

  cdp.py list                         tabs
  cdp.py open URL                     new BACKGROUND tab -> prints target id
  cdp.py front TARGET                 bring a tab to the front (e.g. for sign-in)
  cdp.py back                         bring the satellite UI back to the front
  cdp.py shot TARGET OUT.png          screenshot a tab (works in the background)
  cdp.py eval TARGET 'js expression'  evaluate in a tab, print JSON result
  cdp.py close TARGET
"""
import asyncio
import base64
import json
import sys
import urllib.request

import aiohttp

DEVTOOLS = "http://127.0.0.1:9222"
UI_URL = "http://127.0.0.1:8080/"


def tabs():
    return json.load(urllib.request.urlopen(f"{DEVTOOLS}/json/list", timeout=5))


async def call(ws_url, method, params=None, session_cmds=None):
    async with aiohttp.ClientSession() as s:
        async with s.ws_connect(ws_url, max_msg_size=64 << 20) as ws:
            await ws.send_json({"id": 1, "method": method, "params": params or {}})
            while True:
                msg = await ws.receive_json(timeout=30)
                if msg.get("id") == 1:
                    if "error" in msg:
                        raise SystemExit(f"{method}: {msg['error']}")
                    return msg.get("result", {})


def browser_ws():
    return json.load(urllib.request.urlopen(f"{DEVTOOLS}/json/version", timeout=5))["webSocketDebuggerUrl"]


def page_ws(target):
    for t in tabs():
        if t["id"] == target:
            return t["webSocketDebuggerUrl"]
    raise SystemExit(f"no tab {target}")


def main():
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == "list":
        for t in tabs():
            if t["type"] == "page":
                print(t["id"], t["url"][:100], "|", t["title"][:50])
    elif cmd == "open":
        r = asyncio.run(call(browser_ws(), "Target.createTarget",
                             {"url": args[0], "background": True}))
        print(r["targetId"])
    elif cmd == "front":
        asyncio.run(call(browser_ws(), "Target.activateTarget", {"targetId": args[0]}))
    elif cmd == "back":
        ui = next(t["id"] for t in tabs() if t["type"] == "page" and t["url"].startswith(UI_URL))
        asyncio.run(call(browser_ws(), "Target.activateTarget", {"targetId": ui}))
    elif cmd == "shot":
        r = asyncio.run(call(page_ws(args[0]), "Page.captureScreenshot", {"format": "png"}))
        open(args[1], "wb").write(base64.b64decode(r["data"]))
        print("wrote", args[1])
    elif cmd == "eval":
        r = asyncio.run(call(page_ws(args[0]), "Runtime.evaluate",
                             {"expression": args[1], "returnByValue": True, "awaitPromise": True}))
        print(json.dumps(r.get("result", {}).get("value"), indent=1)[:4000])
    elif cmd == "close":
        asyncio.run(call(browser_ws(), "Target.closeTarget", {"targetId": args[0]}))
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
