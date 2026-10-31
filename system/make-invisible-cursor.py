#!/usr/bin/env python3
"""Write an invisible Xcursor theme ("invisible") into a directory.

cage (the kiosk compositor) draws its own pointer and has no flag to hide it;
the page's `cursor: none` only covers Chromium's surface. Pointing cage at a
theme whose every cursor is one transparent pixel makes the arrow disappear
everywhere. Usage: make-invisible-cursor.py ~/.icons
"""
import os
import struct
import sys

NAMES = ["default", "left_ptr", "arrow", "pointer", "hand1", "hand2", "text", "xterm", "wait",
         "watch", "progress", "crosshair", "grab", "grabbing", "move", "not-allowed",
         "col-resize", "row-resize", "e-resize", "n-resize", "ne-resize", "nw-resize",
         "s-resize", "se-resize", "sw-resize", "w-resize", "ew-resize", "ns-resize",
         "nesw-resize", "nwse-resize", "all-scroll", "cell", "context-menu", "help",
         "question_arrow", "top_left_arrow", "zoom-in", "zoom-out"]


def xcursor_1x1() -> bytes:
    """Xcursor file: one 1x1 fully transparent ARGB image (nominal size 24)."""
    img_type, nominal = 0xFFFD0002, 24
    chunk = struct.pack("<9I", 36, img_type, nominal, 1, 1, 1, 0, 0, 0) + struct.pack("<I", 0)
    header = struct.pack("<4sIII", b"Xcur", 16, 0x10000, 1)
    toc = struct.pack("<III", img_type, nominal, 16 + 12)
    return header + toc + chunk


def main(root: str) -> None:
    # ⚠️ Written as BOTH "invisible" and "default": cage 0.2 creates its cursor
    # manager with no theme name, so libxcursor loads the theme called
    # "default" from XCURSOR_PATH and ignores XCURSOR_THEME. With only
    # "invisible" installed it fell back to its built-in arrow.
    data = xcursor_1x1()
    for theme_name in ("invisible", "default"):
        theme = os.path.join(os.path.expanduser(root), theme_name)
        cursors = os.path.join(theme, "cursors")
        os.makedirs(cursors, exist_ok=True)
        with open(os.path.join(theme, "index.theme"), "w") as f:
            f.write(f"[Icon Theme]\nName={theme_name}\nComment=No visible pointer (kiosk)\n")
        for name in NAMES:
            with open(os.path.join(cursors, name), "wb") as f:
                f.write(data)
        print(f"wrote {len(NAMES)} cursors to {cursors}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "~/.icons")
