#!/usr/bin/env python3
"""Userspace driver for the Waveshare 3.4" DSI panel's Goodix GT9271 touch.

The touch controller sits on the DSI ribbon's I2C (i2c-1, 0x14) but its INT
and RESET lines are not on the ribbon, so the kernel's goodix driver (which
needs the interrupt) cannot drive it. This polls the status register instead
and re-emits contacts through uinput as a direct multitouch screen, which
libinput -> cage -> Chromium see as a normal touchscreen.

Register map (GT911 family):
  0x814E  status: bit7 = buffer ready, bits0-3 = contact count. Write 0 to ack.
  0x814F  contacts, 8 bytes each: id, x lo, x hi, y lo, y hi, size lo, size hi, -
"""
import fcntl
import os
import sys
import time

from evdev import AbsInfo, UInput, ecodes as e

BUS, ADDR = 1, 0x14
I2C_SLAVE_FORCE = 0x0706
W = H = 800
MAX_CONTACTS = 5
POLL_S = 1 / 120
# Orientation fix-ups, if the panel ever reports mirrored or rotated.
SWAP_XY = os.environ.get("TOUCH_SWAP_XY") == "1"
INVERT_X = os.environ.get("TOUCH_INVERT_X") == "1"
INVERT_Y = os.environ.get("TOUCH_INVERT_Y") == "1"


class GT9271:
    def __init__(self):
        self.fd = os.open(f"/dev/i2c-{BUS}", os.O_RDWR)
        fcntl.ioctl(self.fd, I2C_SLAVE_FORCE, ADDR)

    def read(self, reg, n):
        os.write(self.fd, bytes([reg >> 8, reg & 0xFF]))
        return os.read(self.fd, n)

    def write(self, reg, val):
        os.write(self.fd, bytes([reg >> 8, reg & 0xFF, val]))

    def contacts(self):
        """Return {id: (x, y)} if the buffer was ready, else None."""
        st = self.read(0x814E, 1)[0]
        if not st & 0x80:
            return None
        n = min(st & 0x0F, MAX_CONTACTS)
        pts = {}
        if n:
            raw = self.read(0x814F, 8 * n)
            for i in range(n):
                p = raw[8 * i: 8 * i + 8]
                x, y = p[1] | p[2] << 8, p[3] | p[4] << 8
                if SWAP_XY:
                    x, y = y, x
                if INVERT_X:
                    x = W - 1 - x
                if INVERT_Y:
                    y = H - 1 - y
                pts[p[0]] = (min(max(x, 0), W - 1), min(max(y, 0), H - 1))
        self.write(0x814E, 0)
        return pts


def make_device():
    absx = AbsInfo(0, 0, W - 1, 0, 0, 0)
    absy = AbsInfo(0, 0, H - 1, 0, 0, 0)
    caps = {
        e.EV_KEY: [e.BTN_TOUCH],
        e.EV_ABS: [
            (e.ABS_X, absx), (e.ABS_Y, absy),
            (e.ABS_MT_SLOT, AbsInfo(0, 0, MAX_CONTACTS - 1, 0, 0, 0)),
            (e.ABS_MT_TRACKING_ID, AbsInfo(0, 0, 65535, 0, 0, 0)),
            (e.ABS_MT_POSITION_X, absx), (e.ABS_MT_POSITION_Y, absy),
        ],
    }
    return UInput(caps, name="Waveshare GT9271 Touch", input_props=[e.INPUT_PROP_DIRECT])


def main():
    ts = GT9271()
    pid = ts.read(0x8140, 4)
    print(f"touch controller {pid!r} on i2c-{BUS} 0x{ADDR:02x}", flush=True)
    ui = make_device()
    slots = {}          # contact id -> slot
    next_tid = 0
    errors = 0
    while True:
        try:
            pts = ts.contacts()
            errors = 0
        except OSError as err:
            errors += 1
            if errors in (1, 50) or errors % 1000 == 0:
                print(f"i2c error x{errors}: {err}", file=sys.stderr, flush=True)
            time.sleep(0.2 if errors > 50 else POLL_S)
            continue
        if pts is None:
            time.sleep(POLL_S)
            continue
        changed = False
        for cid in [c for c in slots if c not in pts]:          # lifted
            ui.write(e.EV_ABS, e.ABS_MT_SLOT, slots.pop(cid))
            ui.write(e.EV_ABS, e.ABS_MT_TRACKING_ID, -1)
            changed = True
        for cid, (x, y) in pts.items():
            if cid not in slots:                                 # new contact
                free = next(s for s in range(MAX_CONTACTS) if s not in slots.values())
                slots[cid] = free
                ui.write(e.EV_ABS, e.ABS_MT_SLOT, free)
                ui.write(e.EV_ABS, e.ABS_MT_TRACKING_ID, next_tid)
                next_tid = (next_tid + 1) & 0xFFFF
            else:
                ui.write(e.EV_ABS, e.ABS_MT_SLOT, slots[cid])
            ui.write(e.EV_ABS, e.ABS_MT_POSITION_X, x)
            ui.write(e.EV_ABS, e.ABS_MT_POSITION_Y, y)
            changed = True
        if changed:
            if pts:
                x, y = next(iter(pts.values()))
                ui.write(e.EV_ABS, e.ABS_X, x)
                ui.write(e.EV_ABS, e.ABS_Y, y)
            ui.write(e.EV_KEY, e.BTN_TOUCH, 1 if pts else 0)
            ui.syn()
        time.sleep(POLL_S)


if __name__ == "__main__":
    main()
