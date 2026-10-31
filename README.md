# Zephyr

Nick's bullet-radio kitchen speaker and voice satellite: a 40s Fada-style case in ivory and
turquoise, a round 800x800 touch screen, a knob, and a Dayton PC83 music speaker. You talk to it
and Claude answers; it plays Spotify, internet radio, Audible and phone audio.

Two computers live inside:

| Half | Hardware | Software here |
|---|---|---|
| **Radio** (screen, music, knob) | Orange Pi 3B (eMMC), Waveshare 3.4" round DSI, GT9271 touch, EC11 knob, MAX98357A amp on I2S1 -> PC83 | `satd/`, `ui/`, `touch/`, `system/`, `dt/` |
| **Voice** (mics, wake word, replies) | reSpeaker XVF3800 (4 mics, XMOS DSP with echo cancellation) + XIAO ESP32-S3 on ESPHome, own small speaker | `esphome/` |

Power: a 2-port USB-C GaN brick outside, one port to the Pi and one to the XIAO. Only plug the
XIAO's USB-C into the reSpeaker; plugging both knocks the reSpeaker out of USB mode.

## How a question flows

wake word (on the XIAO) -> Home Assistant pipeline "Satellite (Claude)" -> Whisper on talos ->
`conversation.satellite_claude` (nexus_voice, in the roam repo) -> the persistent ROAM hub
channel "Satellite", running in `agent/` -> Piper TTS on talos -> the reSpeaker's speaker.
While the satellite listens or talks, satd ducks the music. While Zephyr plays anything, satd
switches the wake word off (HA `select.satellite_voice_wake_word` = `no_wake_word`), because
the reSpeaker only cancels the echo of its own speaker, not Zephyr's. The knob still talks.

## Layout

| Path | What |
|---|---|
| `satd/` | aiohttp service on the Pi (:8080): UI backend, Spotify/radio/Audible/Bluetooth, timers, volume and ducking, wake word control, HA remote API. `audible.py` drives the Audible web player over loopback DevTools. |
| `ui/` | Kiosk page (cage + Chromium): ring of apps, Spotify Web Playback SDK device "Zephyr", Audible remote view. |
| `touch/` | GT9271 poller -> uinput (the ribbon has no INT line). |
| `system/` | systemd units, udev rules, `asound.conf` (EQ -> softvol -> dmix -> amp). |
| `dt/` | Device-tree overlays: DSI panel, MAX98357A on I2S1, EC11 knob. `attic/`, `debug/` = bring-up history. |
| `esphome/` | `satellite-voice.yaml` for the XIAO (formatBCE XVF3800 integration, pinned). `secrets.yaml` is local only. |
| `ha/` | `satellite_speaker` custom component: Zephyr as `media_player.zephyr` in HA. |
| `agent/` | Workspace of the "Satellite" hub channel: `CLAUDE.md` = spoken rules; `.mcp.json` (local only) = HA + ROAM hub MCP. Restart the pane after editing either. |
| `tools/` | `shots.sh` (screenshot every view), `spotify-login.py`, `esp-entities.py`, `ha-api.py` (runs on the Pi), `cdp.py`. |
| `cad/` | `satellite.py` (build123d) and vendor `ref/` models. Output goes to `~/Collab/CAD/voice-satellite/`. |
| `wakeword/` | Trained "Hey Zephyr" models (added after training). |

## Commands

```sh
sh deploy.sh                    # push satd/ui/touch/system to the Pi (root@192.168.86.62) and restart
sh tools/shots.sh <dir>         # screenshots of every view
~/.venvs/esphome/bin/esphome run esphome/satellite-voice.yaml   # build + OTA the voice half
python cad/satellite.py          # rebuild the case: any python with build123d (see the file header)
```

Voice half: `satellite-voice` @ 192.168.86.53, in HA as "Satellite Voice". ⚠️ macOS Local Network
privacy blocks Homebrew python3.13 from the LAN; the ESPHome venv uses python 3.14, which is allowed.

## Gotchas

- Deploying the kiosk stops Audible. To change satd alone, copy `satd/*.py` and `systemctl restart satd`.
- Audible resumes after any seek; `_seek()` re-pauses a paused book.
- go-librespot is dead for this account (Spotify refuses its audio keys); installed but disabled.
- Spotify needs Widevine (ChromeOS CDM via widevine_fixup.py) at /usr/lib/chromium/WidevineCdm.
