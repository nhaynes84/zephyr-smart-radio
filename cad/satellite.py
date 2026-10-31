"""Voice satellite + terminal — bullet-radio cabinet, Pi inside.

ROUND 8 — the cabinet is a WRAP: one ivory print round the top, both ends
and the bottom, basket-weave relief all over it like grille cloth, rolling
over its front edge onto a blue face. Blue face and back, white grille.

PARTS (each prints without support; orientation in print_orientation())
    wrap            IVORY. Top, ends and bottom, one print, face-down: every
                    wall is vertical. Weave relief 1 mm deep everywhere;
                    over the reSpeaker the top thins to 2 mm and the weave's
                    gaps go THROUGH -- they are the mic and LED openings.
                    The front edge rolls over and laps 2 mm onto the face,
                    plain and smooth like the back edge.
    front_panel     BLUE. Goes in from BEHIND, up against the wrap's lip.
                    Screen rim + ears, PC83 rebate, grille screws, encoder.
    back            BLUE. Glued onto a ledge from outside, set 2 mm in behind
                    the wrap's rolled edge. 45 deg louvres, USB-C in below
                    them.
    speaker_box     the PC83's sealed box, ONE part. Seals on a gasket against
                    the front panel; the four grille screws clamp the lot.
    foot_panel      floor panel with the four legs, screwed up from below.
                    Prints flat, legs up. ★ White panel, ivory legs: ONE
                    filament change at 4.0 mm. The voice speaker bolts
                    through it, behind its own small grille.
    grille          WHITE. Perforated panel over the PC83.
    knob            IVORY. Fluted, D bore for the EC11's 6 mm shaft.

PRINTER: the 280 mm bed. The wrap is 269.5 x 135 footprint, 132 tall.
    (Round 8b: grille 9 mm in, 7 mm of blue outboard of it, body 4 mm
    narrower; screen 2 mm in from the bullet's centre; knob centred.) No
    fuzzy skin: the weave is modelled. M2 pilots print closed-ish: run a
    1.6 mm drill through them afterwards.

ASSEMBLY ORDER
    1. front_panel into the wrap from the back, glued to the lip.
    2. reSpeaker up onto its three pillars under the top (3 x M2).
       Encoder carrier onto its standoffs, knob pressed on.
    3. speaker_box in, wire out through its grommet. PC83 into its rebate
       from the front, grille over it, 4 x M3 through into the box.
    4. Screen + Pi in as one stack through the round opening, onto the ears.
    5. Antenna wedged between the Pi's USB stacks; back glued onto its ledge.
    6. foot_panel from below, voice speaker bolted to it.

LAYOUT
    front, right    3.4" round DSI display on a 2 mm recessed rim, Pi on its
                    back. The opening behind is round and open; the screws
                    land on four ears.
    front, left     PC83 (3" full-range) in its sealed box, behind the grille.
    top             reSpeaker XVF3800, face-up, 3 mm under a 2 mm skin. Its
                    LEDs glow through the weave's open gaps.
    bottom          voice speaker, firing down through the foot panel.
    back            louvres over the electronics bay, USB-C in below them.

AUDIO PATH
    Music: Pi I2S1 -> MAX98357A -> PC83. Voice: XVF3800's own amp -> the
    27 x 30 cavity speaker, so its output is the AEC reference and the
    array can be interrupted.

★ AXIS CONVENTION — WRITTEN DOWN BECAUSE IT COST A BUILD
    `Plane.XZ` has normal (0, -1, 0), so `extrude(+d)` runs into NEGATIVE Y.
    This cabinet uses `extrude(-DEPTH)`: the FRONT PANEL'S FACE IS AT y = 0
    (the wrap's lip sits in front of it, to y = -REC) and "deeper in" is +Y.
        INTO  -> axis +Y        OUTOF -> axis -Y

★ ANOTHER LESSON KEPT: features must stand on material that exists. Seats
    are raised rings; mounts are pillars off real faces.

MEASURED / VERIFIED INPUTS
    reSpeaker  Ø100.0 PCB; THREE M2 holes at (0,-34), (±21.35,+24.5) from
               centre; 12 LEDs on r 40; edge connectors on the underside --
               all read from Seeed's board STEP (ref/board_xvf3800_xiao.stp).
    PC83       frame Ø83, cutout Ø77, depth 30
    display    Ø115 round plate, 17.0 overall, M4 holes at (±37.5,±37.5)
    Pi         ✓ bolts straight onto the screen's standoffs (58 x 49)

⚠️ UNVERIFIED, FLAGGED DELIBERATELY
    - Voice speaker ear holes: read off a product photo, not measured. The
      panel has SLOTS (±3 mm along the face) for that reason. Calipers, then tighten.
    - Power: 15 V PD trigger (no mount holes) GLUED behind the 9.3 x 3.6 opening
      under the louvres -- pocket to come once it is measured. Feeds the
      dual USB-C buck screwed to the foot panel (CONV_*, from the listing).

Output: ~/Collab/CAD/voice-satellite/voice_satellite.step (+ .stl)
        ~/Collab/CAD/voice-satellite/print/<part>.stl  (print-oriented)
"""

import math
from pathlib import Path

from build123d import (
    Align, Axis, Box, BuildPart, BuildSketch, Circle, Color, Compound, Cone,
    Cylinder, Locations, Mode, chamfer, Plane, Polygon, Pos, Rectangle, RectangleRounded,
    Rotation, Sphere, add, export_step, export_stl, extrude, fillet, loft,
)

OUT = Path("/Users/talos/Collab/CAD/voice-satellite")
OUT.mkdir(parents=True, exist_ok=True)

IVORY = Color(0.93, 0.89, 0.80)
BLUE = Color(0.36, 0.66, 0.78)
GREY = Color(0.35, 0.35, 0.37)
WHITE = Color(0.96, 0.95, 0.92)

# ---- cabinet ---------------------------------------------------------------
H, DEPTH, WALL = 135.0, 128.0, 4.0
R_END = H / 2
X_DIAL = 61.0
# The screen sits SCREEN_IN left of the bullet's centre: a slightly wider
# band of blue round its right side than a concentric ring gives.
SCREEN_IN = 2.0
X_SCREEN = X_DIAL - SCREEN_IN
# ★ ROUND 8b: the left end is DERIVED, not set. The grille slides as far in
# as the speaker box allows (see BOX_X1), and the body ends BLUE_EDGE of blue
# face outboard of it, past the wrap's lip. Was 2 mm of blue at -145.
BLUE_EDGE = 7.0
RAKE = 0.0                    # flat cabinet, level array, equal legs

# ---- the wrap ---------------------------------------------------------------
# ★ ROUND 8: the cabinet is a WRAP -- one ivory print round the top, both ends
# and the bottom, like cloth over a box -- with the face and the back as blue
# panels set into it. Printed face-down every wall of the wrap is vertical:
# no supports, no split, no tongue.
# At the front the wrap rolls over its edge and laps OVER mm onto the blue
# panel, so it reads as cloth folded round onto the face. The front panel
# goes in from behind, against that lip; the back panel from outside, onto a
# ledge, set REC in behind the rolled edge to match.
FIL = 8.0                      # the square end's corners
REC = 2.0                      # lip thickness: the face sits this far in
OVER = 2.0                     # lip's lap onto the front panel
ROLL = 2.0                     # radius the wrap rolls over at front and back
FACE_CLR = 0.2

# ---- basket weave, relief in the wrap ----------------------------------------
# Strands run round the wrap in offset rows, like grille cloth: grooves
# between rows, gaps between strand ends. 1 mm deep everywhere -- except over
# the reSpeaker, where the gaps go THROUGH a top thinned to SKIN: they are
# the mic and LED openings, and from outside you cannot tell which.
TILE, GAP = 4.5, 1.5           # strand length, gap at its ends (round the wrap)
ROW, GROOVE = 2.2, 1.0         # strand width, groove between rows (along Y)
W_DEPTH = 1.0
DISC_R = 48.0                  # through-zone over the board

# ---- back (separate, glued) -------------------------------------------------
BACK_T = 3.0
BACK_LEDGE_W, BACK_LEDGE_T = 2.5, 2.0
BACK_CLR = 0.2
Y_BACK = DEPTH - BACK_T                       # back panel's inner face
Y_LEDGE = Y_BACK - BACK_LEDGE_T               # ledge's inner face
# ★ Across the floor opening the FOOT PANEL carries the rim: it runs out to
# DEPTH + REC with the same roll, so the back has one rim all round (owner,
# round 8). The back's bottom edge drops a TAB into a rabbet in the panel's
# inner face: the panel goes on last and locks the back in.
TAB_DROP = 1.6                                # tab below the back's edge
RAB_D, RAB_CLR = 1.5, 0.2                     # rabbet depth, clearance

