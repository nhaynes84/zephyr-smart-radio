#!/usr/bin/env python3
"""List an ESPHome device's entities, current states and services over the
encrypted native API. Key comes from esphome/secrets.yaml (never printed).

  ~/.venvs/esphome/bin/python esp-entities.py [host] [filter]
"""
import asyncio
import re
import sys
from pathlib import Path

from aioesphomeapi import APIClient

HOST = sys.argv[1] if len(sys.argv) > 1 else "satellite-voice.local"
FILTER = (sys.argv[2] if len(sys.argv) > 2 else "").lower()
SECRETS = Path(__file__).resolve().parent.parent / "esphome" / "secrets.yaml"


def secret(name):
    m = re.search(rf'^{name}:\s*"?([^"\n]+)"?', SECRETS.read_text(), re.M)
    return m.group(1)


async def main():
    cli = APIClient(HOST, 6053, None, noise_psk=secret("api_key"))
    await cli.connect(login=True)
    info = await cli.device_info()
    print(f"{info.name}  esphome {info.esphome_version}  project {info.project_name} {info.project_version}")
    entities, services = await cli.list_entities_services()
    states = {}
    cli.subscribe_states(lambda s: states.__setitem__(s.key, s))
    await asyncio.sleep(3)
    for e in sorted(entities, key=lambda e: (type(e).__name__, e.name)):
        kind = type(e).__name__.replace("Info", "")
        st = states.get(e.key)
        val = getattr(st, "state", "") if st else ""
        line = f"{kind:<22} {e.object_id:<40} {e.name:<36} {val}"
        if not FILTER or FILTER in line.lower():
            print(line)
    for s in services:
        if not FILTER or FILTER in s.name.lower():
            print(f"{'Service':<22} {s.name}  args={[a.name for a in s.args]}")
    await cli.disconnect()


asyncio.run(main())
