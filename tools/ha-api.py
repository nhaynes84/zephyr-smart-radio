#!/usr/bin/env python3
"""Tiny Home Assistant API helper, run ON THE PI (the token lives in /etc/satd.json
there and nowhere else).

  ha-api.py entries [domain]            list config entries
  ha-api.py add-esphome HOST            add an ESPHome device; noise key on stdin
  ha-api.py pipelines                   list Assist pipelines (websocket)
"""
import asyncio
import json
import sys
import urllib.request

CFG = json.load(open("/etc/satd.json"))
BASE, TOKEN = CFG.get("ha_url", "http://192.168.86.56:8123").rstrip("/"), CFG["ha_token"]   # same default as satd


def rest(method, path, body=None):
    req = urllib.request.Request(
        BASE + path, method=method, data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read() or b"null")


def entries(domain=None):
    for e in rest("GET", "/api/config/config_entries/entry"):
        if domain and e["domain"] != domain:
            continue
        print(f"{e['domain']:<16} {e['state']:<14} {e['title']}")


def add_esphome(host):
    key = sys.stdin.read().strip()
    flow = rest("POST", "/api/config/config_entries/flow", {"handler": "esphome", "show_advanced_options": False})
    step = rest("POST", f"/api/config/config_entries/flow/{flow['flow_id']}", {"host": host, "port": 6053})
    if step.get("step_id") == "encryption_key":
        step = rest("POST", f"/api/config/config_entries/flow/{flow['flow_id']}", {"noise_psk": key})
    print(json.dumps({k: step.get(k) for k in ("type", "step_id", "title", "reason", "errors")}))


async def ws(msgs):
    import aiohttp
    async with aiohttp.ClientSession() as s:
        async with s.ws_connect(BASE.replace("http", "ws", 1) + "/api/websocket") as w:
            await w.receive_json()
            await w.send_json({"type": "auth", "access_token": TOKEN})
            assert (await w.receive_json())["type"] == "auth_ok"
            out = []
            for i, m in enumerate(msgs, 1):
                await w.send_json({"id": i, **m})
                while True:
                    r = await w.receive_json()
                    if r.get("id") == i:
                        out.append(r)
                        break
            return out


def pipelines():
    (r,) = asyncio.run(ws([{"type": "assist_pipeline/pipeline/list"}]))
    res = r["result"]
    print("preferred:", res.get("preferred_pipeline"))
    for p in res["pipelines"]:
        print(json.dumps({k: p.get(k) for k in ("id", "name", "conversation_engine", "stt_engine",
                                                 "tts_engine", "wake_word_entity", "language")}))


def runs(limit=8, name=None):
    """Recent Assist runs on the preferred pipeline: what STT heard, what came back."""
    (pl,) = asyncio.run(ws([{"type": "assist_pipeline/pipeline/list"}]))
    pid = next((p["id"] for p in pl["result"]["pipelines"] if p["name"] == name), None) if name else pl["result"]["preferred_pipeline"]
    (lst,) = asyncio.run(ws([{"type": "assist_pipeline/pipeline_debug/list", "pipeline_id": pid}]))
    ids = [r["pipeline_run_id"] for r in lst["result"]["pipeline_runs"]][-limit:]
    got = asyncio.run(ws([{"type": "assist_pipeline/pipeline_debug/get", "pipeline_id": pid,
                           "pipeline_run_id": i} for i in ids]))
    for g in got:
        ev = {e["type"]: e for e in g["result"]["events"]}
        start = ev.get("run-start", {}).get("timestamp", "")[11:19]
        stt_end = (ev.get("stt-end") or {}).get("data") or {}
        heard = (stt_end.get("stt_output") or {}).get("text")
        intent = ((ev.get("intent-end") or {}).get("data") or {}).get("intent_output") or {}
        speech = (((intent.get("response") or {}).get("speech") or {}).get("plain") or {}).get("speech")
        err = (ev.get("error") or {}).get("data")
        vad = (ev.get("stt-vad-end") or {}).get("timestamp", "")[11:19]
        print(f"{start}  heard={heard!r}  vad_end={vad}  reply={speech!r}" + (f"  ERROR={err}" if err else ""))