# ---- display ---------------------------------------------------------------
# Every number here is off WAVESHARE'S DRAWING (their STEP put a connector in
# the bbox). Ø115 round plate, 17.0 overall, four M4 holes at (±37.5, ±37.5).
SCREEN_MOD, SCREEN_T = 115.0, 17.0
SCREEN_REG = 2.0              # ★ the plate sinks 2 mm into the face
SCREEN_REG_D = SCREEN_MOD + 0.6
SCREEN_HOLE_D = SCREEN_MOD - 4.0    # -> a 2 mm rim all round for the plate
SCREEN_PCD = 75.0                   # mounts at (±37.5, ±37.5), diagonals
SCREEN_PILOT = 3.4                  # M4 self-tap
SCREEN_PCB_W, SCREEN_PCB_H = 85.0, 65.0
# ★ EARS, not pads. The screw is 7.1 mm from the PCB's corner, so a round ear
# of r 4.5 round the screw clears it by 2.5, and the rest of the opening is
# left OPEN -- the old rectangular cut-out with square pads is what the
# boards were hitting.
EAR_R, EAR_DEPTH = 4.5, 8.0         # ear stands 8 mm into the cabinet

# ---- PC83 + grille ---------------------------------------------------------
GR_W, GR_H, GR_R = 94.0, 94.0, 14.0
GR_T, GR_REBATE = 3.0, 1.8
GR_PCD_X, GR_PCD_Z = 80.0, 80.0         # four corner screws -> into the box
GR_HOLE_D, GR_PITCH = 4.0, 6.6          # hex perforation
GR_FIELD = 80.0                         # perforated: the dome, clear of its rim
# ★ BUBBLE GRILLE (owner, round 8): the PC83's surround stands ~2 mm proud of
# its flange, and the flat grille sat level with the flange -- no room for the
# cone at all. So the WHOLE face is one shallow spherical cap: it rises
# DOME_H at the centre and runs out to nothing at the square's corners (no
# rim, no flat border -- owner), leaving ~2 mm of edge at the side middles.
# Behind it, a 2 mm shell over a Ø77 pocket that clears the surround by
# >= SURROUND_H + 1.5. The back still clamps the flange ring as before.
SURROUND_H = 2.0
DOME_R = ((GR_W - 0.4) / 2 - GR_R) * math.sqrt(2) + GR_R   # the corners
DOME_H, DOME_EDGE = 5.2, 0.0                 # rise at centre / at the corners
DOME_SHELL = 2.0
DRIVER_OPEN = 84.0                      # PC83 frame Ø83 drops in from the front
DRIVER_LIP = 77.0                       # Dayton's cutout; do not widen
# ★ The grille CLAMPS the PC83's flange onto the lip, over a ring of 1 mm
# closed-cell foam (seals the box). Flange measured 1.0 mm (owner). The
# pocket under the grille's rebate is only 1.0 deep, so the grille's back is
# relieved to make up flange + foam squashed to half.
FLANGE_T, FOAM_SQ = 1.0, 0.5
DRIVER_POCKET = WALL - 1.2 - GR_REBATE        # 1.0 below the rebate floor
GR_RELIEF = FLANGE_T + FOAM_SQ - DRIVER_POCKET
SCREW_CLR = 3.4                         # M3 clearance
PLATE_PILOT = 2.5                       # M3 self-tap

# ---- speaker box: ONE part, sealed, clamped by the grille screws -------------
# Open at the front only: it seals against the cabinet's front wall on a foam
# gasket, and the front wall IS its baffle. The front plate's inside is a
# loft from the Ø80 throat to the full box section, every face of it under
# 45 degrees, so the box prints back-down with no support -- and support
# inside a sealed box could never come out.
BOX_T = 3.0
BOX_GASKET = 1.0
BOX_Y0 = WALL + BOX_GASKET
BOX_Y1 = Y_LEDGE - 0.5
BOX_THROAT_D = 80.0
BOX_PLATE = 3.0
BOX_LOFT = 40.0
BOX_PILOT_DEPTH = 12.0
WIRE_D = 7.0                            # grommet, box -> electronics bay

# ---- foot panel -------------------------------------------------------------
# The floor opening runs out through the BACK edge. Printed face-down a
# closed opening would leave a 190 mm bridge across its top; open-ended, the
# back panel closes it instead.
PANEL_Y0 = 10.0
PANEL_CLR = 0.2
FRAME_W, FRAME_H = 5.0, 5.0             # ledge ring the panel screws up into
BOX_Z0 = -H / 2 + WALL + FRAME_H + 0.5


# ---- reSpeaker on the top deck ---------------------------------------------
# ⚠️ ROUND 5 HAD THIS WRONG. Its three pillars at r = 45.07, 120 deg apart,
# were the SHELL screws of Seeed's enclosure_down -- the bosses that hold
# their two halves together -- not the board's mounts. The board's own holes
# are M2, at (0,-34) and (±21.35,+24.5) from its centre: not equal radii,
# not 120 deg. Read off the board STEP this time.
BOARD_D = 100.0
BOARD_PCB_T = 1.1
# Y 66: centred in the depth between the front panel and the back.
BOARD_X, BOARD_Y = 9.0, 66.0
# ★ Rotated so the XIAO's USB-C faces +X, into the bullet end. That is the
# only side with room for a plug: ~30 mm to the curve at that height. Facing
# the back it would hit the back panel, facing the front the screen.
BOARD_ROT = -90.0
BOARD_HOLES = [(0.0, -34.0), (21.35, 24.5), (-21.35, 24.5)]
BOARD_MICS = [(33.0, 33.0), (-33.0, 33.0), (33.0, -33.0), (-33.0, -33.0)]
# ★ ROUND 8: almost flush, as Seeed intends. The top is thinned to SKIN over
# the board and the PCB hangs BOARD_HANG under that, on three short pillars.
# Its edge connectors are on the underside, so nothing needs room above it.
SKIN = 2.0
# Round 8c: 4 mm (was 3). At 3 a part on the board's top face just kissed the
# skin, and the skin slapped it at ~150-210 Hz -- a buzz in voices (2026-10-20).
BOARD_HANG = 4.0                        # thinned skin -> PCB top face
POCKET_R = BOARD_D / 2 + 1.0
BOSS_D, BOSS_PILOT = 5.0, 1.7           # M2 self-tap
# ★ The board does NOT move: at BOARD_X 9 the XIAO's right-angle USB-C plug
# already ends at the bullet's inner wall (x 79 at that height).
BOARD_PARTS_R = BOARD_D / 2 - 6         # underside parts, inside r 44 ...
# ⚠️ ... EXCEPT these two, on the edge opposite the XIAO, right over the
# speaker box (round 8 print: the owner had to trim the box for the jack).
# Board frame (lx0, lx1, ly0, ly1, depth under the PCB), off the board STEP.
BOARD_UNDER_EDGE = [
    (10.3, 20.7, -50.8, -35.2, 5.4),    # 3.5 mm audio jack
    (-4.5, 4.5, -52.6, -45.6, 3.1),     # the board's own USB-C
]
UNDER_CLR = 1.0

# ---- speaker box: where it may go, and so where the grille and body end ----
# The box's right wall runs up to the board's underside parts (1 mm clear),
# and its top drops under the PCB's edge (1 mm clear) so it can pass beneath.
BOX_X1 = BOARD_X - BOARD_PARTS_R - 1.0
BOX_Z1 = H / 2 - SKIN - BOARD_HANG - BOARD_PCB_T - 1.0
# Throat edge 2 mm inside the box's inner wall (was 3).
X_GRILLE = BOX_X1 - BOX_T - 2.0 - BOX_THROAT_D / 2
X_LEFT = X_GRILLE - GR_W / 2 - BLUE_EDGE - (WALL + OVER)
BOX_X0 = X_LEFT + WALL + 0.5

# ---- foot panel, follows the left end ---------------------------------------
PANEL_X0, PANEL_X1 = X_LEFT + 14.0, 59.0  # inside the flat of the underside
PANEL_SCREWS = [(X_LEFT + 35.0, 12.5), (-40.0, 12.5), (30.0, 12.5),
                (PANEL_X0 + 2.5, 60.0), (PANEL_X0 + 2.5, 115.0),
                (PANEL_X1 - 2.5, 60.0), (PANEL_X1 - 2.5, 115.0)]

# ---- electronics bay ---------------------------------------------------------
PI_W, PI_D = 85.0, 56.0
PI_BEHIND_PLATE = 12.1
PI_PCB_T = 1.6
PI_TALLEST = 16.0

