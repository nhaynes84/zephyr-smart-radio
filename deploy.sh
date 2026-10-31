#!/bin/sh
# Push the satellite software from talos to the Orange Pi and (re)install it.
# Idempotent: safe to run after any change. Usage: sh deploy.sh [host]
#
# Needs on the Pi (apt, once): cage chromium mpv python3-aiohttp python3-evdev libasound2-plugin-equal
#   fonts-inter fonts-noto-color-emoji alsa-utils curl
# go-librespot is pushed from talos (pinned release, see GLR below).
set -eu
HOST=${1:-root@192.168.86.62}
HERE=$(cd "$(dirname "$0")" && pwd)
GLR=${GLR:-}                     # optional go-librespot binary (unused: see README)
SSH="ssh -o BatchMode=yes -o ConnectTimeout=8 $HOST"

cd "$HERE"
COPYFILE_DISABLE=1 tar czf - satd ui touch system dt/ws-panel-on.py dt/ws-panel.service \
  | $SSH 'rm -rf /tmp/sat-deploy && mkdir -p /tmp/sat-deploy && tar xzf - -C /tmp/sat-deploy'
if [ -f "$GLR" ]; then
  scp -q -o BatchMode=yes "$GLR" "$HOST:/tmp/sat-deploy/go-librespot"
fi

$SSH 'sh -s' <<'REMOTE'
set -eu
D=/tmp/sat-deploy
getent group i2c >/dev/null || groupadd --system i2c
id sat >/dev/null 2>&1 || useradd --create-home --shell /bin/bash --user-group sat
passwd -l sat >/dev/null
usermod -aG audio,video,render,input,i2c,bluetooth sat

install -d /opt/satellite
rm -rf /opt/satellite/satd /opt/satellite/ui /opt/satellite/touch
cp -r $D/satd $D/ui $D/touch /opt/satellite/
runuser -u sat -- python3 $D/system/make-invisible-cursor.py /home/sat/.icons >/dev/null
install -m 755 $D/dt/ws-panel-on.py /usr/local/sbin/ws-panel-on
install -m 644 $D/dt/ws-panel.service /etc/systemd/system/ws-panel.service
for u in satd gt9271-touch kiosk audio-keepalive; do
  install -m 644 $D/system/$u.service /etc/systemd/system/$u.service
done
install -m 644 $D/system/99-satellite.rules /etc/udev/rules.d/99-satellite.rules
install -m 644 $D/system/asound.conf /etc/asound.conf
# go-librespot restarts only when its binary or config changed: a restart
# before pairing issues a new pairing code.
GLR_CHANGED=
if [ -f $D/go-librespot ] && ! cmp -s $D/go-librespot /usr/local/bin/go-librespot; then
  install -m 755 $D/go-librespot /usr/local/bin/go-librespot; GLR_CHANGED=1
fi
install -d -o sat -g sat /var/lib/go-librespot
if ! cmp -s $D/system/go-librespot.yml /var/lib/go-librespot/config.yml; then
  install -m 644 -o sat -g sat $D/system/go-librespot.yml /var/lib/go-librespot/config.yml; GLR_CHANGED=1
fi
if ! cmp -s $D/system/go-librespot.service /etc/systemd/system/go-librespot.service; then GLR_CHANGED=1; fi
[ -f /etc/satd.json ] || echo '{}' > /etc/satd.json
chown root:sat /etc/satd.json && chmod 640 /etc/satd.json

install -m 644 $D/system/go-librespot.service /etc/systemd/system/go-librespot.service

udevadm control --reload && udevadm trigger --subsystem-match=i2c-dev
systemctl daemon-reload
systemctl enable -q ws-panel satd gt9271-touch kiosk audio-keepalive
systemctl set-default graphical.target >/dev/null
systemctl restart satd gt9271-touch audio-keepalive
# go-librespot stays installed but OFF: Spotify refuses audio keys to librespot
# clients on newer accounts (go-librespot #279/#317). Spotify plays through the
# official Web Playback SDK in the kiosk instead.
systemctl disable -q --now go-librespot 2>/dev/null || true
: "${GLR_CHANGED:=}"
systemctl restart kiosk
rm -rf $D
for u in ws-panel satd gt9271-touch kiosk audio-keepalive; do printf '%-14s %s\n' $u "$(systemctl is-active $u)"; done
REMOTE
