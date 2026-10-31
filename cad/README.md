# CAD

`satellite.py` is the whole case in build123d: shell, front panel, speaker grille, knob, feet.
Its header lists every dimension and which ones are still unverified. Run it with any Python
that has build123d; it writes STEP and print-oriented STLs to `$ZEPHYR_CAD_OUT` (default
`cad/out/`).

The board and screen dimensions in the header were measured from the vendor models below. The
script doesn't need them to run, and they aren't redistributed here; to check a dimension,
download them from the vendors into `cad/ref/`:

| File | What | Source |
|---|---|---|
| `ref/board_xvf3800_xiao.stp` | reSpeaker XVF3800 + XIAO ESP32-S3 board | Seeed Studio wiki, reSpeaker XVF3800 page (3D model) |
| `ref/enclosure_up.stp`, `ref/enclosure_down.stp` | Seeed's case for the same board (mic and LED positions) | same page |
| `ref/respeaker_xvf3800_2d.pdf` | board drawing | same page |
| `ref/screen34/3_4inch-DSI-LCD_C.stp` | Waveshare 3.4" round DSI LCD (C) | Waveshare wiki, 3.4inch DSI LCD (C), "3D drawing" |
| `ref/opi3b_schematic_v2.1.pdf` | Orange Pi 3B v2.1 schematic | orangepi.org, Orange Pi 3B downloads |