# ---- back: vents, power, antenna ---------------------------------------------
# ★ ROUND 7: LOUVRES, not the hex field. Horizontal slots cut at 45 deg
# through a back thickened to 6 mm behind them, so at 45 deg the blades
# overlap and you cannot see in. The field is a rounded rectangle, centred
# over the electronics bay. Every slot rises inwards -- slants down to the
# outside -- like a real louvre.
VENT_X = 30.0
LV_W, LV_H, LV_R = 92.0, 62.0, 16.0     # field, on the outer face
LV_PITCH, LV_OPEN = 6.0, 3.0
LV_BOSS = 3.0                           # inner thickening -> 6 mm total
# ★ USB-C power in, centred UNDER the louvres: the cable drops straight off
# the back, not out of the side.
# ★ Sized to the USB-C RECEPTACLE (8.94 x 3.26 shell) + clearance, not a
# panel-socket housing: the 15 V trigger is glued behind with its socket
# pushed through, flush with the outside, so the plug seats fully.
PWR_X, PWR_Z, PWR_W, PWR_H = VENT_X, -48.0, 9.3, 3.6
PWR_R = 1.75

# ---- EC11 encoder -----------------------------------------------------------
ENC_BUSH_D = 8.4
# Centred in the blue between the grille's edge and the screen's recess.
ENC_X = ((X_GRILLE + GR_W / 2) + (X_SCREEN - SCREEN_REG_D / 2)) / 2
ENC_Z = -46.0
# ★ From the EC11 DATASHEET (owner, round 8): smooth bushing, NO thread, so
# no nut -- it rides on a perfboard carrier. Body 4.5 above the board; the
# bushing is Ø8.8 for 5.5 then Ø8.0 to 10.0 above the body; shaft tip 20.0
# above the body. The Ø8.4 hole passes the Ø8.0 and STOPS the Ø8.8 shoulder
# on the panel's back face: that sets the depth. The bushing ends 0.5 proud
# of the face, the shaft 10.5.
ENC_BODY_H, ENC_SHOULDER, ENC_BUSH_TOP, ENC_SHAFT_TIP = 4.5, 5.5, 10.0, 20.0
ENC_BOARD_Y = WALL + ENC_SHOULDER + ENC_BODY_H     # board's front face
ENC_BOARD_T = 1.6
# Pads on the shaft's centreline, 4 perfboard pitches either side: the A/Com/B
# row is 7.5 below the shaft (~3 pitches, 0.12 off), so the holes land on the
# grid near enough -- drill them out to Ø2.2 for M2.
ENC_PAD_DX, ENC_PAD_D, ENC_PAD_PILOT = 4 * 2.54, 5.0, 1.7
ENC_BOARD_W, ENC_BOARD_UP, ENC_BOARD_DN = 28.0, 11.0, 9.5   # max carrier extent
KNOB_D, KNOB_H = 22.0, 14.0
KNOB_GAP = 1.0                          # off the face
# EC11 D-shaft: Ø6, flat to 4.5. Pressed on, so only a whisker of clearance.
SHAFT_D, SHAFT_FLAT, BORE_CLR = 6.0, 4.5, 0.1
BORE_DEPTH = 10.0
KNOB_FLUTES, FLUTE_R = 24, 1.1

# ---- voice speaker: 27 x 30 x 15 cavity unit, bolted to the foot panel -------
VS_W, VS_D, VS_H = 27.0, 30.0, 15.0
VS_X, VS_Y = 30.0, 45.0
VS_GRILLE_D, VS_HOLE_D, VS_PITCH = 21.0, 2.0, 3.2
# ★ Ears CALIPERED (owner): Ø2.2 holes, 36 c-c, ear 9 mm back from the
# speaker's face. The face sits on the panel over a ring of 1 mm foam
# (squashed to 0.5), so the ears stand 9.5 off the panel on two printed
# spacer tubes, M2 x 20 up through panel + spacer + ear, nut on top. Holes on
# a line through the centre: if the ears are offset along their faces, the
# body just turns a few degrees.
VS_EAR_CC, VS_EAR_D = 36.0, 2.4
VS_EARS = [(VS_EAR_CC / 2, 0.0), (-VS_EAR_CC / 2, 0.0)]
VS_FOAM_SQ = 0.5
VS_SPACER_H = 9.0 + VS_FOAM_SQ
VS_SPACER_OD = 5.0

# ★ The speaker box HANGS off the front panel on its four grille screws: it
# clears the floor frame by 0.5 by design. ~0.5 kg cantilevered on self-tapped
# PLA under vibration creeps loose (owner). Two risers glued to the foot
# panel, topped with the 1 mm closed-cell foam, push up under the box when
# the panel goes on: the floor carries the weight, the screws only clamp.
PAD_W, PAD_D = 20.0, 50.0
PAD_FOAM, PAD_SQ = 1.0, 0.4                   # foam on top; how much it squashes
PAD_YS = (45.0, 97.0)          # clear of the front rail (y 15) and the back (y 125)

# ---- power: 15 V PD trigger at the back -> dual USB-C buck on the floor -------
# YIPIN HEXHA DC 10-32V -> 5V 6A, two USB-C leads (Pi, XIAO). Body 42 x 44 x
# 20 off the listing's drawing; ears on the 42 sides, holes ~48 apart
# (scaled off that drawing -- one ear is an open SLOT, which takes up the
# error). Screws down through the ears into pilots in the foot panel, so the
# panel still prints inner face down with nothing standing on it.
CONV_W, CONV_D, CONV_H = 42.0, 44.0, 20.0
CONV_X, CONV_Y = -5.0, 92.0             # behind the knob, clear of box and Pi
CONV_EAR_PITCH = 48.0

# ---- mid-century legs ------------------------------------------------------
LEG_VISIBLE = 30.0
LEG_R_TOP, LEG_R_BOT = 8.5, 5.0
LEG_SPLAY = 11.0
CAB_CX = (X_LEFT + X_DIAL + R_END) / 2
LEG_FLOOR = -96.0
# ★ The cone runs right THROUGH the panel and is clipped at its inner face.
# A tilted cone's end disc spans ±2.3 mm in z (and the tilt shortens it), so
# the old "embed 1.5" left a crescent of the disc hanging below the panel's
# outer face at every root -- a printed overhang (owner, round 8).
LEG_EMBED = WALL + 4.0
# ⚠️ Right pair at x=50, was 58: they now root in the panel, and a Ø17 leg
# top at 58 hung off its edge.
LEG_POS = [(X_LEFT + 28.0, 22.0), (50.0, 22.0),
           (X_LEFT + 28.0, 106.0), (50.0, 106.0)]

INTO, OUTOF = (-90, 0, 0), (90, 0, 0)


def cabinet_sketch(shrink=0.0):
    """Fada silhouette: rectangle + full semicircular right end."""
    with Locations((((X_LEFT + shrink) + X_DIAL) / 2, 0)):
        Rectangle(X_DIAL - X_LEFT - shrink, H - shrink * 2)
    with Locations((X_DIAL, 0)):
        Circle(R_END - shrink)


def prism(shrink, y0, y1):
    """The cabinet silhouette, shrunk, as a solid from y0 to y1."""
    # ⚠️ PRIVATE: a BuildPart opened inside another one ADDS its result to
    # the outer part on exit. Without this the ledge's cut-out prism filled
    # the whole cabinet.
    with BuildPart(mode=Mode.PRIVATE) as p:
        with BuildSketch(Plane.XZ.offset(-y0)):
            cabinet_sketch(shrink)
        extrude(amount=-(y1 - y0))
    return p.part


def slab(z0, z1):
    return Pos(0, DEPTH / 2, (z0 + z1) / 2) * Box(600, DEPTH + 40, z1 - z0,
                                                  mode=Mode.PRIVATE)


def board_xy(lx, ly):
    """reSpeaker board coordinates (Seeed's, mics up) -> cabinet X, Y."""
    a = math.radians(BOARD_ROT)
    return (BOARD_X + lx * math.cos(a) - ly * math.sin(a),
            BOARD_Y + lx * math.sin(a) + ly * math.cos(a))


