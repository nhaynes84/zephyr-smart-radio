#!/bin/sh
# Screenshot every view of the satellite UI on the Pi (headless Chromium) and
# pull the PNGs back to talos. Usage: sh shots.sh [outdir] [host]
set -eu
OUT=${1:-/tmp/sat-shots}
HOST=${2:-root@192.168.86.62}
mkdir -p "$OUT"
ssh -o BatchMode=yes "$HOST" 'sh -s' <<'REMOTE'
set -eu
rm -rf /tmp/shots && mkdir -p /tmp/shots
for v in home spotify radio weather timers clock ha; do
  timeout 40 chromium --headless=new --no-sandbox --disable-gpu --hide-scrollbars \
    --user-data-dir=/tmp/shots/profile-$v --window-size=800,800 --virtual-time-budget=4000 \
    --screenshot=/tmp/shots/$v.png "http://127.0.0.1:8080/#$v" >/dev/null 2>&1 || echo "shot $v failed"
done
ls /tmp/shots/*.png
REMOTE
scp -q -o BatchMode=yes "$HOST:/tmp/shots/*.png" "$OUT/"
ls "$OUT"