def add_mcp_server():
    """Set up HA's MCP server integration on the Assist API (idempotent)."""
    if any(e["domain"] == "mcp_server" for e in rest("GET", "/api/config/config_entries/entry")):
        print(json.dumps({"type": "already_configured"}))
        return
    flow = rest("POST", "/api/config/config_entries/flow", {"handler": "mcp_server"})
    step = flow
    if flow.get("type") == "form":
        step = rest("POST", f"/api/config/config_entries/flow/{flow['flow_id']}", {"llm_hass_api": ["assist"]})
    print(json.dumps({k: step.get(k) for k in ("type", "step_id", "title", "reason", "errors")}))


def new_token(name):
    """Mint a long-lived token for the token's own user; prints ONLY the token (pipe it)."""
    (r,) = asyncio.run(ws([{"type": "auth/long_lived_access_token", "client_name": name,
                            "lifespan": 3650}]))
    if not r.get("success"):
        sys.exit(f"token creation failed: {r.get('error')}")
    sys.stdout.write(r["result"])


def clone_pipeline(src_name, new_name, agent_entity):
    """Copy pipeline `src_name` as `new_name` with a different conversation agent (idempotent)."""
    (lst,) = asyncio.run(ws([{"type": "assist_pipeline/pipeline/list"}]))
    pipes = lst["result"]["pipelines"]
    if any(p["name"] == new_name for p in pipes):
        print(json.dumps({"exists": new_name}))
        return
    src = next(p for p in pipes if p["name"] == src_name)
    keep = ("conversation_language", "language", "stt_engine", "stt_language", "tts_engine",
            "tts_language", "tts_voice", "wake_word_entity", "wake_word_id", "prefer_local_intents")
    body = {k: src.get(k) for k in keep if k in src}
    body.update(name=new_name, conversation_engine=agent_entity, prefer_local_intents=False)
    (r,) = asyncio.run(ws([{"type": "assist_pipeline/pipeline/create", **body}]))
    print(json.dumps({"success": r.get("success"), "error": r.get("error"),
                      "id": (r.get("result") or {}).get("id")}))


def add_remote_calendar(name):
    """Add an ICS calendar to HA as remote_calendar. The (secret) URL comes on stdin."""
    url = sys.stdin.read().strip()
    flow = rest("POST", "/api/config/config_entries/flow", {"handler": "remote_calendar"})
    step = rest("POST", f"/api/config/config_entries/flow/{flow['flow_id']}",
                {"calendar_name": name, "url": url, "verify_ssl": True})
    print(json.dumps({k: step.get(k) for k in ("type", "step_id", "title", "reason", "errors")}))


def entities(substr):
    for s in rest("GET", "/api/states"):
        if substr in s["entity_id"]:
            print(s["entity_id"], "=", s["state"], s["attributes"].get("friendly_name", ""))


def select(entity_id, option):
    rest("POST", "/api/services/select/select_option", {"entity_id": entity_id, "option": option})
    print(entity_id, "->", rest("GET", f"/api/states/{entity_id}")["state"])


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "entries":
        entries(sys.argv[2] if len(sys.argv) > 2 else None)
    elif cmd == "add-esphome":
        add_esphome(sys.argv[2])
    elif cmd == "pipelines":
        pipelines()
    elif cmd == "runs":
        runs(int(sys.argv[2]) if len(sys.argv) > 2 else 8, sys.argv[3] if len(sys.argv) > 3 else None)
    elif cmd == "add-mcp-server":
        add_mcp_server()
    elif cmd == "new-token":
        new_token(sys.argv[2])
    elif cmd == "clone-pipeline":
        clone_pipeline(sys.argv[2], sys.argv[3], sys.argv[4])
    elif cmd == "add-remote-calendar":
        add_remote_calendar(sys.argv[2])
    elif cmd == "entities":
        entities(sys.argv[2])
    elif cmd == "select":
        select(sys.argv[2], sys.argv[3])
