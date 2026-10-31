#!/usr/bin/env python3
"""Power the Waveshare 3.4" DSI LCD (C) on, via its control MCU at I2C1 0x45.

The same register writes as Waveshare's Raspberry Pi driver
(raspberrypi/linux drivers/gpu/drm/panel/panel-waveshare-dsi.c):
    probe:     0xc0=1, 0xc2=1, 0xac=1   power rails on
    enable:    0xad=1                   display on
    backlight: 0xab=255-level, 0xaa=1   latch
No packages: plain ioctl on /dev/i2c-1.

usage: ws-panel-on [brightness 0-255]     (default 255)
       ws-panel-on off
"""
import fcntl
import os
import sys
import time

BUS, ADDR = 1, 0x45
I2C_SLAVE_FORCE = 0x0706


def write(fd, reg, val):
    os.write(fd, bytes([reg, val]))
    time.sleep(0.005)


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else "255"
    fd = os.open(f"/dev/i2c-{BUS}", os.O_RDWR)
    fcntl.ioctl(fd, I2C_SLAVE_FORCE, ADDR)
    if arg == "off":
        write(fd, 0xAD, 0x00)
        print("panel off")
        return
    level = max(0, min(255, int(arg)))
    write(fd, 0xC0, 0x01)
    write(fd, 0xC2, 0x01)
    write(fd, 0xAC, 0x01)
    time.sleep(0.1)
    write(fd, 0xAD, 0x01)
    write(fd, 0xAB, 0xFF - level)
    write(fd, 0xAA, 0x01)
    print(f"panel on, backlight {level}")


if __name__ == "__main__":
    main()