def board_under_edge(grow=0.0, clr=0.0):
    """Boxes for BOARD_UNDER_EDGE in the cabinet, grown by clr + grow all round
    (but not above the PCB's underside)."""
    z_under = H / 2 - SKIN - BOARD_HANG - BOARD_PCB_T
    out = []
    for lx0, lx1, ly0, ly1, depth in BOARD_UNDER_EDGE:
        pts = [board_xy(x, y) for x in (lx0, lx1) for y in (ly0, ly1)]
        g = clr + grow
        x0, x1 = min(q[0] for q in pts) - g, max(q[0] for q in pts) + g
        y0, y1 = min(q[1] for q in pts) - g, max(q[1] for q in pts) + g
        z0, z1 = z_under - depth - g, z_under + (1.0 if clr else 0.0)
        out.append(Pos((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2)
                   * Box(x1 - x0, y1 - y0, z1 - z0, mode=Mode.PRIVATE))
    return out


MIN = (Align.CENTER, Align.CENTER, Align.MIN)


def cyl(r, z0, z1, x=None, y=None):
    """Vertical cylinder from z0 to z1, on the board's centre by default."""
    x = BOARD_X if x is None else x
    y = BOARD_Y if y is None else y
    return Pos(x, y, z0) * Cylinder(r, z1 - z0, align=MIN, mode=Mode.PRIVATE)


def prism_f(shrink, y0, y1, roll=0.0):
    """prism() with the square end's corners rounded concentric with the
    wrap's, and optionally its two end edges rolled over."""
    with BuildPart(mode=Mode.PRIVATE) as p:
        with BuildSketch(Plane.XZ.offset(-y0)):
            cabinet_sketch(shrink)
        extrude(amount=-(y1 - y0))
        corners = [e for e in p.part.edges().filter_by(Axis.Y)
                   if e.center().X < X_LEFT + shrink + 1]
        p.part = fillet(corners, FIL - shrink)
        if roll:
            ends = [e for e in p.part.edges()
                    if abs(e.center().Y - y0) < 0.01 or abs(e.center().Y - y1) < 0.01]
            p.part = fillet(ends, roll)
    return p.part


def wrap_path(d):
    """The wrap's profile at inset d: up the square end from its bottom
    corner, over the top, down round the bullet. [(kind, data, length)]"""
    cxl, ztl, zbl = X_LEFT + FIL, H / 2 - FIL, -H / 2 + FIL
    segs = [("arc", (cxl, zbl, FIL - d, -90.0, -180.0)),
            ("line", ((X_LEFT + d, zbl), (X_LEFT + d, ztl), 180.0)),
            ("arc", (cxl, ztl, FIL - d, 180.0, 90.0)),
            ("line", ((cxl, H / 2 - d), (X_DIAL, H / 2 - d), 90.0)),
            ("arc", (X_DIAL, 0.0, R_END - d, 90.0, -90.0))]
    out = []
    for kind, data in segs:
        if kind == "arc":
            n = math.radians(abs(data[4] - data[3])) * data[2]
        else:
            (ax, az), (bx, bz), _ = data
            n = math.hypot(bx - ax, bz - az)
        out.append((kind, data, n))
    return out


def wrap_at(path, sv):
    """-> (x, z, normal_deg, on_top) at arc length sv along the path."""
    for kind, data, n in path:
        if sv <= n:
            if kind == "line":
                (ax, az), (bx, bz), nd = data
                t = sv / n
                return ax + (bx - ax) * t, az + (bz - az) * t, nd, nd == 90.0
            cx, cz, r, a0, a1 = data
            a = a0 + (a1 - a0) * sv / n
            return (cx + r * math.cos(math.radians(a)),
                    cz + r * math.sin(math.radians(a)), a, False)
        sv -= n
    return None


def weave_cuts():
    """Everything the weave removes from the wrap, as one compound."""
    path = wrap_path(0.0)
    total = sum(n for *_, n in path)
    pitch, rpitch = TILE + GAP, ROW + GROOVE
    y0, y1 = -REC + ROLL + 0.5, DEPTH + REC - ROLL - 0.5
    rows = int((y1 - y0 + GROOVE) / rpitch)
    ys = y0 + ((y1 - y0) - (rows * rpitch - GROOVE)) / 2      # centred
    cuts = []
    for r in range(rows):
        yc = ys + r * rpitch + ROW / 2
        sv = TILE + GAP / 2 + (r % 2) * pitch / 2
        while sv < total:
            x, z, nd, top = wrap_at(path, sv)
            thru = top and math.hypot(x - BOARD_X, yc - BOARD_Y) <= DISC_R
            dn = SKIN + 1 if thru else W_DEPTH
            nx, nz = math.cos(math.radians(nd)), math.sin(math.radians(nd))
            cuts.append(Pos(x + nx * (1 - dn) / 2, yc, z + nz * (1 - dn) / 2)
                        * Rotation(0, 90 - nd, 0)
                        * Box(GAP, ROW + 0.1, dn + 1, mode=Mode.PRIVATE))
            sv += pitch
        if r:                                       # groove before this row
            g0 = yc - ROW / 2 - GROOVE
            cuts.append(prism_f(0, g0, g0 + GROOVE)
                        - prism_f(W_DEPTH, g0 - 1, g0 + GROOVE + 1))
    # ★ The lip stays PLAIN: smooth roll-over, like the back edge. Strand
    # slots on it read as notches, not cloth (owner, round 8).
    # never the underside
    return Compound(children=cuts) & slab(-H / 2 + W_DEPTH + 0.01, H)


def floor_opening(up=0.0):
    """The foot panel's hole in the floor; up = how far to carry it above the wall."""
    return Pos((PANEL_X0 + PANEL_X1) / 2, (PANEL_Y0 + DEPTH + 2) / 2,
               -H / 2 + (WALL + up) / 2) * Box(PANEL_X1 - PANEL_X0,
                                               DEPTH + 2 - PANEL_Y0, WALL + up + 0.02,
                                               mode=Mode.PRIVATE)


def wrap_part():
    """Ivory: top, both ends and the bottom in one print, weave all round."""
    with BuildPart() as p:
        p.part = prism_f(0, -REC, DEPTH + REC, roll=ROLL)
        p.part = p.part - prism_f(WALL, 0, DEPTH + REC + 1)       # hollow
        p.part = p.part - prism_f(WALL + OVER, -REC - 1, 0.01)    # the lip

        # Ledge the back panel lands on (not across the floor opening --
        # that edge sits on the foot panel instead).
        # ⚠️ The cut must reach ABOVE the wall: the ledge stands on it, so a
        # wall-deep cut left a 2.5 x 2 mm bar spanning the whole opening. Printed,
        # it rang like a string (~150 / 210 Hz) against the back -- the "fuzz" in
        # voices (round 8 print, found by sweep 2026-10-20).
        ledge = (prism_f(WALL - 0.01, Y_LEDGE, Y_BACK)
                 - prism_f(WALL + BACK_LEDGE_W, Y_LEDGE - 1, Y_BACK + 1)
                 - floor_opening(up=BACK_LEDGE_W + 1))
        p.part = p.part + ledge

        # --- reSpeaker: top thinned over it, three short pillars ----------
        z_skin = H / 2 - SKIN
        p.part = p.part - cyl(POCKET_R, H / 2 - WALL - 1, z_skin)
        for h in BOARD_HOLES:
            p.part = p.part + cyl(BOSS_D / 2, z_skin - BOARD_HANG, z_skin + 0.01, *board_xy(*h))
            p.part = p.part - cyl(BOSS_PILOT / 2, z_skin - BOARD_HANG - 1, z_skin - 0.6,
                                  *board_xy(*h))

        # --- floor: opening for the foot panel + the frame it screws into ---
        p.part = p.part - floor_opening()
        zf = -H / 2 + WALL
        fy1 = Y_LEDGE
        frame = [
            ((PANEL_X0 - 2 + PANEL_X1 + 2) / 2, (PANEL_Y0 - 2 + PANEL_Y0 + FRAME_W) / 2,
             PANEL_X1 - PANEL_X0 + 4, FRAME_W + 2),
            (PANEL_X0 - 2 + (FRAME_W + 2) / 2, (PANEL_Y0 - 2 + fy1) / 2,
             FRAME_W + 2, fy1 - PANEL_Y0 + 2),
            (PANEL_X1 + 2 - (FRAME_W + 2) / 2, (PANEL_Y0 - 2 + fy1) / 2,
             FRAME_W + 2, fy1 - PANEL_Y0 + 2),
        ]
        for cx, cy, w, d in frame:
            with Locations((cx, cy, zf - 0.01)):
                Box(w, d, FRAME_H, align=(Align.CENTER, Align.CENTER, Align.MIN))
        with Locations(*[(x, y, zf - 0.1) for x, y in PANEL_SCREWS]):
            Cylinder(PLATE_PILOT / 2, FRAME_H - 1.0,
                     align=(Align.CENTER, Align.CENTER, Align.MIN),
                     mode=Mode.SUBTRACT)
    print("  weave ...")
    return p.part - weave_cuts()


def front_panel_part():
    """Blue face, in behind the wrap's lip. Screen, grille, encoder."""
    with BuildPart() as p:
        p.part = prism_f(WALL + FACE_CLR, 0, WALL)
        # --- display: 2 mm recessed rim, round opening, four ears ----------
        with Locations((X_SCREEN, -0.5, 0)):
            Cylinder(SCREEN_REG_D / 2, SCREEN_REG + 0.5, rotation=INTO,
                     align=(Align.CENTER, Align.CENTER, Align.MIN),
                     mode=Mode.SUBTRACT)
        with Locations((X_SCREEN, -1, 0)):
            Cylinder(SCREEN_HOLE_D / 2, WALL + 2, rotation=INTO,
                     align=(Align.CENTER, Align.CENTER, Align.MIN),
                     mode=Mode.SUBTRACT)
        for sx in (-1, 1):
            for sz in (-1, 1):
                sx_, sz_ = X_SCREEN + sx * SCREEN_PCD / 2, sz * SCREEN_PCD / 2
                ang = math.degrees(math.atan2(sz, sx))
                with Locations((sx_, SCREEN_REG, sz_)):
                    Cylinder(EAR_R, EAR_DEPTH, rotation=INTO,
                             align=(Align.CENTER, Align.CENTER, Align.MIN))
                # bar from the ear out to the rim, along the diagonal
                mid = SCREEN_PCD / 2 * math.sqrt(2) + 3.0
                with Locations((X_SCREEN + mid * math.cos(math.radians(ang)),
                                SCREEN_REG + EAR_DEPTH / 2,
                                mid * math.sin(math.radians(ang)))):
                    Box(6.0, EAR_DEPTH, EAR_R * 2, rotation=(0, -ang, 0))
                with Locations((sx_, SCREEN_REG - 0.1, sz_)):
                    Cylinder(SCREEN_PILOT / 2, EAR_DEPTH + 0.2, rotation=INTO,
                             align=(Align.CENTER, Align.CENTER, Align.MIN),
                             mode=Mode.SUBTRACT)

        # --- PC83: rebate + cone opening; the box is its baffle ------------
        with Locations((X_GRILLE, -1, 0)):
            Cylinder(DRIVER_OPEN / 2, WALL + 1 - 1.2, rotation=INTO,
                     align=(Align.CENTER, Align.CENTER, Align.MIN),
                     mode=Mode.SUBTRACT)
        with Locations((X_GRILLE, -1, 0)):
            Cylinder(DRIVER_LIP / 2, WALL + 4, rotation=INTO,
                     align=(Align.CENTER, Align.CENTER, Align.MIN),
                     mode=Mode.SUBTRACT)
        with BuildSketch(Plane.XZ.offset(-GR_REBATE)):
            with Locations((X_GRILLE, 0)):
                RectangleRounded(GR_W, GR_H, GR_R)
        extrude(amount=GR_REBATE, mode=Mode.SUBTRACT)
        # Grille screws pass straight through into the box behind.
        for sx in (-1, 1):
            for sz in (-1, 1):
                with Locations((X_GRILLE + sx * GR_PCD_X / 2, -1,
                                sz * GR_PCD_Z / 2)):
                    Cylinder(SCREW_CLR / 2, WALL + 2, rotation=INTO,
                             align=(Align.CENTER, Align.CENTER, Align.MIN),
                             mode=Mode.SUBTRACT)

        # --- encoder ----------------------------------------------------------
        with Locations((ENC_X, -1, ENC_Z)):
            Cylinder(ENC_BUSH_D / 2, WALL + 2, rotation=INTO,
                     align=(Align.CENTER, Align.CENTER, Align.MIN),
                     mode=Mode.SUBTRACT)
        pads = [(ENC_X - ENC_PAD_DX, WALL, ENC_Z),
                (ENC_X + ENC_PAD_DX, WALL, ENC_Z)]
        with Locations(*pads):
            Cylinder(ENC_PAD_D / 2, ENC_BOARD_Y - WALL, rotation=INTO,
                     align=(Align.CENTER, Align.CENTER, Align.MIN))
        with Locations(*pads):
            Cylinder(ENC_PAD_PILOT / 2, ENC_BOARD_Y - WALL + 1, rotation=INTO,
                     align=(Align.CENTER, Align.CENTER, Align.MIN),
                     mode=Mode.SUBTRACT)

    return p.part


def back_part():
    """Blue back, glued onto its ledge. Outer face prints on the bed."""
    with BuildPart() as p:
        p.part = prism_f(WALL + BACK_CLR, Y_BACK, DEPTH)

        # Louvre boss on the inside: 6 mm of back behind the field.
        with BuildSketch(Plane.XZ.offset(-(Y_BACK - LV_BOSS))):
            with Locations((VENT_X, 0)):
                RectangleRounded(LV_W + 6, LV_H + 14, LV_R + 3)
        extrude(amount=-(LV_BOSS + 0.01))

        # Louvres. Each slot is a parallelogram in Y-Z, run along X; its
        # length follows the field's rounded corners at that height.
        def half_len(z):
            flat = LV_H / 2 - LV_R
            if abs(z) <= flat:
                return LV_W / 2
            dz = abs(z) - flat
            return LV_W / 2 - LV_R + math.sqrt(max(LV_R ** 2 - dz ** 2, 0.0))

        y_out, y_in = DEPTH + 1.0, Y_BACK - LV_BOSS - 1.0
        run = y_out - y_in
        rows = []
        for k in range(6):
            z = 2.0 + k * LV_PITCH                  # bottom edge, outer face
            if z + LV_OPEN <= LV_H / 2:
                # ★ All rise inwards (slant DOWN to the outside), like a
                # real louvre -- the round-7 chevron is gone (owner).
                rows.append((z, +1))
                rows.append((-z - LV_OPEN, +1))
        for z0, s in rows:
            hl = half_len(z0 + LV_OPEN / 2) - 1.5
            # outer face is y = DEPTH; the slot shifts 1 mm in z per mm in
            zo = z0 - s * (y_out - DEPTH)
            zi = zo + s * run
            with BuildSketch(Plane.YZ.offset(VENT_X - hl)):
                Polygon((y_out, zo), (y_out, zo + LV_OPEN),
                        (y_in, zi + LV_OPEN), (y_in, zi), align=None)
            extrude(amount=2 * hl, mode=Mode.SUBTRACT)

        with BuildSketch(Plane.XZ.offset(-(Y_BACK - 1))):        # power in
            with Locations((PWR_X, PWR_Z)):
                RectangleRounded(PWR_W, PWR_H, PWR_R)
        extrude(amount=-(BACK_T + 2), mode=Mode.SUBTRACT)

        # Tab down into the foot panel's rabbet, across the floor opening.
        z_edge = -H / 2 + WALL + BACK_CLR
        with Locations(((PANEL_X0 + PANEL_X1) / 2, (Y_BACK + DEPTH) / 2,
                        z_edge + 0.01)):
            Box(PANEL_X1 - PANEL_X0 - 1.0, BACK_T, TAB_DROP + 0.01,
                align=(Align.CENTER, Align.CENTER, Align.MAX))
        # (No antenna clip: the Pi's stock stick antenna wedges between its
        # two USB stacks and points straight back -- owner, round 8.)
    return p.part


def speaker_box_part():
    """The PC83's sealed box. Open front, sealed by its gasket on the face."""
    w_in_x0, w_in_x1 = BOX_X0 + BOX_T, BOX_X1 - BOX_T
    w_in_z0, w_in_z1 = BOX_Z0 + BOX_T, BOX_Z1 - BOX_T
    y_loft0 = BOX_Y0 + BOX_PLATE
    y_loft1 = y_loft0 + BOX_LOFT
    y_back = BOX_Y1 - BOX_T
    with BuildPart() as p:
        with Locations(((BOX_X0 + BOX_X1) / 2, (BOX_Y0 + BOX_Y1) / 2,
                        (BOX_Z0 + BOX_Z1) / 2)):
            Box(BOX_X1 - BOX_X0, BOX_Y1 - BOX_Y0, BOX_Z1 - BOX_Z0)
        with Locations((X_GRILLE, BOX_Y0 - 0.1, 0)):          # throat
            Cylinder(BOX_THROAT_D / 2, BOX_PLATE + 0.2, rotation=INTO,
                     align=(Align.CENTER, Align.CENTER, Align.MIN),
                     mode=Mode.SUBTRACT)
        # ⚠️ Circle -> Rectangle lofts TWIST: OCC pairs up the sections'
        # vertices however it likes and half the throat came out as a fan.
        # Both ends are polygons with the SAME vertex count, matched ray by
        # ray from the driver axis, and the loft is ruled.
        corners = [(w_in_x1, w_in_z1), (w_in_x0, w_in_z1),
                   (w_in_x0, w_in_z0), (w_in_x1, w_in_z0)]
        angs = sorted(math.atan2(cz, cx - X_GRILLE) % (2 * math.pi)
                      for cx, cz in corners)
        rays = []
        for i, a0 in enumerate(angs):
            a1 = angs[(i + 1) % 4] + (2 * math.pi if i == 3 else 0)
            rays += [a0 + (a1 - a0) * k / 4 for k in range(4)]
        def on_rect(a):
            dx, dz = math.cos(a), math.sin(a)
            t = min(((w_in_x1 - X_GRILLE) / dx if dx > 1e-9 else
                     (w_in_x0 - X_GRILLE) / dx if dx < -1e-9 else 1e9),
                    (w_in_z1 / dz if dz > 1e-9 else
                     w_in_z0 / dz if dz < -1e-9 else 1e9))
            return (X_GRILLE + t * dx, t * dz)
        throat = [(X_GRILLE + BOX_THROAT_D / 2 * math.cos(a),
                   BOX_THROAT_D / 2 * math.sin(a)) for a in rays]
        mouth = [on_rect(a) for a in rays]
        with BuildSketch(Plane.XZ.offset(-y_loft0)):
            Polygon(*throat, align=None)
        with BuildSketch(Plane.XZ.offset(-y_loft1)):
            Polygon(*mouth, align=None)
        loft(ruled=True, mode=Mode.SUBTRACT)
        with Locations(((w_in_x0 + w_in_x1) / 2, (y_loft1 - 0.01 + y_back) / 2,
                        (w_in_z0 + w_in_z1) / 2)):
            Box(w_in_x1 - w_in_x0, y_back - y_loft1 + 0.01, w_in_z1 - w_in_z0,
                mode=Mode.SUBTRACT)
        # Blind pilots for the grille screws.
        for sx in (-1, 1):
            for sz in (-1, 1):
                with Locations((X_GRILLE + sx * GR_PCD_X / 2, BOX_Y0 - 0.1,
                                sz * GR_PCD_Z / 2)):
                    Cylinder(PLATE_PILOT / 2, BOX_PILOT_DEPTH, rotation=INTO,
                             align=(Align.CENTER, Align.CENTER, Align.MIN),
                             mode=Mode.SUBTRACT)
        # Wire out into the bay, low on the side facing it. Grommet it.
        with Locations((BOX_X1, (y_loft1 + y_back) / 2, -40.0)):
            Cylinder(WIRE_D / 2, BOX_T * 3, rotation=(0, 90, 0),
                     mode=Mode.SUBTRACT)
    # Notches for the jack and USB-C hanging off the reSpeaker's edge. Each is
    # walled BOX_T all round inside the box first, so the box stays sealed.
    outer = (Pos((BOX_X0 + BOX_X1) / 2, (BOX_Y0 + BOX_Y1) / 2, (BOX_Z0 + BOX_Z1) / 2)
             * Box(BOX_X1 - BOX_X0, BOX_Y1 - BOX_Y0, BOX_Z1 - BOX_Z0, mode=Mode.PRIVATE))
    part = p.part
    for wall in board_under_edge(grow=BOX_T, clr=UNDER_CLR):
        part = part + (wall & outer)
    for notch in board_under_edge(clr=UNDER_CLR):
        part = part - notch
    return part & prism_f(WALL + 0.5, -10, DEPTH + 10)


def legs():
    """Four tapered, splayed mid-century legs, rooted in the foot panel."""
    out = []
    for cx, cy in LEG_POS:
        wz = -H / 2
        total = wz - LEG_FLOOR + 6.0 + LEG_EMBED
        # Same taper as ever: R_TOP is the radius 1.5 mm into the panel, so
        # the longer cone just carries the slope on through it.
        ref = wz - LEG_FLOOR + 6.0 + 1.5
        r_end = LEG_R_BOT + (LEG_R_TOP - LEG_R_BOT) * total / ref
        with BuildPart(mode=Mode.PRIVATE) as leg:
            with Locations((cx, cy, LEG_FLOOR - 6.0)):
                Cone(LEG_R_BOT, r_end, total,
                     align=(Align.CENTER, Align.CENTER, Align.MIN),
                     # ⚠️ Signs inverted from the obvious reading: the cone
                     # is built foot-up, so tilting the TOP in splays the
                     # FOOT out -- and the two axes need OPPOSITE signs.
                     rotation=(LEG_SPLAY * (1 if cy > DEPTH / 2 else -1),
                               -LEG_SPLAY * (1 if cx > CAB_CX else -1), 0))
            # Trim the feet on one plane, or it rocks.
            with Locations((cx, cy, LEG_FLOOR)):
                Box(60, 60, 40, align=(Align.CENTER, Align.CENTER, Align.MAX),
                    mode=Mode.SUBTRACT)
        out.append(leg.part & slab(LEG_FLOOR - 50, wz + WALL - 0.1))
    return out


def foot_panel_part():
    """Floor panel + legs, one print: inner face on the bed, legs up."""
    z0 = -H / 2
    with BuildPart() as p:
        with Locations(((PANEL_X0 + PANEL_X1) / 2,
                        (PANEL_Y0 + PANEL_CLR + DEPTH) / 2, z0)):
            Box(PANEL_X1 - PANEL_X0 - PANEL_CLR * 2, DEPTH - PANEL_Y0 - PANEL_CLR,
                WALL - 0.1, align=(Align.CENTER, Align.CENTER, Align.MIN))
        # The rim past the back, rolled like the wrap's.
        with Locations(((PANEL_X0 + PANEL_X1) / 2, DEPTH - 0.5, z0)):
            Box(PANEL_X1 - PANEL_X0 - PANEL_CLR * 2, REC + 0.5, WALL - 0.1,
                align=(Align.CENTER, Align.MIN, Align.MIN))
        fillet([e for e in p.edges().filter_by(Axis.X)
                if abs(e.center().Y - (DEPTH + REC)) < 0.01
                and abs(e.center().Z - z0) < 0.01], radius=ROLL)
        # Rabbet for the back's tab (open at both ends).
        with Locations(((PANEL_X0 + PANEL_X1) / 2, (Y_BACK + DEPTH) / 2,
                        z0 + WALL - 0.1 + 0.01)):
            Box(PANEL_X1 - PANEL_X0, BACK_T + 2 * RAB_CLR, RAB_D + 0.01,
                align=(Align.CENTER, Align.CENTER, Align.MAX), mode=Mode.SUBTRACT)
        for leg in legs():
            p.part = p.part + leg
        # Countersunk M3 up into the frame.
        with Locations(*[(x, y, z0 - 0.1) for x, y in PANEL_SCREWS]):
            Cylinder(SCREW_CLR / 2, WALL + 0.2,
                     align=(Align.CENTER, Align.CENTER, Align.MIN),
                     mode=Mode.SUBTRACT)
            Cone(3.3, SCREW_CLR / 2, 1.8,
                 align=(Align.CENTER, Align.CENTER, Align.MIN),
                 mode=Mode.SUBTRACT)
        # Voice speaker: its own small hex grille, plus slotted ear holes.
        pts = []
        n = int(VS_GRILLE_D / VS_PITCH) + 2
        for r in range(-n, n + 1):
            z = r * VS_PITCH * 0.866
            off = (VS_PITCH / 2) if (r % 2) else 0.0
            for c in range(-n, n + 1):
                x = c * VS_PITCH + off
                if math.hypot(x, z) <= (VS_GRILLE_D - VS_HOLE_D) / 2:
                    pts.append((VS_X + x, VS_Y + z, z0 - 0.1))
        with Locations(*pts):
            Cylinder(VS_HOLE_D / 2, WALL + 0.2,
                     align=(Align.CENTER, Align.CENTER, Align.MIN),
                     mode=Mode.SUBTRACT)
        # Buck converter: two M3 self-tap pilots through the panel.
        with Locations(*[(CONV_X + sx * CONV_EAR_PITCH / 2, CONV_Y, z0 - 0.1)
                         for sx in (-1, 1)]):
            Cylinder(PLATE_PILOT / 2, WALL + 0.2,
                     align=(Align.CENTER, Align.CENTER, Align.MIN),
                     mode=Mode.SUBTRACT)
        with Locations(*[(VS_X + ex, VS_Y + ey, z0 - 0.1) for ex, ey in VS_EARS]):
            Cylinder(VS_EAR_D / 2, WALL + 0.2,
                     align=(Align.CENTER, Align.CENTER, Align.MIN),
                     mode=Mode.SUBTRACT)
    return p.part


def dome_ball(shift=0.0):
    """The sphere whose cap is the grille's dome (shift: +Y, into the box)."""
    sag = DOME_H - DOME_EDGE                    # rim to centre
    rad = (DOME_R ** 2 + sag ** 2) / (2 * sag)
    y_apex = GR_REBATE - GR_T - DOME_H
    return Pos(X_GRILLE, y_apex + rad + shift, 0) * Sphere(rad, mode=Mode.PRIVATE), rad


def dome_height(r, shift=0.0):
    """How far in front of the grille's face the dome surface is at radius r."""
    _, rad = dome_ball()
    return DOME_H - shift - (rad - math.sqrt(rad ** 2 - r ** 2))


def grille_part():
    """Removable perforated grille over the PC83, its middle domed out."""
    y_face = GR_REBATE - GR_T
    y_front = y_face - DOME_H - 1.0
    ball, _ = dome_ball()
    inner, _ = dome_ball(DOME_SHELL)
    # Clearance over the surround, at the pocket's edge (its lowest point).
    flange_top = GR_REBATE - GR_RELIEF
    edge = (flange_top - y_face) + dome_height(DRIVER_LIP / 2, DOME_SHELL)
    assert edge >= SURROUND_H + 1.5, f"dome clears the surround by only {edge:.2f}"
    print(f"  grille       dome clears the flange by {edge:.2f} at its pocket's edge")
    with BuildPart() as p:
        with BuildSketch(Plane.XZ.offset(-GR_REBATE)):
            with Locations((X_GRILLE, 0)):
                RectangleRounded(GR_W - 0.4, GR_H - 0.4, GR_R)
        extrude(amount=GR_T)
        with BuildPart(mode=Mode.PRIVATE) as sq:
            with BuildSketch(Plane.XZ.offset(-(y_face + 0.01))):
                with Locations((X_GRILLE, 0)):
                    RectangleRounded(GR_W - 0.4, GR_H - 0.4, GR_R)
            extrude(amount=y_face + 0.01 - y_front)
        p.part = p.part + (sq.part & ball)
        # Flat seats for the screw heads, down at the old face.
        with Locations(*[(X_GRILLE + sx * GR_PCD_X / 2, y_face, sz * GR_PCD_Z / 2)
                         for sx in (-1, 1) for sz in (-1, 1)]):
            Cylinder(3.6, y_face - y_front, rotation=(90, 0, 0),
                     align=(Align.CENTER, Align.CENTER, Align.MIN),
                     mode=Mode.SUBTRACT)
        pocket = (Pos(X_GRILLE, GR_REBATE + 0.01, 0) * Cylinder(
            DRIVER_LIP / 2, GR_REBATE + 0.01 - y_front, rotation=(90, 0, 0),
            align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.PRIVATE)) & inner
        p.part = p.part - pocket
        if GR_RELIEF > 0:                   # back face, over the flange
            with Locations((X_GRILLE, GR_REBATE + 0.01, 0)):
                Cylinder(DRIVER_OPEN / 2 + 0.2, GR_RELIEF + 0.01,
                         rotation=(90, 0, 0),
                         align=(Align.CENTER, Align.CENTER, Align.MIN),
                         mode=Mode.SUBTRACT)
        rows = int(GR_FIELD / (GR_PITCH * 0.866)) + 2
        cols = int(GR_FIELD / GR_PITCH) + 2
        pts = []
        for r in range(-rows // 2, rows // 2 + 1):
            z = r * GR_PITCH * 0.866
            off = (GR_PITCH / 2) if (r % 2) else 0.0
            for c in range(-cols // 2, cols // 2 + 1):
                x = c * GR_PITCH + off
                if math.hypot(x, z) <= GR_FIELD / 2:
                    pts.append((X_GRILLE + x, y_front, z))
        with Locations(*pts):
            Cylinder(GR_HOLE_D / 2, GR_REBATE - y_front + 1, rotation=INTO,
                     align=(Align.CENTER, Align.CENTER, Align.MIN),
                     mode=Mode.SUBTRACT)
        for sx in (-1, 1):
            for sz in (-1, 1):
                with Locations((X_GRILLE + sx * GR_PCD_X / 2, y_front,
                                sz * GR_PCD_Z / 2)):
                    Cylinder(SCREW_CLR / 2, GR_REBATE - y_front + 1, rotation=INTO,
                             align=(Align.CENTER, Align.CENTER, Align.MIN),
                             mode=Mode.SUBTRACT)
    return p.part


def knob_part():
    """Fluted knob, D bore for the EC11. Prints front-down, bore up."""
    with BuildPart(mode=Mode.PRIVATE) as p:
        Cylinder(KNOB_D / 2, KNOB_H, align=MIN)
        p.part = chamfer(p.part.edges().group_by(Axis.Z)[-1], length=1.2)
        for k in range(KNOB_FLUTES):
            a = 2 * math.pi * k / KNOB_FLUTES
            with Locations((KNOB_D / 2 * math.cos(a), KNOB_D / 2 * math.sin(a), -1)):
                Cylinder(FLUTE_R, KNOB_H + 2, align=MIN, mode=Mode.SUBTRACT)
        with Locations((0, 0, KNOB_H - 0.5)):                # inlaid ring
            Cylinder(7.8, 1.0, align=MIN, mode=Mode.SUBTRACT)
            Cylinder(7.0, 0.5, align=MIN)
        with BuildSketch(Plane.XY.offset(-0.01)):            # D bore
            Circle(SHAFT_D / 2 + BORE_CLR)
            flat = SHAFT_FLAT - SHAFT_D / 2 + BORE_CLR
            with Locations((flat + SHAFT_D / 2, 0)):
                Rectangle(SHAFT_D, SHAFT_D + 2, mode=Mode.SUBTRACT)
        extrude(amount=BORE_DEPTH + 0.01, mode=Mode.SUBTRACT)
        # Counterbore over the bushing, which stands 0.5 proud of the face:
        # the push switch travels 0.5 and the knob must not land on it.
        with Locations((0, 0, -0.01)):
            Cylinder(4.6, 1.0, align=MIN, mode=Mode.SUBTRACT)
    # local +Z (back face at 0) -> cabinet -Y, off the face by KNOB_GAP
    return Pos(ENC_X, -KNOB_GAP, ENC_Z) * Rotation(90, 0, 0) * p.part


def pi_proxy():
    """Screen body + Orange Pi on its standoffs. Not printed -- clearance only."""
    y_plate = SCREEN_REG
    with BuildPart() as p:
        with Locations((X_SCREEN, y_plate, 0)):
            Box(SCREEN_PCB_W, SCREEN_T - 6.0, SCREEN_PCB_H,
                align=(Align.CENTER, Align.MIN, Align.CENTER))
        y_pcb = y_plate + PI_BEHIND_PLATE
        with Locations((X_SCREEN, y_pcb, 0)):
            Box(PI_W, PI_PCB_T, PI_D, align=(Align.CENTER, Align.MIN, Align.CENTER))
        with Locations((X_SCREEN, y_pcb + PI_PCB_T, 0)):
            Box(PI_W - 6, PI_TALLEST, PI_D - 6,
                align=(Align.CENTER, Align.MIN, Align.CENTER))
    return p.part


def screen_plate_proxy():
    with BuildPart() as p:
        with Locations((X_SCREEN, SCREEN_REG, 0)):
            Cylinder(SCREEN_MOD / 2, 6.0, rotation=OUTOF,
                     align=(Align.CENTER, Align.CENTER, Align.MIN))
    return p.part


def board_proxy():
    """reSpeaker + XIAO, face-up under the crown. Not printed."""
    z_top = H / 2 - SKIN - BOARD_HANG
    with BuildPart() as p:
        with Locations((BOARD_X, BOARD_Y, z_top - BOARD_PCB_T)):
            Cylinder(BOARD_D / 2, BOARD_PCB_T,
                     align=(Align.CENTER, Align.CENTER, Align.MIN))
        with Locations((BOARD_X, BOARD_Y, z_top - BOARD_PCB_T - 6.7)):
            Cylinder(BOARD_D / 2 - 6, 6.7,
                     align=(Align.CENTER, Align.CENTER, Align.MIN))
        for part in board_under_edge():                 # jack + board USB-C
            add(part)
        # XIAO + its USB-C, and room for a right-angle plug beyond the edge
        cx, cy = board_xy(0.0, 38.5)
        with Locations((cx, cy, z_top - BOARD_PCB_T - 4.5)):
            Box(9.0 if abs(math.sin(math.radians(BOARD_ROT))) < 0.5 else 23.0,
                23.0 if abs(math.sin(math.radians(BOARD_ROT))) < 0.5 else 9.0,
                4.5, align=(Align.CENTER, Align.CENTER, Align.MIN))
        px, py = board_xy(0.0, 50.0 + 10.0)
        # (the USB-C sits just UNDER the PCB, so the plug does too)
        with Locations((px, py, z_top - BOARD_PCB_T - 7.5)):
            Box(20.0 if abs(math.sin(math.radians(BOARD_ROT))) > 0.5 else 12.0,
                12.0 if abs(math.sin(math.radians(BOARD_ROT))) > 0.5 else 20.0,
                7.0, align=(Align.CENTER, Align.CENTER, Align.MIN))
    return p.part


def converter_proxy():
    """The buck converter's body on the foot panel. Not printed."""
    with BuildPart() as p:
        with Locations((CONV_X, CONV_Y, -H / 2 + WALL - 0.1)):
            Box(CONV_W, CONV_D, CONV_H, align=(Align.CENTER, Align.CENTER, Align.MIN))
    return p.part


def voice_speaker_proxy():
    with BuildPart() as p:
        with Locations((VS_X, VS_Y, -H / 2 + WALL + VS_FOAM_SQ)):
            Box(VS_W, VS_D, VS_H, align=(Align.CENTER, Align.CENTER, Align.MIN))
    return p.part


def box_pads_part():
    """Two risers: foot panel up to the speaker box's underside (less foam)."""
    z_top = -H / 2 + WALL - 0.1                 # foot panel's inner face
    h = BOX_Z0 - z_top - PAD_FOAM + PAD_SQ
    x = (BOX_X0 + BOX_X1) / 2
    with BuildPart() as p:
        with Locations(*[(x, y, z_top) for y in PAD_YS]):
            Box(PAD_W, PAD_D, h, align=(Align.CENTER, Align.CENTER, Align.MIN))
    return p.part


def encoder_proxy():
    """EC11 on its perfboard carrier. Clearance only."""
    yb = ENC_BOARD_Y
    with BuildPart() as p:
        with Locations((ENC_X, yb, ENC_Z + (ENC_BOARD_UP - ENC_BOARD_DN) / 2)):
            Box(ENC_BOARD_W, ENC_BOARD_T + 3.5, ENC_BOARD_UP + ENC_BOARD_DN,
                align=(Align.CENTER, Align.MIN, Align.CENTER))   # + pins behind
        with Locations((ENC_X, yb, ENC_Z)):
            Box(12.5, ENC_BODY_H, 13.0, align=(Align.CENTER, Align.MAX, Align.CENTER))
        with Locations((ENC_X, yb - ENC_BODY_H, ENC_Z)):
            Cylinder(4.4, ENC_SHOULDER, rotation=(90, 0, 0),
                     align=(Align.CENTER, Align.CENTER, Align.MIN))
    return p.part


def vs_spacers_part():
    """Two spacer tubes: foot panel up to the voice speaker's ears."""
    with BuildPart() as p:
        with Locations(*[(VS_X + ex, VS_Y + ey, -H / 2 + WALL)
                         for ex, ey in VS_EARS]):
            Cylinder(VS_SPACER_OD / 2, VS_SPACER_H,
                     align=(Align.CENTER, Align.CENTER, Align.MIN))
            Cylinder(VS_EAR_D / 2, VS_SPACER_H,
                     align=(Align.CENTER, Align.CENTER, Align.MIN),
                     mode=Mode.SUBTRACT)
    return p.part


def print_orientation(name, part):
    """Rotate a part onto the bed the way it should be printed."""
    rot = {
        "wrap": Rotation(90, 0, 0),           # lip down: every wall vertical
        "front_panel": Rotation(90, 0, 0),    # face down, ears up
        "grille": Rotation(-90, 0, 0),        # back down, dome up; support the pocket
        "back": Rotation(-90, 0, 0),          # outer face down, clip up
        "speaker_box": Rotation(-90, 0, 0),   # back down, throat up
        "foot_panel": Rotation(180, 0, 0),    # inner face down, legs up
        "knob": Rotation(90, 0, 0),           # front down, bore up
    }[name]
    r = rot * part
    bb = r.bounding_box()
    return Pos(-bb.center().X, -bb.center().Y, -bb.min.Z) * r


def overlap(a, b):
    try:
        return (a & b).volume
    except Exception:                                       # noqa: BLE001
        return float("nan")


def main():
    wrap, front, back = wrap_part(), front_panel_part(), back_part()
    box = speaker_box_part()
    panel = foot_panel_part()
    grille = grille_part()
    board, pi, plate = board_proxy(), pi_proxy(), screen_plate_proxy()
    knob, vs = knob_part(), voice_speaker_proxy()
    conv = converter_proxy()
    spacers = vs_spacers_part()
    pads = box_pads_part()
    enc = encoder_proxy()

    printed = {"wrap": wrap, "front_panel": front, "back": back,
               "speaker_box": box, "foot_panel": panel, "grille": grille,
               "knob": knob}
    for name, part in printed.items():
        n = len(part.solids())
        print(f"  {name:12s} {part.volume / 1000:6.1f} cm^3  solids {n}")
        assert n == 1, f"{name} is {n} solids"

    # Clearances that matter: nothing printed may occupy the same space as
    # another part or as the boards. Contact faces read as ~0.
    checks = [("board", board, wrap), ("pi+screen", pi, wrap + front),
              ("plate", plate, wrap + front), ("box", box, wrap + front),
              ("box/panel", box, panel), ("panel", panel, wrap),
              ("back", back, wrap), ("front", front, wrap),
              ("back/panel", back, panel),
              ("board/box", board, box), ("board/back", board, back),
              ("vspk", vs, wrap), ("vspk/pi", vs, pi),
              ("spacers", spacers, vs + panel + conv + wrap),
              ("pads", pads, panel + wrap + conv + vs + pi),
              ("encoder", enc, wrap + front + box + pi + plate + conv),
              ("knob", knob, wrap + front), ("grille", grille, wrap + front),
              ("conv", conv, wrap + box + back), ("conv/pi", conv, pi + vs)]
    for label, a, b in checks:
        v = overlap(a, b)
        flag = "" if v < 1.0 else "   ⚠️ INTERFERENCE"
        print(f"  overlap {label:10s} {v:8.2f} mm^3{flag}")

    chamber = ((BOX_X1 - BOX_X0 - 2 * BOX_T) * (BOX_Z1 - BOX_Z0 - 2 * BOX_T)
               * (BOX_Y1 - BOX_Y0 - BOX_PLATE - BOX_T) / 1e6)
    print(f"  sealed box   ~{chamber:.2f} L gross (less the throat loft)")

    wrap.label, wrap.color = "wrap", IVORY
    front.label, front.color = "front_panel", BLUE
    back.label, back.color = "back", BLUE
    box.label, box.color = "speaker_box", GREY
    panel.label, panel.color = "foot_panel", WHITE
    grille.label, grille.color = "grille", WHITE
    knob.label, knob.color = "knob", IVORY
    spacers.label, spacers.color = "vs_spacers", GREY
    pads.label, pads.color = "box_pads", GREY
    for prox, lab in ((board, "reSpeaker"), (pi, "pi_screen"), (plate, "screen_plate"),
                      (vs, "voice_speaker"), (conv, "buck_converter"),
                      (enc, "encoder")):
        prox.label, prox.color = lab, GREY
    asm = Compound(children=[wrap, front, back, box, panel, grille, knob,
                             spacers, pads, board, pi, plate, vs, conv, enc])
    bb = asm.bounding_box()
    print(f"  cabinet      {bb.size.X:.0f} W x {bb.size.Z:.0f} H x {bb.size.Y:.0f} D")

    export_step(asm, str(OUT / "voice_satellite.step"))
    export_stl(asm, str(OUT / "voice_satellite.stl"))
    pdir = OUT / "print"
    pdir.mkdir(exist_ok=True)
    for name, part in printed.items():
        oriented = print_orientation(name, part)
        s = oriented.bounding_box().size
        print(f"  print {name:12s} {s.X:5.0f} x {s.Y:5.0f} x {s.Z:5.0f}")
        export_stl(oriented, str(pdir / f"{name}.stl"))
    # Two loose tubes, already standing upright: just drop them to the bed.
    bb = spacers.bounding_box()
    export_stl(Pos(-bb.center().X, -bb.center().Y, -bb.min.Z) * spacers,
               str(pdir / "vs_spacers.stl"))
    print(f"  print vs_spacers   2 x Ø{VS_SPACER_OD:.0f} x {VS_SPACER_H}")
    bb = pads.bounding_box()
    export_stl(Pos(-bb.center().X, -bb.center().Y, -bb.min.Z) * pads,
               str(pdir / "box_pads.stl"))
    print(f"  print box_pads     2 x {PAD_W:.0f} x {PAD_D:.0f} x {bb.size.Z:.2f}"
          f"  (+ {PAD_FOAM} foam -> {bb.size.Z + PAD_FOAM:.2f} into a"
          f" {BOX_Z0 - (-H / 2 + WALL - 0.1):.2f} gap)")
    print(f"\nwrote {OUT}/voice_satellite.step (+ .stl, print/*.stl)")


if __name__ == "__main__":
    main()
