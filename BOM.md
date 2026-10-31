# Bill of materials

Everything in one Zephyr. Quantities are per radio. Rows marked ⚠️ are not settled yet; see the
notes under the tables.

## Electronics

| Qty | Part | Notes |
|---|---|---|
| 1 | Orange Pi 3B (RK3566), with eMMC | Runs the radio: screen, music, knob. Bolts onto the screen's standoffs. Stock stick WiFi antenna. |
| 1 | Waveshare 3.4" round DSI LCD (C), 800x800, GT9271 touch | Front right. Ø115 plate, 4 x M4 holes at ±37.5 mm. Overlay in `dt/`. |
| 1 | Seeed reSpeaker XVF3800 4-mic array with XIAO ESP32-S3 (presoldered) | The voice half: mics, echo cancellation, wake word. Ø100 PCB, under the top. |
| 1 | MAX98357A I2S amp breakout | Pi I2S1 -> PC83. Powered from the Pi's 5 V. |
| 1 | Dayton Audio PC83-4, 3" full-range driver | The music speaker, in its own sealed printed box. |
| 1 | Mini cavity speaker, 4 Ω 3 W, 27 x 30 x 15 mm with ears, JST-PH 2.0 lead | The voice speaker, on the reSpeaker's own amp. Fires down through the foot panel. |
| 1 | EC11 rotary encoder with push switch, 6 mm D shaft | The knob: volume, play/pause, push-to-talk. On a small perfboard carrier. Overlay in `dt/`. |
| 1 | Perfboard scrap, ~28 x 21 mm | Encoder carrier. |
| 1 | USB-C PD trigger board, fixed 15 V (5 A) | The power inlet, glued behind the opening under the back louvres. |
| 1 | Dual USB-C buck converter, 10-32 V in, 2 x 5 V 3 A (30 W total) | On the foot panel: one port to the Pi, one to the XIAO. |
| 2 | Short USB-C to USB-C cables | Buck -> Pi, buck -> XIAO. |
| 1 | USB-C PD wall charger that offers 15 V, and a USB-C cable | Outside, to the wall. 30 W or more covers both boards with margin. |
| — | Hookup wire, Dupont/JST leads | Pi header -> amp, encoder; amp -> PC83. |

## Hardware

| Qty | Part | Where |
|---|---|---|
| 3 | M2 self-tapping screw | reSpeaker onto its pillars |
| 2 | M2 self-tapping screw | Encoder carrier |
| 2 | M2 x 20 screw + nut | Voice speaker ears, through printed spacer tubes |
| 4 | M3 countersunk screw | Grille + PC83 into the speaker box |
| 7 | M3 countersunk screw | Foot panel up into the floor frame |
| 2 | M3 self-tapping screw | Buck converter onto the foot panel (if used) |
| 4 | M4 self-tapping screw | Screen onto the front panel's ears |
| — | 1 mm foam sheet | Gasket: speaker box to face; ring under the voice speaker |
| 1 | Grommet, 7 mm | Speaker wire out of the sealed box |

## Printed parts

The case is `cad/satellite.py`. Every part prints without supports on a 280 mm bed (the wrap is
269.5 x 135 mm, 132 mm tall).

| Part | Colour | Notes |
|---|---|---|
| wrap | Ivory | Top, ends and bottom in one print; the basket-weave is modelled, no fuzzy skin |
| front_panel | Blue | |
| back | Blue | Louvres, USB-C opening |
| speaker_box | any | Sealed box for the PC83 |
| foot_panel | White, ivory legs | One filament change at 4.0 mm |
| grille | White | Over the PC83 |
| knob | Ivory | Fluted, pressed onto the EC11 shaft |

## Notes

- **Power:** one USB-C cable from a PD wall charger into the trigger board, which asks for 15 V;
  the dual buck makes two separate 5 V feeds from it. A charger without a 15 V profile won't
  work. Plug only the XIAO's USB-C into the reSpeaker: powering it from both ports knocks it out
  of USB mode.
- The voice speaker's ear holes were calipered; the slots in the foot panel allow ±3 mm anyway.
- M2 pilots print nearly closed: run a 1.6 mm drill through them.
