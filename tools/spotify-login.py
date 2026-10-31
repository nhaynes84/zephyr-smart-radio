#!/usr/bin/env python3
"""One-time Spotify login for the satellite (Authorization Code + PKCE, no secret).

  spotify-login.py start CLIENT_ID        print the URL to open in a browser
  spotify-login.py finish 'REDIRECT_URL'  hand the code to the Pi, which exchanges
                                          it and keeps the refresh token itself

After approving, the browser lands on http://127.0.0.1:8888/callback?code=...
and shows "can't connect" -- that is expected; copy that URL from the address
bar. The verifier lives in a 600 file next to this script's state until finish.
"""
import base64
import hashlib
import json
import os
import secrets
import subprocess
import sys
import urllib.parse
from pathlib import Path

REDIRECT = "http://127.0.0.1:8888/callback"
SCOPES = ("streaming user-read-email user-read-private user-read-playback-state "
          "user-modify-playback-state user-read-currently-playing user-read-recently-played "
          "user-top-read user-library-read playlist-read-private")
PI = os.environ.get("SAT_HOST", "root@192.168.86.62")
STATE = Path(os.environ.get("TMPDIR", "/tmp")) / "sat-spotify-pkce.json"


def start(client_id):
    verifier = secrets.token_urlsafe(64)[:96]
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    state = secrets.token_urlsafe(16)
    STATE.write_text(json.dumps({"verifier": verifier, "state": state, "client_id": client_id}))
    os.chmod(STATE, 0o600)
    print("https://accounts.spotify.com/authorize?" + urllib.parse.urlencode({
        "client_id": client_id, "response_type": "code", "redirect_uri": REDIRECT,
        "code_challenge_method": "S256", "code_challenge": challenge, "scope": SCOPES, "state": state}))


def finish(url):
    saved = json.loads(STATE.read_text())
    q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    if "error" in q:
        sys.exit(f"Spotify said: {q['error'][0]}")
    if q.get("state", [None])[0] != saved["state"]:
        sys.exit("state mismatch -- run start again and use the newest URL")
    body = json.dumps({"code": q["code"][0], "code_verifier": saved["verifier"], "redirect_uri": REDIRECT})
    out = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", PI,
         "curl -s -m 20 -X POST -H 'Content-Type: application/json' --data-binary @- "
         "http://127.0.0.1:8080/api/spotify/exchange"],
        input=body, capture_output=True, text=True, timeout=40)
    print(out.stdout or out.stderr)
    STATE.unlink(missing_ok=True)


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "start":
        start(sys.argv[2])
    elif len(sys.argv) == 3 and sys.argv[1] == "finish":
        finish(sys.argv[2])
    else:
        sys.exit(__doc__)
