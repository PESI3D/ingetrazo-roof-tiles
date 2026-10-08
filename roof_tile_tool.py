# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pesi (pesi3d.de)
"""Roof Tiles — build roofs and cover them with real 3D roof tiles, for
IngeTrazo.

**Create Roof…** builds a roof on a footprint (a horizontal face, or a
building body): gable, hip, half-hip, Dutch gable, pyramid, mono-pitch,
split-level, saltbox, mansard, gambrel, bonnet, butterfly, M-roof,
sawtooth, barrel, spire, dome, Rhenish helm, A-frame and flat — gable, hip
and their kin on any footprint (L, T, U …) through a weighted straight
skeleton. **Edit Roof Shape…** changes it later; a covering laid on it
follows.

Model the roof as you like (gable, hip, half-hip, mono-pitch, mansard,
pyramid, L- and T-shaped roofs with valleys, dormers, chimneys as holes),
select its **roof faces** (or the group that holds them) and run
**Roof Tiles ▸ Cover Roof…**. The plugin reads every edge of the roof by
itself and lays the tiles the way a roofer does:

* **Eaves** — the first course starts at the eave with an overhang into the
  gutter; the batten gauge is fitted between eave and ridge inside the
  tile's range, so every course is a full one.
* **Ridge and hips** — ridge tiles along the ridge, hip tiles along every
  hip (laid from the eave upwards), end pieces at the ridge ends and at
  the foot of every hip.
* **Mono-pitch ridges** — one mono-pitch ridge tile per column, the tile's
  profile turned down over the top edge.
* **Verges** — verge tiles (left / right) on every gable edge, inner ones
  too; the cover width is fitted between the verges. Or the tiles cut
  flush and the verge closed with a mortar bead, a verge board or a verge
  flashing.
* **Valleys** — the tiles are cut along the valley with an open gap and a
  valley flashing underneath.
* **Holes** (chimney, skylight) and free edges against a wall — tiles cut.

Classic tiles from around the world are built in (Frankfurt pan, Harz pan,
Toscana, flat interlocking tile, Marseille tile, plain tile «Biberschwanz»,
monk and nun, English pantile, English plain tile, Spanish tile) — the
dimensions are typical values, not the data of any one manufacturer. A tile
of your own comes from an .igz or .obj file or from the selection.

Every whole tile is an INSTANCE of one shared tile (a big roof stays light);
cut tiles are real cuts (closed solids, made with manifold3d). The result is
ONE group that remembers its roof faces and settings: select it and run
**Edit Roof Tiles…** to change it. Every run is one undo step; the Live
Preview shows the result in the model while the dialog stays open.

Install: copy this file into the plugins folder
(Extensions ▸ Open plugins folder; on Windows %APPDATA%\\ingetrazo\\plugins)
and restart IngeTrazo. Needs IngeTrazo ≥ 0.5.7 (extension API 2).

Product names (Frankfurter Pfanne, Harzer Pfanne, …) are used only to
describe the tile shape; this plugin is not affiliated with any tile maker.
"""
from __future__ import annotations

import json
import math
import time

KEY = "roof_tile_tool"
TITLE = "Roof Tiles"
VERSION = "1.0"
SETTINGS_KEY = "plugins/roof_tile_tool/params"
MAX_TILES = 40_000              # instances + cut tiles: keep it sane
WARN_TILES = 12_000
MIN_TILT = 3.0                  # degrees: steeper than 90°−this = a wall
FLAT_TILT = 0.2                 # degrees: flatter = level, no fall to lay by
MAX_TILT = 87.0
TOL = 0.003                     # m: edges closer than this are the same


# ---------------------------------------------------------------------------
# The tiles
# ---------------------------------------------------------------------------
#   W   cover width (Deckbreite)        Wt  overall width
#   Lt  overall length                  Lmin/Lmax  batten gauge range
#   t   plate thickness                 A   profile height
#   prof profile shape                  half  rows offset by half a tile
#   verge  default verge: "tiles" (verge tiles), or the tiles cut flush and
#          the edge closed with "mortar", a "board" or "metal" flashing —
#          or "cut" (left open)
#   minpitch  usual lowest roof pitch (°) — below it only a warning
#   ridge  (radius, half angle °, length, gauge) of the ridge tile

PRESETS = [
    dict(id="frankfurt", minpitch=22, name="Frankfurt pan (Frankfurter Pfanne)",
         region="Germany · concrete", W=0.300, Wt=0.330, Lt=0.420,
         Lmin=0.312, Lmax=0.345, t=0.015, A=0.030, prof="double",
         half=False, verge="tiles", ridge=(0.135, 88, 0.420, 0.375)),
    dict(id="harz", minpitch=22, name="Harz pan (Harzer Pfanne)",
         region="Germany · concrete", W=0.300, Wt=0.330, Lt=0.420,
         Lmin=0.310, Lmax=0.345, t=0.015, A=0.042, prof="s",
         half=False, verge="tiles", ridge=(0.135, 88, 0.420, 0.375)),
    dict(id="toscana", minpitch=22, name="Toscana (monk-and-nun look)",
         region="Mediterranean · clay", W=0.209, Wt=0.262, Lt=0.424,
         Lmin=0.330, Lmax=0.345, t=0.013, A=0.060, prof="roll",
         half=False, verge="tiles", ridge=(0.125, 88, 0.400, 0.350)),
    dict(id="flat", minpitch=22, name="Flat interlocking tile",
         region="Modern · concrete / clay", W=0.300, Wt=0.330, Lt=0.420,
         Lmin=0.312, Lmax=0.345, t=0.016, A=0.006, prof="flat",
         half=False, verge="tiles", ridge=(0.130, 88, 0.420, 0.375)),
    dict(id="marseille", minpitch=22, name="Marseille tile",
         region="France / worldwide · clay", W=0.223, Wt=0.260, Lt=0.433,
         Lmin=0.320, Lmax=0.360, t=0.013, A=0.020, prof="ribs",
         half=False, verge="tiles", ridge=(0.125, 88, 0.400, 0.350)),
    dict(id="biber", minpitch=30, name="Plain tile «Biberschwanz» (double lap)",
         region="Germany · clay", W=0.180, Wt=0.180, Lt=0.380,
         Lmin=0.145, Lmax=0.165, t=0.013, A=0.0, prof="biber",
         half=True, verge="board", ridge=(0.120, 88, 0.400, 0.330)),
    dict(id="monk", minpitch=40, name="Monk and nun (Mönch und Nonne)",
         region="Europe · clay", W=0.190, Wt=0.190, Lt=0.400,
         Lmin=0.300, Lmax=0.330, t=0.014, A=0.075, prof="monk",
         half=False, verge="mortar", ridge=(0.125, 88, 0.400, 0.330)),
    dict(id="pantile", minpitch=30, name="English pantile",
         region="UK · clay", W=0.210, Wt=0.252, Lt=0.342,
         Lmin=0.250, Lmax=0.270, t=0.012, A=0.045, prof="s",
         half=False, verge="tiles", ridge=(0.115, 88, 0.330, 0.290)),
    dict(id="plain_uk", minpitch=35, name="English plain tile (double lap)",
         region="UK · clay", W=0.165, Wt=0.165, Lt=0.265,
         Lmin=0.090, Lmax=0.115, t=0.012, A=0.003, prof="plain",
         half=True, verge="board", ridge=(0.115, 88, 0.330, 0.290)),
    dict(id="spanish", minpitch=20, name="Spanish tile (teja curva, cover and channel)",
         region="Spain / Latin America · clay", W=0.200, Wt=0.200, Lt=0.450,
         Lmin=0.330, Lmax=0.380, t=0.012, A=0.075, prof="spanish",
         half=False, verge="mortar", ridge=(0.110, 88, 0.450, 0.380)),
]
PRESET_BY_ID = {p["id"]: p for p in PRESETS}
CUSTOM = "custom"

COLORS = [
    ("Natural red", (0.70, 0.27, 0.16)),
    ("Copper red", (0.58, 0.22, 0.13)),
    ("Terracotta", (0.78, 0.43, 0.25)),
    ("Brown", (0.36, 0.22, 0.15)),
    ("Anthracite", (0.20, 0.21, 0.22)),
    ("Black", (0.09, 0.09, 0.10)),
    ("Slate grey", (0.36, 0.38, 0.40)),
]
FLASHING_COLOR = (0.62, 0.64, 0.66)
DETAIL = {"low": 8, "medium": 14, "high": 24}
VERGE_DEPTH = 0.045             # m: lip of a verge tile below the roof face
VERGE_MODES = ("tiles", "mortar", "board", "metal", "cut")
VERGE_LABELS = {"tiles": "Verge tiles",
                "mortar": "Cut flush, mortar bead",
                "board": "Cut flush, verge board",
                "metal": "Cut flush, verge flashing",
                "cut": "Cut flush, open"}
MORTAR_COLOR = (0.78, 0.76, 0.72)
BOARD_COLOR = (0.93, 0.92, 0.89)


def default_params() -> dict:
    return {"preset": "frankfurt", "W": 0.300, "Lmin": 0.312, "Lmax": 0.345,
            "detail": "medium", "color": "Natural red",
            "eave_ov": 0.05, "ridge_gap": 0.03, "verge": "tiles",
            "verge_ov": 0.03, "valley_gap": 0.05, "hip_gap": 0.01,
            "cut_gap": 0.01, "offset": 0.0,
            "ridge": True, "hips": True, "mono": True, "endcaps": True,
            "endstyle": "stone",
            "flashing": True, "holeflash": True,
            "follow": False, "force": False,
            "custom": None}


def normalize_params(p) -> dict:
    out = default_params()
    if isinstance(p, dict):
        for k in out:
            if k in p:
                out[k] = p[k]
    if out["preset"] != CUSTOM and out["preset"] not in PRESET_BY_ID:
        out["preset"] = "frankfurt"
    if out["preset"] == CUSTOM and not isinstance(out["custom"], dict):
        out["preset"] = "frankfurt"

    def num(k, lo, hi):
        try:
            v = float(out[k])
        except (TypeError, ValueError):
            v = default_params()[k]
        out[k] = min(hi, max(lo, v))
    num("W", 0.03, 2.0)
    num("Lmin", 0.03, 2.0)
    num("Lmax", 0.03, 2.0)
    if out["Lmax"] < out["Lmin"]:
        out["Lmax"] = out["Lmin"]
    for k in ("eave_ov", "verge_ov"):
        num(k, 0.0, 0.5)
    for k in ("ridge_gap", "valley_gap", "hip_gap", "cut_gap"):
        num(k, 0.0, 0.5)
    num("offset", -0.5, 0.5)
    if out["detail"] not in DETAIL:
        out["detail"] = "medium"
    if out["color"] not in dict(COLORS):
        out["color"] = COLORS[0][0]
    if out["endstyle"] not in dict(END_STYLES):
        out["endstyle"] = "stone"
    if out["verge"] not in VERGE_MODES:
        out["verge"] = "tiles"
    for k in ("ridge", "hips", "mono", "endcaps", "flashing", "holeflash",
              "follow",
              "force"):
        out[k] = bool(out[k])
    return out


def load_params() -> dict:
    try:
        from PySide6.QtCore import QSettings
        raw = QSettings().value(SETTINGS_KEY)
        p = normalize_params(json.loads(raw) if raw else None)
    except Exception:  # noqa: BLE001
        p = default_params()
    p["force"] = False
    return p


def save_params(p: dict) -> None:
    try:
        from PySide6.QtCore import QSettings
        q = {k: v for k, v in p.items() if k not in ("force", "custom")}
        QSettings().setValue(SETTINGS_KEY, json.dumps(q))
    except Exception:  # noqa: BLE001
        pass


def tile_spec(p) -> dict:
    """The tile in use: the preset (or custom tile) with the user's cover
    width and gauge range."""
    if p["preset"] == CUSTOM and isinstance(p.get("custom"), dict):
        c = p["custom"]
        spec = dict(id=CUSTOM, name=c.get("name") or "Custom tile",
                    region="Custom", W=p["W"], Wt=c["Wt"], Lt=c["Lt"],
                    Lmin=p["Lmin"], Lmax=p["Lmax"], t=0.012,
                    A=max(0.0, c["H"] - 0.012), prof="custom", half=False,
                    verge="cut", ridge=(0.125, 88, 0.400, 0.340))
    else:
        spec = dict(PRESET_BY_ID[p["preset"]])
        spec["W"], spec["Lmin"], spec["Lmax"] = p["W"], p["Lmin"], p["Lmax"]
    spec["Wt"] = max(spec["Wt"], spec["W"])
    spec["Lmax"] = min(spec["Lmax"], spec["Lt"] - 0.01)
    spec["Lmin"] = min(spec["Lmin"], spec["Lmax"])
    return spec


class RoofError(Exception):
    """A user-facing refusal."""


# ---------------------------------------------------------------------------
# Small solids: vertices + polygons (outward, counter-clockwise)
# ---------------------------------------------------------------------------

class Solid:
    __slots__ = ("V", "F")

    def __init__(self, V=None, F=None):
        self.V = list(V or [])
        self.F = [list(f) for f in (F or [])]

    def add(self, other):
        n = len(self.V)
        self.V.extend(other.V)
        self.F.extend([i + n for i in f] for f in other.F)
        return self

    def volume(self):
        import numpy as np
        V = np.asarray(self.V, float)
        vol = 0.0
        for f in self.F:
            a = V[f[0]]
            for i in range(1, len(f) - 1):
                vol += float(np.dot(a, np.cross(V[f[i]], V[f[i + 1]])))
        return vol / 6.0

    def fix_orientation(self):
        if self.volume() < 0:
            self.F = [list(reversed(f)) for f in self.F]
        return self


def _strip_solid(xs, zb, zt, y0, y1, taper=1.0):
    """A plate along y: cross-section bottom ``zb(x)`` / top ``zt(x)``
    at the samples ``xs``, from ``y0`` to ``y1``. ``taper`` scales the
    cross-section at ``y1`` (x and z, about the origin)."""
    n = len(xs)
    loop = [(xs[i], zb[i]) for i in range(n)] + \
           [(xs[i], zt[i]) for i in range(n - 1, -1, -1)]
    m = len(loop)
    V = [(x, y0, z) for x, z in loop] + \
        [(x * taper, y1, z * taper) for x, z in loop]
    F = [list(range(m - 1, -1, -1)), list(range(m, 2 * m))]
    for i in range(m):
        j = (i + 1) % m
        F.append([i, j, m + j, m + i])
    return Solid(V, F).fix_orientation()


def _prism_solid(poly, z0, z1):
    """An xy polygon (convex or not, counter-clockwise) from z0 to z1."""
    m = len(poly)
    V = [(x, y, z0) for x, y in poly] + [(x, y, z1) for x, y in poly]
    F = [list(range(m - 1, -1, -1)), list(range(m, 2 * m))]
    for i in range(m):
        j = (i + 1) % m
        F.append([i, j, m + j, m + i])
    return Solid(V, F).fix_orientation()


def _xz_prism(poly_xz, y0, y1):
    """A polygon in the xz plane, extruded along y."""
    m = len(poly_xz)
    V = [(x, y0, z) for x, z in poly_xz] + [(x, y1, z) for x, z in poly_xz]
    F = [list(range(m - 1, -1, -1)), list(range(m, 2 * m))]
    for i in range(m):
        j = (i + 1) % m
        F.append([i, j, m + j, m + i])
    return Solid(V, F).fix_orientation()


def _box(x0, x1, y0, y1, z0, z1):
    return _prism_solid([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], z0, z1)


# ---- tile profiles ----------------------------------------------------------

def _profile(prof, u, A):
    """Height of the tile's underside at ``u`` = x / cover width (period 1)."""
    u = u % 1.0
    d = min(u, 1.0 - u)                   # distance to the side joint
    tp = 2.0 * math.pi
    if prof == "double":                  # two even waves (Frankfurt)
        return A * (0.5 + 0.5 * math.cos(2 * tp * u))
    if prof == "s":                       # one big S wave (Harz, pantile)
        return A * (0.5 + 0.5 * math.cos(tp * u + 0.55 * math.sin(tp * u)))
    if prof == "roll":                    # high roll over a flat pan
        roll = A * math.sqrt(max(0.0, 1.0 - (d / 0.20) ** 2)) ** 0.9
        pan = 0.006 * (1.0 - math.sin(math.pi * u))
        return max(roll, pan)
    if prof == "monk":                    # monk over the joint, nun below
        roll = A * math.sqrt(max(0.0, 1.0 - (d / 0.24) ** 2))
        nun = 0.018 * (1.0 - math.sin(math.pi * u))
        return max(roll, nun)
    if prof == "spanish":                 # cover over a channel
        cov = A * math.sqrt(max(0.0, 1.0 - (d / 0.27) ** 2))
        chan = 0.35 * A * (1.0 - math.sin(math.pi * u)) ** 2
        return max(cov, chan)
    if prof == "ribs":                    # Marseille: ribs on a flat tile
        return A * (math.exp(-(d / 0.07) ** 2)
                    + 0.55 * math.exp(-((u - 0.5) / 0.07) ** 2))
    if prof == "flat":
        return A * math.exp(-(d / 0.05) ** 2)
    if prof == "plain":
        return A * math.sin(math.pi * u)
    return 0.0


def _samples(spec, detail, x0, x1, smooth=True):
    n = max(2, int(math.ceil((x1 - x0) / spec["W"] * DETAIL[detail]))) \
        if smooth else 2
    return [x0 + (x1 - x0) * i / n for i in range(n + 1)]


def tile_solids(spec, detail, kind="tile", flange=None):
    """The tile in its own frame: cover area x 0…W (the side lock reaches
    left to W−Wt, under the neighbour), tail at y 0, head at y Lt, lying on
    z 0. ``kind``: tile, verge_l, verge_r."""
    W, Wt, Lt, t, A = spec["W"], spec["Wt"], spec["Lt"], spec["t"], spec["A"]
    prof = spec["prof"]
    flange = VERGE_DEPTH if flange is None else flange
    out = []
    if prof == "biber":                    # flat, segmental tail
        sag = 0.035
        pts = [(W, Lt), (0.0, Lt)]
        for i in range(13):
            x = W * i / 12.0
            pts.append((x, sag * ((2.0 * x / W - 1.0) ** 2)))
        out.append(_prism_solid(pts[:2] + pts[2:], 0.0, t))
    elif prof == "custom":
        return []
    elif kind in ("verge_l", "verge_r"):
        return [_verge_tile(spec, detail, kind, flange)]
    else:
        smooth = prof not in ("biber",)
        x_lo = 0.0 if kind == "verge_l" else W - Wt
        xs = _samples(spec, detail, x_lo, W, smooth)
        zb, zt = [], []
        for x in xs:
            if x < -1e-9:                   # the side lock: under the neighbour
                z = _profile(prof, (x + W) / W, A) - t - 0.002
            else:
                z = _profile(prof, x / W, A)
            zb.append(z)
            zt.append(z + t)
        out.append(_strip_solid(xs, zb, zt, 0.0, Lt))
    return out


def _verge_tile(spec, detail, kind, depth):
    """A verge tile in ONE piece: the tile's own profile runs out over the
    gable and bends down (radius R) into the lip — one plate of the tile's
    thickness, like the real verge tile. The lower edge of the lip runs
    parallel to the roof (the tile itself is tilted by its lift), and at the
    tail the lip stands a little further out, so the lip of the course above
    laps OVER the one below."""
    W, Wt, Lt, t, A = spec["W"], spec["Wt"], spec["Lt"], spec["t"], spec["A"]
    prof = spec["prof"]
    R = max(0.012, 1.2 * t)                 # bend radius (centre line)
    lap = 0.004
    th = math.atan2(_lift(spec), Lt)
    c, s_ = math.cos(th), math.sin(th)

    def zbot(y):                            # straight in the roof frame
        return (-depth - (Lt - y) * s_) / c

    def zmid(x):
        if x < -1e-9:                       # side lock under the neighbour
            return _profile(prof, (x + W) / W, A) - t - 0.002 + t / 2
        return _profile(prof, x / W, A) + t / 2

    left = kind == "verge_l"
    # centre line from the inner end to the start of the bend
    if left:
        xs = _samples(spec, detail, R, W)[::-1]          # W … R
    else:
        xs = _samples(spec, detail, W - Wt, W - R)        # W−Wt … W−R
    mid = [(x, zmid(x)) for x in xs]
    xe, ze = mid[-1]
    sgn = -1.0 if left else 1.0
    nb = 6
    for i in range(1, nb + 1):              # the bend: a quarter circle
        f = 0.5 * math.pi * i / nb
        mid.append((xe + sgn * R * math.sin(f), ze - R + R * math.cos(f)))

    def section(y, extra):
        pts = list(mid) + [(mid[-1][0], zbot(y) + t / 2)]
        n = len(pts)
        top, bot = [], []
        for i in range(n):
            a = pts[max(0, i - 1)]
            b = pts[min(n - 1, i + 1)]
            dx, dz = b[0] - a[0], b[1] - a[1]
            ln = math.hypot(dx, dz) or 1.0
            nx, nz = -dz / ln, dx / ln       # left of the running direction
            x, z = pts[i]
            if i >= len(xs):                 # bend and lip stand out at the tail
                x += sgn * extra
            top.append((x + nx * t / 2, z + nz * t / 2))
            bot.append((x - nx * t / 2, z - nz * t / 2))
        return top + bot[::-1]

    s0 = section(0.0, lap)
    s1 = section(Lt, 0.0)
    m = len(s0)
    V = [(x, 0.0, z) for x, z in s0] + [(x, Lt, z) for x, z in s1]
    F = [list(range(m - 1, -1, -1)), list(range(m, 2 * m))]
    for i in range(m):
        j = (i + 1) % m
        F.append([i, j, m + j, m + i])
    return Solid(V, F).fix_orientation()


def ridge_solid(spec, detail, taper=0.92):
    R, beta, Lr, _g = spec["ridge"]
    t = spec["t"]
    b = math.radians(beta)
    n = max(6, DETAIL[detail])
    phis = [-b + 2 * b * i / n for i in range(n + 1)]
    xs = [R * math.sin(f) for f in phis]
    zb = [R * (math.cos(f) - math.cos(b)) for f in phis]
    # thickness along the normal: grow the radius
    xt = [(R + t) * math.sin(f) for f in phis]
    zt = [(R + t) * math.cos(f) - R * math.cos(b) for f in phis]
    loop_b = list(zip(xs, zb))
    loop_t = list(zip(xt, zt))
    loop = loop_b + loop_t[::-1]
    m = len(loop)
    V = [(x, 0.0, z) for x, z in loop] + \
        [(x * taper, Lr, z * taper) for x, z in loop]
    F = [list(range(m - 1, -1, -1)), list(range(m, 2 * m))]
    for i in range(m):
        j = (i + 1) % m
        F.append([i, j, m + j, m + i])
    return Solid(V, F).fix_orientation()


END_STYLES = [("stone", "End stone (domed)"),
              ("disc", "End disc"),
              ("fan", "Ornamental disc (fan)")]


def _loft(sections):
    """Closed solid through polygon sections of equal size (3D points)."""
    m = len(sections[0])
    V = [p for sec in sections for p in sec]
    k = len(sections)
    F = [list(range(m - 1, -1, -1)),
         list(range((k - 1) * m, k * m))]
    for j in range(k - 1):
        o0, o1 = j * m, (j + 1) * m
        for i in range(m):
            i2 = (i + 1) % m
            F.append([o0 + i, o0 + i2, o1 + i2, o1 + i])
    return Solid(V, F).fix_orientation()


def _skirt_poly(w, ztop, skirt, slope):
    """The part of an end piece below the ridge tile: as wide as the end
    piece, its lower edges parallel to the two roof faces (they meet below
    the ridge) — the gable shape of a real ridge end stone."""
    zside = min(ztop - 0.005, -skirt + w * slope)
    pts = [(-w, ztop), (w, ztop), (w, zside)]
    if -skirt < zside - 1e-4:
        pts.append((0.0, -skirt))
    pts.append((-w, zside))
    return pts


def ridge_end_solids(spec, detail, skirt=0.0, slope=0.8, style="stone"):
    """The end of a ridge at a gable, in the ridge tile's frame (the line
    runs along +y, the end piece sits at y <= 0):

    * ``stone`` — like a classic ridge end stone: a domed front over the
      end of the ridge tile, a collar round it and, below, a gable-shaped
      apron down past the verge tiles;
    * ``disc`` — a flat end disc with the same apron;
    * ``fan`` — a larger ornamental disc with a fan of ribs.
    ``skirt``: how far the apron reaches below the rims of the ridge tile,
    ``slope``: the fall of the roof faces in the tile's cross-section."""
    R, beta, _Lr, _g = spec["ridge"]
    t = spec["t"]
    b = math.radians(beta)
    n = max(10, DETAIL[detail])
    z0 = -R * math.cos(b)                    # rim level of the tile = 0
    Ro = R + t + 0.005
    skirt = max(skirt, 0.03)

    def arc(r, y, scale=1.0):
        out = []
        for i in range(n + 1):
            f = b - 2 * b * i / n
            out.append((r * scale * math.sin(f), y,
                        r * scale * math.cos(f) + z0 * scale))
        return out

    w = Ro * math.sin(b) + 0.008
    out = []
    if style == "stone":
        db = 0.022                            # how far the front bulges out
        secs = []
        for k in range(5):
            th = math.radians(70.0 * k / 4)
            secs.append(arc(Ro, -db * math.sin(th), math.cos(th)))
        out.append(_loft(secs))
        # collar: a short shell round the end of the ridge tile
        outer = arc(Ro + 0.004, 0.0)
        inner = arc(R + t + 0.0005, 0.0)
        loop = [(x, z) for x, _y, z in outer] + \
               [(x, z) for x, _y, z in inner[::-1]]
        out.append(_xz_prism(loop, -0.002, 0.07))
        # back plate: the outline of the dome with the apron below it
        top = [(x, z) for x, _y, z in arc(Ro + 0.006, 0.0)]
        pts = top + [(-w, top[-1][1])]
        zside = min(top[-1][1] - 0.005, -skirt + w * slope)
        pts.append((-w, zside))
        if -skirt < zside - 1e-4:
            pts.append((0.0, -skirt))
        pts += [(w, zside), (w, top[0][1])]
        out.append(_xz_prism(pts, -0.016, 0.0))
    else:
        r = Ro * (1.18 if style == "fan" else 1.0)
        top = [(x, z) for x, _y, z in arc(r, 0.0)]
        ww = max(w, r * math.sin(b) + 0.008)
        # the arc, then the apron below it
        pts = top + [(-ww, top[-1][1])]
        zside = min(top[-1][1] - 0.005, -skirt + ww * slope)
        pts.append((-ww, zside))
        if -skirt < zside - 1e-4:
            pts.append((0.0, -skirt))
        pts += [(ww, zside), (ww, top[0][1])]
        out.append(_xz_prism(pts, -0.014, 0.0))
        if style == "fan":                   # a fan of ribs on the front
            hub = 0.035
            out.append(_xz_prism([(hub * math.cos(math.radians(a2)),
                                   hub * math.sin(math.radians(a2)) + z0)
                                  for a2 in range(0, 181, 15)],
                                 -0.024, -0.013))
            for j in range(7):
                ang = math.radians(15 + 150 * j / 6)
                ca, sa = math.cos(ang), math.sin(ang)
                r1, r2 = hub + 0.006, r * 0.93
                h1, h2 = 0.004, 0.011
                quad = [(ca * r1 - sa * h1, sa * r1 + ca * h1 + z0),
                        (ca * r1 + sa * h1, sa * r1 - ca * h1 + z0),
                        (ca * r2 + sa * h2, sa * r2 - ca * h2 + z0),
                        (ca * r2 - sa * h2, sa * r2 + ca * h2 + z0)]
                out.append(_xz_prism(quad, -0.022, -0.013))
    return out


MONO_DROP = 0.06               # m: apron of a mono-pitch ridge tile below the roof


def mono_tile_solid(spec, detail, x0, x1, y0, ext, drop, clamp=None,
                    side=None):
    """Mono-pitch ridge tile («Pultfirstziegel»): the tile's own profile
    runs on past its head by ``ext``, turns down round the top edge and
    ends in an apron ``drop`` below the tile frame — the wave of the tile
    turns with it, so the apron shows the tile's profile from the front.
    Plate from ``y0`` (0 = a whole tile; Lt = only the turned-down head,
    for the corner over a verge tile). ``clamp``: x range of the profile
    (outside it the profile runs on flat, over a verge lip)."""
    W, Wt, Lt, t, A = spec["W"], spec["Wt"], spec["Lt"], spec["t"], spec["A"]
    prof = spec["prof"]
    lo, hi = clamp if clamp else (x0, x1)

    def h(x):                                  # underside of the plate
        x = min(max(x, lo), hi)
        if x < -1e-9:                          # side lock under the neighbour
            return _profile(prof, (x + W) / W, A) - t - 0.002
        return _profile(prof, x / W, A)

    xs = _samples(spec, detail, x0, x1)
    hs = [h(x) for x in xs]
    R0 = 0.012 + max(0.0, -min(hs))            # bend radius at h = 0
    zc = -R0
    zbot = min(-drop, zc - 0.01)
    Ye = Lt + ext
    nb = 7

    def section(kind, f=0.0):
        bot, top = [], []
        for x, hh in zip(xs, hs):
            rb = hh - zc
            rt = rb + t
            if kind == "tail":
                bot.append((x, y0, hh))
                top.append((x, y0, hh + t))
            elif kind == "bend":
                bot.append((x, Ye + rb * math.sin(f), zc + rb * math.cos(f)))
                top.append((x, Ye + rt * math.sin(f), zc + rt * math.cos(f)))
            else:                              # the lower edge of the apron
                bot.append((x, Ye + rb, zbot))
                top.append((x, Ye + rt, zbot))
        return bot + top[::-1]

    secs = [section("tail")]
    for i in range(nb + 1):
        secs.append(section("bend", 0.5 * math.pi * i / nb))
    secs.append(section("lip"))
    out = [_loft(secs)]
    if side:
        # over a verge: a side cheek from the verge tile's lip up into the
        # turned-down head, so the corner is closed
        xe = x0 if side == "l" else x1
        hh = h(xe)
        rt = hh - zc + t
        poly = [(y0, -VERGE_DEPTH - 0.01), (y0, hh + t), (Ye, hh + t)]
        for i in range(1, nb + 1):
            f = 0.5 * math.pi * i / nb
            poly.append((Ye + rt * math.sin(f), zc + rt * math.cos(f)))
        poly.append((Ye + rt, zbot))
        poly = [(z, y) for y, z in poly]     # (z, y) in the yz plane
        xa, xb = (xe, xe + t) if side == "l" else (xe - t, xe)
        V, F = [], []
        m = len(poly)
        V = [(xa, y, z) for z, y in poly] + [(xb, y, z) for z, y in poly]
        F = [list(range(m - 1, -1, -1)), list(range(m, 2 * m))]
        for i in range(m):
            j = (i + 1) % m
            F.append([i, j, m + j, m + i])
        out.append(Solid(V, F).fix_orientation())
    return out


def mono_solid(spec, length, leg=0.16, lip=0.09):
    """Mono-pitch ridge tile: a leg over the top course and a lip down the
    front, along y. x > 0 = over the roof, x < 0 = outside."""
    t = spec["t"]
    h = spec["A"] + spec["t"] + 0.006
    poly = [(-t, -lip), (0.0, -lip), (0.0, h), (leg, h),
            (leg, h + t), (-t, h + t)]
    poly = [(-x, z) for x, z in poly]       # x > 0 outside, as built below
    return _xz_prism(poly, 0.0, length)


# ---- conversions ------------------------------------------------------------

def _poly_tris(pts3):
    """Triangles (local indices) of one planar polygon."""
    n = len(pts3)
    if n == 3:
        return [(0, 1, 2)]
    if n == 4:
        return [(0, 1, 2), (0, 2, 3)]
    import numpy as np
    P = np.asarray(pts3, float)
    nrm = np.zeros(3)
    for i in range(n):
        a, b = P[i], P[(i + 1) % n]
        nrm += np.array([(a[1] - b[1]) * (a[2] + b[2]),
                         (a[2] - b[2]) * (a[0] + b[0]),
                         (a[0] - b[0]) * (a[1] + b[1])])
    k = int(np.argmax(np.abs(nrm)))
    i0, i1 = [(1, 2), (2, 0), (0, 1)][k]
    xy = P[:, [i0, i1]]
    if nrm[k] < 0:
        xy = xy[:, ::-1]
    try:
        import manifold3d as mf
        tri = mf.triangulate([np.ascontiguousarray(xy)])
        return [tuple(int(v) for v in r) for r in tri]
    except Exception:  # noqa: BLE001
        return [(0, i, i + 1) for i in range(1, n - 1)]


def solid_to_manifold(solids):
    """A list of Solids → one manifold3d.Manifold (union), or None."""
    try:
        import manifold3d as mf
        import numpy as np
    except Exception:  # noqa: BLE001
        return None
    parts = []
    for s in solids:
        tris = []
        for f in s.F:
            for a, b, c in _poly_tris([s.V[i] for i in f]):
                tris.append((f[a], f[b], f[c]))
        mesh = mf.Mesh(vert_properties=np.asarray(s.V, dtype=np.float32),
                       tri_verts=np.asarray(tris, dtype=np.uint32))
        m = mf.Manifold(mesh)
        if m.status() != mf.Error.NoError or m.is_empty():
            return None
        parts.append(m)
    if not parts:
        return None
    if len(parts) == 1:
        return parts[0]
    return mf.Manifold.batch_boolean(parts, mf.OpType.Add)


def _polys_of(solids):
    """Solids → list of polygons (each a list of (x, y, z))."""
    out = []
    for s in solids:
        for f in s.F:
            out.append([tuple(s.V[i]) for i in f])
    return out


def mesh_from_polys(polys, attrs, soft_deg=95.0):
    """IngeTrazo Mesh from polygons; edges between faces that meet flatter
    than ``soft_deg`` are soft (a curved tile looks round)."""
    import numpy as np
    from core.mesh import Mesh
    mesh = Mesh()
    if not polys:
        return mesh
    pos = np.asarray([p for poly in polys for p in poly], dtype=float)
    sizes = np.asarray([len(poly) for poly in polys], dtype=np.int64)
    mesh.add_faces_bulk(pos, sizes, np.ones(len(sizes), dtype=np.int64),
                        [dict(attrs) for _ in polys] if attrs else None)
    soften(mesh, soft_deg)
    return mesh


def _soften_fast(mesh, pos, sizes, soft_deg=35.0):
    """``soften`` with the normals from the arrays the faces were made of
    (same order as ``mesh.faces``)."""
    import numpy as np
    starts = np.concatenate([[0], np.cumsum(sizes)[:-1]])
    a = pos[starts]
    b = pos[starts + 1]
    c = pos[starts + 2]
    N = np.cross(b - a, c - a)
    ln = np.linalg.norm(N, axis=1)
    ln[ln < 1e-15] = 1.0
    N = N / ln[:, None]
    if len(mesh.faces) != len(N):
        soften(mesh, soft_deg)
        return
    index = {id(f): i for i, f in enumerate(mesh.faces)}
    lim = math.cos(math.radians(soft_deg))
    for e in mesh.edges:
        fs = e.faces
        if len(fs) != 2:
            continue
        i, j = index.get(id(fs[0])), index.get(id(fs[1]))
        if i is None or j is None:
            continue
        if float(N[i] @ N[j]) > lim:
            e.soft = True


def soften(mesh, soft_deg=35.0):
    lim = math.cos(math.radians(soft_deg))
    normals = {}
    for e in mesh.edges:
        fs = e.faces
        if len(fs) != 2:
            continue
        ns = []
        for f in fs:
            n = normals.get(id(f))
            if n is None:
                q = f.normal()
                ln = math.sqrt(q.x() ** 2 + q.y() ** 2 + q.z() ** 2) or 1.0
                n = (q.x() / ln, q.y() / ln, q.z() / ln)
                normals[id(f)] = n
            ns.append(n)
        dot = sum(a * b for a, b in zip(ns[0], ns[1]))
        if dot > lim:
            e.soft = True


# ---------------------------------------------------------------------------
# Custom tile
# ---------------------------------------------------------------------------

def custom_from_polys(polys, name):
    """Normalise a tile modelled lying flat (Z up): the longer horizontal
    side is its length. → custom record (polys in the tile frame)."""
    import numpy as np
    pts = np.asarray([p for poly in polys for p in poly], float)
    if not len(pts):
        raise RoofError("The tile has no faces.")
    lo, hi = pts.min(0), pts.max(0)
    ext = hi - lo
    swap = ext[0] > ext[1] * 1.05
    out = []
    for poly in polys:
        q = np.asarray(poly, float) - lo
        if swap:                            # length along x → along y
            q = np.stack([q[:, 1], ext[0] - q[:, 0], q[:, 2]], 1)
        out.append(q)
    Wt = float(ext[1] if swap else ext[0])
    Lt = float(ext[0] if swap else ext[1])
    H = float(ext[2])
    if Wt < 0.02 or Lt < 0.02:
        raise RoofError("The tile is too small (under 2 cm).")
    return {"name": name, "Wt": round(Wt, 5), "Lt": round(Lt, 5),
            "H": round(H, 5),
            "polys": [[[round(float(v), 5) for v in p] for p in q]
                      for q in out]}


def custom_from_scene(scene, name="Custom tile"):
    from core.group import Group, world_mesh
    from core.mesh import Face
    polys = []
    for ent in scene.selection:
        if isinstance(ent, Face):
            fs = [ent]
        elif isinstance(ent, Group):
            if (getattr(ent, "ext", None) or {}).get(KEY):
                continue
            fs = list(world_mesh(ent).faces)
        else:
            continue
        for f in fs:
            if f.holes:
                for tri in f.triangulate():
                    polys.append([(v.x(), v.y(), v.z()) for v in tri])
            else:
                polys.append([(v.x(), v.y(), v.z()) for v in f.vertices])
    if not polys:
        raise RoofError("Select the tile (a group or its faces) first.")
    return custom_from_polys(polys, name)


def custom_from_file(path):
    from pathlib import Path
    from core.scene import Scene
    from core.group import world_mesh
    path = Path(path)
    sc = Scene()
    if path.suffix.lower() == ".igz":
        from formats import igz
        igz.load_into(sc, path)
    elif path.suffix.lower() == ".obj":
        from formats import obj
        obj.load_obj(sc, path)
    else:
        raise RoofError("Only .igz and .obj files.")
    polys = []
    meshes = [sc.loose_mesh] + [world_mesh(g) for g in sc.groups]
    for m in meshes:
        for f in m.faces:
            if f.holes:
                for tri in f.triangulate():
                    polys.append([(v.x(), v.y(), v.z()) for v in tri])
            else:
                polys.append([(v.x(), v.y(), v.z()) for v in f.vertices])
    rec = custom_from_polys(polys, path.stem)
    return rec


def custom_solids(spec, rec):
    """The custom tile placed in the tile frame: right edge at x = W."""
    dx = spec["W"] - rec["Wt"]
    polys = [[(p[0] + dx, p[1], p[2]) for p in poly] for poly in rec["polys"]]
    V, F, idx = [], [], {}
    for poly in polys:
        f = []
        for p in poly:
            k = (round(p[0], 6), round(p[1], 6), round(p[2], 6))
            if k not in idx:
                idx[k] = len(V)
                V.append(k)
            f.append(idx[k])
        F.append(f)
    return [Solid(V, F)]


# ---------------------------------------------------------------------------
# Source: roof faces from the selection
# ---------------------------------------------------------------------------

def _p3(v):
    return (float(v.x()), float(v.y()), float(v.z()))


def roof_data(group):
    data = (getattr(group, "ext", None) or {}).get(KEY)
    return data if isinstance(data, dict) and "faces" in data else None


def _newell(pts):
    nx = ny = nz = 0.0
    n = len(pts)
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        nx += (a[1] - b[1]) * (a[2] + b[2])
        ny += (a[2] - b[2]) * (a[0] + b[0])
        nz += (a[0] - b[0]) * (a[1] + b[1])
    ln = math.sqrt(nx * nx + ny * ny + nz * nz)
    if ln < 1e-12:
        return None
    return (nx / ln, ny / ln, nz / ln)


def gather(scene):
    """``{"faces": [{"outer": [(x,y,z)…], "holes": [[…]]}, …]}`` — the
    sloped faces in the selection (loose faces, faces inside selected
    groups; a roof covering made by this plugin is skipped)."""
    from core.group import Group, world_mesh
    from core.mesh import Face
    lim = math.sin(math.radians(MIN_TILT))
    out = []
    seen = set()

    def add(f, loose):
        outer = [_p3(v) for v in f.vertices]
        holes = [[_p3(v) for v in h] for h in (f.holes or [])]
        n = _newell(outer)
        if n is None:
            return None
        k = tuple(sorted((round(p[0], 4), round(p[1], 4), round(p[2], 4))
                         for p in outer))
        if k in seen:
            return None
        rec = {"outer": outer, "holes": holes, "n": n}
        return k, rec

    for ent in scene.selection:
        if isinstance(ent, Face):
            r = add(ent, True)
            if r and abs(r[1]["n"][2]) > lim:
                seen.add(r[0])
                out.append(r[1])
        elif isinstance(ent, Group) and roof_data(ent) is None:
            ups, downs = [], []
            for f in world_mesh(ent).faces:
                r = add(f, False)
                if not r:
                    continue
                if r[1]["n"][2] > lim:
                    ups.append(r)
                elif r[1]["n"][2] < -lim:
                    downs.append(r)
            for k, rec in (ups or downs):   # a thick roof: its top only
                if k not in seen:
                    seen.add(k)
                    out.append(rec)
    faces = []
    for rec in out:
        faces.append({"outer": rec["outer"], "holes": rec["holes"]})
    shapes = [ent.uid for ent in scene.selection
              if isinstance(ent, Group) and shape_data(ent) is not None]
    return {"faces": faces, "shapes": shapes}


# ---------------------------------------------------------------------------
# Analysis: planes, their outline and what every edge is
# ---------------------------------------------------------------------------

EDGE_NAMES = {"eave": "eave", "ridge": "ridge", "hip": "hip",
              "valley": "valley", "verge_l": "verge", "verge_r": "verge",
              "top": "mono-pitch ridge", "break_low": "break",
              "break_high": "break", "abut": "abutment", "cut": "cut edge",
              "seam": "seam"}


def _v(a, b):
    return (b[0] - a[0], b[1] - a[1], b[2] - a[2])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _norm(a):
    ln = math.sqrt(_dot(a, a))
    return (a[0] / ln, a[1] / ln, a[2] / ln) if ln > 1e-15 else (0, 0, 0)


def _add(a, b, s=1.0):
    return (a[0] + b[0] * s, a[1] + b[1] * s, a[2] + b[2] * s)


def _area2(loop):
    s = 0.0
    n = len(loop)
    for i in range(n):
        x0, y0 = loop[i]
        x1, y1 = loop[(i + 1) % n]
        s += x0 * y1 - x1 * y0
    return 0.5 * s


class Plane:
    """One roof plane: frame (O, ex along the eave, ey up the slope, n),
    the region (CrossSection, plane coordinates) and its boundary pieces."""

    def __init__(self, n, O):
        self.n = n
        up = _add((0.0, 0.0, 1.0), n, -n[2])
        self.ey = _norm(up)
        self.ex = _cross(self.ey, n)
        self.O = O
        self.faces = []                     # 2D loops per face
        self.region = None
        self.loops = []                     # 2D loops of the union
        self.pieces = []                    # dicts, see classify
        self.tilt = math.degrees(math.acos(max(-1.0, min(1.0, n[2]))))

    def to2(self, p):
        d = _v(self.O, p)
        return (_dot(d, self.ex), _dot(d, self.ey))

    def to3(self, q, z=0.0):
        return (self.O[0] + self.ex[0] * q[0] + self.ey[0] * q[1] + self.n[0] * z,
                self.O[1] + self.ex[1] * q[0] + self.ey[1] * q[1] + self.n[1] * z,
                self.O[2] + self.ex[2] * q[0] + self.ey[2] * q[1] + self.n[2] * z)

    def matrix(self):
        """4×4 (numpy) plane → world."""
        import numpy as np
        M = np.eye(4)
        M[:3, 0], M[:3, 1], M[:3, 2], M[:3, 3] = self.ex, self.ey, self.n, self.O
        return M


def build_planes(data):
    import manifold3d as mf
    lim = math.sin(math.radians(MIN_TILT))
    hi = math.cos(math.radians(FLAT_TILT))
    planes = []
    flat = steep = 0
    for f in data["faces"]:
        outer = [tuple(p) for p in f["outer"]]
        n = _newell(outer)
        if n is None:
            continue
        holes = [[tuple(p) for p in h] for h in f.get("holes") or []]
        if n[2] < 0:
            n = (-n[0], -n[1], -n[2])
        if n[2] > hi:
            flat += 1                       # flat: not a roof face
            continue
        if n[2] < lim:
            steep += 1                      # vertical: a wall
            continue
        pl = None
        for q in planes:
            if _dot(q.n, n) > math.cos(math.radians(0.6)) and \
                    abs(_dot(q.n, outer[0]) - _dot(q.n, q.O)) < 0.005:
                pl = q
                break
        if pl is None:
            pl = Plane(n, outer[0])
            planes.append(pl)
        o2 = [pl.to2(p) for p in outer]
        if _area2(o2) < 0:
            o2.reverse()
        loops = [o2]
        for h in holes:
            h2 = [pl.to2(p) for p in h]
            if _area2(h2) > 0:
                h2.reverse()
            loops.append(h2)
        pl.faces.append(loops)
    if not planes:
        if flat:
            raise RoofError("The selected roof is level (0°) — tiles are laid "
                            "down the fall of the roof, a level face has none. "
                            "Give it a little Pitch.")
        raise RoofError("No sloped faces in the selection — select the roof "
                        "faces (or the group that holds them).")
    for pl in planes:
        parts = [mf.CrossSection(lp, mf.FillRule.Positive) for lp in pl.faces]
        cs = parts[0] if len(parts) == 1 else \
            mf.CrossSection.batch_boolean(parts, mf.OpType.Add)
        cs = cs.simplify(0.0005) if hasattr(cs, "simplify") else cs
        pl.region = cs
        pl.loops = [[(float(x), float(y)) for x, y in lp]
                    for lp in cs.to_polygons() if len(lp) >= 3]
        pl.area = float(cs.area())
        pl.region = None                    # no native objects kept around
    return planes


def _seg_dist(p, a, b):
    """Distance of p from segment ab (3D) and its parameter."""
    ab = _v(a, b)
    L2 = _dot(ab, ab)
    if L2 < 1e-18:
        return math.sqrt(_dot(_v(a, p), _v(a, p))), 0.0
    t = _dot(_v(a, p), ab) / L2
    tc = min(1.0, max(0.0, t))
    q = _add(a, ab, tc)
    d = _v(q, p)
    return math.sqrt(_dot(d, d)), t


def classify(planes):
    """Split every outline edge where another plane's edge starts or ends,
    then tell each piece what it is (eave, ridge, hip, valley, verge …)."""
    # all edges in 3D: (plane index, a3, b3, inward3, hole?)
    edges = []
    for i, pl in enumerate(planes):
        for lp in pl.loops:
            hole = _area2(lp) < 0
            n = len(lp)
            for k in range(n):
                a2, b2 = lp[k], lp[(k + 1) % n]
                dx, dy = b2[0] - a2[0], b2[1] - a2[1]
                ln = math.hypot(dx, dy)
                if ln < 1e-6:
                    continue
                inw2 = (-dy / ln, dx / ln)
                inw3 = _add(_add((0, 0, 0), pl.ex, inw2[0]), pl.ey, inw2[1])
                edges.append((i, pl.to3(a2), pl.to3(b2), inw3, hole, a2, b2))
    for pl in planes:
        pl.pieces = []
    horiz = 0.05                            # ≈ 3°
    for (i, a3, b3, inw3, hole, a2, b2) in edges:
        pl = planes[i]
        L = math.sqrt(_dot(_v(a3, b3), _v(a3, b3)))
        ts = {0.0, 1.0}
        for (j, c3, d3, _w, _h, _c2, _d2) in edges:
            if j == i:
                continue
            for q in (c3, d3):
                dist, t = _seg_dist(q, a3, b3)
                if dist < TOL and TOL / L < t < 1 - TOL / L:
                    ts.add(t)
        ts = sorted(ts)
        for t0, t1 in zip(ts, ts[1:]):
            if (t1 - t0) * L < 1e-4:
                continue
            pa2 = (a2[0] + (b2[0] - a2[0]) * t0, a2[1] + (b2[1] - a2[1]) * t0)
            pb2 = (a2[0] + (b2[0] - a2[0]) * t1, a2[1] + (b2[1] - a2[1]) * t1)
            pa3, pb3 = pl.to3(pa2), pl.to3(pb2)
            mid = _add(pa3, _v(pa3, pb3), 0.5)
            nb = None
            for (j, c3, d3, w3, _h, _c2, _d2) in edges:
                if j == i:
                    continue
                dist, t = _seg_dist(mid, c3, d3)
                if dist < TOL and 0.0 <= t <= 1.0:
                    dirA = _norm(_v(pa3, pb3))
                    dirB = _norm(_v(c3, d3))
                    if abs(_dot(dirA, dirB)) > 0.999:
                        nb = (j, w3)
                        break
            dx, dy = pb2[0] - pa2[0], pb2[1] - pa2[1]
            ln = math.hypot(dx, dy)
            inw2 = (-dy / ln, dx / ln)
            is_h = abs(dy) < horiz * ln
            is_v = abs(dx) < horiz * ln
            bottom = inw2[1] > 0
            if hole:
                kind = "cut"
            elif nb is not None:
                j, w3 = nb
                s = _dot(pl.n, w3)
                other = planes[j]
                if abs(s) < 0.02:
                    kind = "seam"
                elif s < 0:                 # convex
                    if is_h:
                        if bottom:
                            kind = "break_low"
                        else:
                            ob = _dot(w3, other.ey) > 0     # B's inward up?
                            kind = "ridge" if not ob else "break_high"
                    else:
                        kind = "hip"
                else:                       # concave
                    if is_h:
                        kind = "eave" if bottom else "abut"
                    else:
                        kind = "valley"
            else:
                if is_h:
                    kind = "eave" if bottom else "top"
                elif is_v:
                    kind = "verge_l" if inw2[0] > 0 else "verge_r"
                else:
                    kind = "cut"
            pl.pieces.append({"a": pa2, "b": pb2, "a3": pa3, "b3": pb3,
                              "kind": kind, "nb": nb[0] if nb else None,
                              "hole": hole, "inw": inw2})
    return planes


def summary(planes):
    cnt = {}
    for pl in planes:
        for pc in pl.pieces:
            k = EDGE_NAMES.get(pc["kind"], pc["kind"])
            cnt[k] = cnt.get(k, 0) + 1
    return cnt


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

def _offsets(p, spec):
    vo = p["verge_ov"] + (0.08 + spec["Wt"] - spec["W"]
                          if p["verge"] == "tiles" else 0.0)
    return {"eave": p["eave_ov"], "break_low": p["eave_ov"],
            "ridge": 0.0, "top": 0.0, "break_high": 0.0,
            "abut": -p["cut_gap"], "hip": -p["hip_gap"],
            "valley": -p["valley_gap"], "verge_l": vo, "verge_r": vo,
            "cut": -p["cut_gap"], "seam": 0.0}


def _offset_loop(pieces, offs):
    """Each piece's line moved outward by its own distance; corners where
    the moved lines meet (two points where two parallel lines step)."""
    n = len(pieces)
    lines = []
    for pc in pieces:
        (ax, ay), (bx, by) = pc["a"], pc["b"]
        dx, dy = bx - ax, by - ay
        ln = math.hypot(dx, dy)
        nx, ny = dy / ln, -dx / ln          # outward (right of the loop)
        d = offs.get(pc["kind"], 0.0)
        lines.append(((ax + nx * d, ay + ny * d), (bx + nx * d, by + ny * d),
                      (dx / ln, dy / ln), d))
    out = []
    for k in range(n):
        p0, p1, d0, o0 = lines[k - 1]
        q0, q1, d1, o1 = lines[k]
        cr = d0[0] * d1[1] - d0[1] * d1[0]
        if abs(cr) < 1e-6:
            if abs(o0 - o1) < 1e-9:
                out.append(q0)
            else:
                out.append(p1)
                out.append(q0)
            continue
        # p1 + s*d0 == q0 + u*d1
        wx, wy = q0[0] - p1[0], q0[1] - p1[1]
        s = (wx * d1[1] - wy * d1[0]) / cr
        x, y = p1[0] + d0[0] * s, p1[1] + d0[1] * s
        corner = pieces[k]["a"]
        lim = 6.0 * max(abs(o0), abs(o1), 0.01)
        if math.hypot(x - corner[0], y - corner[1]) > lim:
            out.append(p1)                  # bevel a very sharp corner
            out.append(q0)
        else:
            out.append((x, y))
    return out


def _loops_of_pieces(pl):
    """Pieces grouped back into their loops (consecutive, closed)."""
    loops, cur = [], []
    for pc in pl.pieces:
        if cur and (abs(cur[-1]["b"][0] - pc["a"][0]) > 1e-7 or
                    abs(cur[-1]["b"][1] - pc["a"][1]) > 1e-7):
            loops.append(cur)
            cur = []
        cur.append(pc)
        if abs(cur[0]["a"][0] - pc["b"][0]) < 1e-7 and \
                abs(cur[0]["a"][1] - pc["b"][1]) < 1e-7:
            loops.append(cur)
            cur = []
    if cur:
        loops.append(cur)
    return loops


def lay_region(pl, p, spec):
    import manifold3d as mf
    offs = _offsets(p, spec)
    loops = [_offset_loop(lp, offs) for lp in _loops_of_pieces(pl)]
    loops = [lp for lp in loops if len(lp) >= 3]
    cs = mf.CrossSection(loops, mf.FillRule.Positive)
    return cs


def _rows(pl, p, spec):
    eaves = [pc for pc in pl.pieces if pc["kind"] in ("eave", "break_low")]
    ys = [y for lp in pl.loops for _x, y in lp]
    ymin, ymax = min(ys), max(ys)
    y0 = (min(min(pc["a"][1], pc["b"][1]) for pc in eaves) - p["eave_ov"]
          if eaves else ymin)
    tops = [pc for pc in pl.pieces
            if pc["kind"] in ("ridge", "top", "break_high", "abut")]
    ytop = max(max(pc["a"][1], pc["b"][1]) for pc in tops) if tops else ymax
    gap = p["ridge_gap"] if tops else 0.0
    Lt, Lmin, Lmax = spec["Lt"], spec["Lmin"], spec["Lmax"]
    D = ytop - gap - y0 - Lt
    if D <= 1e-6:
        return y0, Lmax, 1
    m = max(1, int(math.ceil(D / Lmax - 1e-9)))
    L = D / m
    if L < Lmin:
        L = Lmin
        m = int(math.ceil(D / L - 1e-9))
    return y0, L, m + 1


def _columns(pl, p, spec, rows_y):
    """[(x, width, kind)] per row-parity: kind tile / verge_l / verge_r."""
    W = spec["W"]
    xs = [x for lp in pl.loops for x, _y in lp]
    xmin, xmax = min(xs), max(xs)
    vl = [pc for pc in pl.pieces if pc["kind"] == "verge_l"]
    vr = [pc for pc in pl.pieces if pc["kind"] == "verge_r"]
    ov = p["verge_ov"]
    tiles = p["verge"] == "tiles"
    info = {"stretch": 1.0}
    if vl and vr:
        X0 = min(min(pc["a"][0], pc["b"][0]) for pc in vl) - ov
        X1 = max(max(pc["a"][0], pc["b"][0]) for pc in vr) + ov
        if tiles:
            # inner verges (an L, a step in the roof) want a whole number of
            # columns too: pick the count whose stretch fits them best
            others = [pc["a"][0] - ov - X0 for pc in vl
                      if pc["a"][0] - ov - X0 > 0.5 * W] + \
                     [pc["a"][0] + ov - X0 for pc in vr
                      if X1 - X0 - (pc["a"][0] + ov - X0) > 0.5 * W]
            n0 = max(1, int(round((X1 - X0) / W)))
            best = None
            for n in range(max(1, n0 - 3), n0 + 4):
                cw = (X1 - X0) / n
                if abs(cw / W - 1.0) > 0.03 and n != n0:
                    continue
                miss = sum(abs(d / cw - round(d / cw)) * cw for d in others)
                score = miss + 2.0 * abs(cw - W)
                if best is None or score < best[0]:
                    best = (score, n)
            n = best[1]
            s = (X1 - X0) / (n * W)
            info["stretch"] = s
            return X0, W * s, n, info
        n = int(math.ceil((X1 - X0) / W)) + 1
        return X0, W, n, info
    if vl:
        X0 = min(min(pc["a"][0], pc["b"][0]) for pc in vl) - ov
        n = int(math.ceil((xmax - X0) / W)) + 2
        return X0, W, n, info
    if vr:
        X1 = max(max(pc["a"][0], pc["b"][0]) for pc in vr) + ov
        n = int(math.ceil((X1 - xmin) / W)) + 2
        return X1 - n * W, W, n, info
    eaves = [pc for pc in pl.pieces if pc["kind"] == "eave"]
    if eaves:
        pc = max(eaves, key=lambda q: abs(q["b"][0] - q["a"][0]))
        xc = 0.5 * (pc["a"][0] + pc["b"][0])
    else:
        xc = 0.5 * (xmin + xmax)
    k = int(math.ceil((xc - W / 2 - xmin) / W)) + 1
    X0 = xc - W / 2 - k * W
    n = int(math.ceil((xmax - X0) / W)) + 2
    return X0, W, n, info


def _np_matrix(T):
    from PySide6.QtGui import QMatrix4x4
    return QMatrix4x4(*[float(v) for v in T.reshape(-1)])


def _tilt_local(spec, lift):
    """Tile frame: rotate about the head so the tail rises by ``lift``."""
    import numpy as np
    Lt = spec["Lt"]
    th = math.atan2(lift, Lt)
    c, s = math.cos(th), math.sin(th)
    R = np.eye(4)
    R[1, 1], R[1, 2], R[2, 1], R[2, 2] = c, s, -s, c
    T1 = np.eye(4)
    T1[1, 3] = -Lt
    T2 = np.eye(4)
    T2[1, 3] = Lt
    return T2 @ R @ T1


def _rect_hits(rects, ea, eb):
    """For tile rectangles (k×4: x0 y0 x1 y1) → bool: some region edge
    crosses it."""
    import numpy as np
    hit = np.zeros(len(rects), dtype=bool)
    if not len(ea):
        return hit
    ex0 = np.minimum(ea[:, 0], eb[:, 0])
    ex1 = np.maximum(ea[:, 0], eb[:, 0])
    ey0 = np.minimum(ea[:, 1], eb[:, 1])
    ey1 = np.maximum(ea[:, 1], eb[:, 1])
    dx = (eb[:, 0] - ea[:, 0])
    dy = (eb[:, 1] - ea[:, 1])
    for s in range(0, len(rects), 512):
        R = rects[s:s + 512]
        ov = ((ex1[None, :] >= R[:, None, 0]) & (ex0[None, :] <= R[:, None, 2])
              & (ey1[None, :] >= R[:, None, 1]) & (ey0[None, :] <= R[:, None, 3]))
        sides = []
        for cx, cy in ((0, 1), (2, 1), (2, 3), (0, 3)):
            sides.append(dx[None, :] * (R[:, None, cy] - ea[None, :, 1])
                         - dy[None, :] * (R[:, None, cx] - ea[None, :, 0]))
        S = np.stack(sides, 0)
        straddle = ~(np.all(S > 0, 0) | np.all(S < 0, 0))
        hit[s:s + 512] = np.any(ov & straddle, 1)
    return hit


def _inside(points, loops):
    """Even-odd point in polygon for (k×2) points against loops."""
    import numpy as np
    P = np.asarray(points, float)
    res = np.zeros(len(P), dtype=bool)
    for lp in loops:
        L = np.asarray(lp, float)
        A, B = L, np.roll(L, -1, 0)
        for a, b in zip(A, B):
            cond = (a[1] > P[:, 1]) != (b[1] > P[:, 1])
            with np.errstate(divide="ignore", invalid="ignore"):
                xi = a[0] + (P[:, 1] - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
            res ^= cond & (P[:, 0] < xi)
    return res


def _clip_triangles(tris, region_tris):
    """Fallback cut for a tile that is no closed solid: every triangle
    clipped against every region triangle (convex) — no caps."""
    out = []
    for rt in region_tris:
        planes = []
        for k in range(3):
            a, b = rt[k], rt[(k + 1) % 3]
            planes.append((a, (-(b[1] - a[1]), b[0] - a[0])))   # inward
        for tri in tris:
            poly = [tuple(v) for v in tri]
            for a, nrm in planes:
                if not poly:
                    break
                res = []
                m = len(poly)
                for i in range(m):
                    P, Q = poly[i], poly[(i + 1) % m]
                    dp = (P[0] - a[0]) * nrm[0] + (P[1] - a[1]) * nrm[1]
                    dq = (Q[0] - a[0]) * nrm[0] + (Q[1] - a[1]) * nrm[1]
                    if dp >= 0:
                        res.append(P)
                    if (dp >= 0) != (dq >= 0):
                        t = dp / (dp - dq)
                        res.append(tuple(P[j] + (Q[j] - P[j]) * t
                                         for j in range(3)))
                poly = res
            if len(poly) >= 3:
                for i in range(1, len(poly) - 1):
                    out.append((poly[0], poly[i], poly[i + 1]))
    return out


class Protos:
    """The shared tiles of one run, built once: Solid lists, manifolds and
    IngeTrazo meshes."""

    def __init__(self, spec, p, attrs):
        self.spec, self.p, self.attrs = spec, p, attrs
        self._solids, self._mf, self._mesh = {}, {}, {}

    def solids(self, kind):
        if kind not in self._solids:
            sp, det = self.spec, self.p["detail"]
            if kind in ("tile", "verge_l", "verge_r"):
                if sp["prof"] == "custom":
                    s = custom_solids(sp, self.p["custom"])
                else:
                    s = tile_solids(sp, det, kind)
            elif kind == "ridge":
                s = [ridge_solid(sp, det)]
            elif kind.startswith("mono"):
                parts = kind.split(":")
                ext, drop = float(parts[1]), float(parts[2])
                W, Wt, Lt, t = sp["W"], sp["Wt"], sp["Lt"], sp["t"]
                R = max(0.012, 1.2 * t)        # the verge tile's bend
                if parts[0] == "mono":
                    s = mono_tile_solid(sp, det, W - Wt, W, 0.0, ext, drop)
                elif parts[0] == "mono_l":
                    s = tile_solids(sp, det, "verge_l") + mono_tile_solid(
                        sp, det, -t / 2, W, Lt - 0.002, ext, drop,
                        clamp=(0.0, W), side="l")
                else:
                    s = tile_solids(sp, det, "verge_r") + mono_tile_solid(
                        sp, det, W - Wt, W + t / 2, Lt - 0.002, ext, drop,
                        clamp=(W - Wt, W), side="r")
            elif kind.startswith("ridge_end"):
                parts = kind.split(":")
                skirt = float(parts[1]) if len(parts) > 1 else 0.0
                slope = float(parts[2]) if len(parts) > 2 else 0.8
                style = parts[3] if len(parts) > 3 else "stone"
                s = ridge_end_solids(sp, det, skirt, slope, style)
            else:
                raise KeyError(kind)
            self._solids[kind] = s
        return self._solids[kind]

    def manifold(self, kind):
        if kind not in self._mf:
            self._mf[kind] = solid_to_manifold(self.solids(kind))
        return self._mf[kind]

    def mesh(self, kind, L=None):
        """The shared mesh of ``kind``; with ``L`` (3×3) already turned and
        stretched into place, so its instances only move. IngeTrazo bakes the
        shading of a component from its definition — a turned instance would
        keep the light of the untilted tile; tiles of one roof plane share
        one turned definition instead."""
        key = (kind, None if L is None else
               tuple(round(float(v), 9) for v in L.reshape(-1)))
        if key not in self._mesh:
            polys = _polys_of(self.solids(kind))
            if L is not None:
                import numpy as np
                polys = [[tuple(float(c) for c in (np.asarray(q) @ L.T))
                          for q in poly] for poly in polys]
            self._mesh[key] = mesh_from_polys(polys, self.attrs)
        return self._mesh[key]

    def triangles(self, kind):
        out = []
        for s in self.solids(kind):
            for f in s.F:
                pts = [s.V[i] for i in f]
                for a, b, c in _poly_tris(pts):
                    out.append((pts[a], pts[b], pts[c]))
        return out


def _lift(spec):
    L = max(spec["Lmin"], 0.5 * (spec["Lmin"] + spec["Lmax"]))
    return spec["t"] * spec["Lt"] / max(L, 0.02) + 0.002


def mono_tiles_ok(p, spec):
    """Mono-pitch ridges as one ridge tile per column (the tile's profile
    turned down over the edge) — for the profiled tiles; plain tiles laid
    half-bond and own tiles keep the plain mono-pitch ridge piece."""
    return bool(p["mono"]) and spec["prof"] != "custom" and not spec["half"]


def layout(planes, p, spec, protos, progress=None):
    """→ placements [(kind, 4×4 world)], cut triangles (n×3×3 world),
    flashing quads, info."""
    import numpy as np
    import manifold3d as mf
    W, Wt, Lt = spec["W"], spec["Wt"], spec["Lt"]
    lift = _lift(spec)
    tilt = _tilt_local(spec, lift)
    place, cuts, flash = [], [], []
    info = {"tiles": 0, "cut": 0, "verge": 0, "stretch": [], "gauge": [],
            "rows": 0, "area": 0.0, "dropped": 0}
    tiles_mode = p["verge"] == "tiles" and spec["prof"] != "custom"
    mono_ok = mono_tiles_ok(p, spec)
    info["mono_tiles"] = 0
    total = len(planes)
    for ip, pl in enumerate(planes):
        info["area"] += pl.area
        region = lay_region(pl, p, spec)
        rloops = [[(float(x), float(y)) for x, y in lp]
                  for lp in region.to_polygons() if len(lp) >= 3]
        if not rloops:
            continue
        ea = np.asarray([lp[k] for lp in rloops for k in range(len(lp))], float)
        eb = np.asarray([lp[(k + 1) % len(lp)] for lp in rloops
                         for k in range(len(lp))], float)
        prism = region.extrude(2.0).translate((0.0, 0.0, -1.0))
        rtris = None
        y0, L, nrows = _rows(pl, p, spec)
        X0, cw, ncols, cinfo = _columns(pl, p, spec, None)
        s = cw / W
        info["gauge"].append(L)
        info["rows"] += nrows
        if abs(s - 1.0) > 1e-6:
            info["stretch"].append(s)
        vl = [pc for pc in pl.pieces if pc["kind"] == "verge_l"]
        vr = [pc for pc in pl.pieces if pc["kind"] == "verge_r"]

        def vrange(ps):
            if not ps:
                return None
            ys = [pc["a"][1] for pc in ps] + [pc["b"][1] for pc in ps]
            return min(ys) - p["eave_ov"] - 0.01, max(ys) + 0.01

        # every verge gets its verge tiles in the column next to it — also
        # an inner verge (the step of an L), not only the outermost two
        ovv = p["verge_ov"]
        vtarget = []                          # (kind, column, y from, y to)
        for pc in vl + vr:
            ys = (pc["a"][1], pc["b"][1])
            if pc["kind"] == "verge_l":
                col = int(round((pc["a"][0] - ovv - X0) / cw))
            else:
                col = int(round((pc["a"][0] + ovv - X0) / cw)) - 1
            vtarget.append((pc["kind"], col, min(ys) - p["eave_ov"] - 0.01,
                            max(ys) + 0.01))

        def verge_kind(c, mid):
            for k, col, ya, yb in vtarget:
                if c == col and ya <= mid <= yb + Lt:
                    return k
            return None

        # mono-pitch ridges: the top course under each one turns into
        # mono-pitch ridge tiles; the courses above it there are dropped.
        # At an inner corner (the verge goes on up beside the ridge) the
        # column there is split: mono-pitch tile on the ridge side, the
        # ordinary course on the other.
        tops = []
        vo_all = _offsets(p, spec)["verge_l"] + 0.01
        if mono_ok:
            gap = p["ridge_gap"]

            def end_kind(pt, yt):
                for q in pl.pieces:
                    if q["kind"] == "top":
                        continue
                    for e1, e2 in ((q["a"], q["b"]), (q["b"], q["a"])):
                        if math.dist(e1, pt) < 1e-4:
                            return "inner" if e2[1] > yt + 0.01 else "outer"
                return "outer"

            for pc in pl.pieces:
                if pc["kind"] != "top":
                    continue
                yt = 0.5 * (pc["a"][1] + pc["b"][1])
                rt = int(math.floor((yt - gap - Lt - y0) / L + 1e-6))
                if rt < 0:
                    continue
                rt = min(rt, nrows - 1)
                ext = yt - (y0 + rt * L + Lt) + 0.015
                pa, pb = sorted((pc["a"], pc["b"]))
                xa, xb = pa[0], pb[0]
                ea_ = 0.0 if end_kind(pa, yt) == "inner" else vo_all
                eb_ = 0.0 if end_kind(pb, yt) == "inner" else vo_all
                tops.append(dict(xa=xa, xb=xb, yt=yt, rt=rt, ea=ea_, eb=eb_,
                                 sfx=":%.3f:%.3f" % (ext,
                                                     MONO_DROP + p["offset"])))

        def top_of(xc):
            """(index, whole column under the ridge, split at an inner end)"""
            xlo, xhi = xc + (W - Wt) * s, xc + cw
            xmid = xc + 0.5 * cw
            for i, t in enumerate(tops):
                if t["xa"] - 0.01 <= xmid <= t["xb"] + 0.01:
                    whole = (xlo >= t["xa"] - t["ea"] - 0.01 and
                             xhi <= t["xb"] + t["eb"] + 0.01)
                    return i, whole
                # a column mostly beside an inner end still gets its share
                if (t["ea"] == 0.0 and xlo < t["xa"] < xhi) or \
                        (t["eb"] == 0.0 and xlo < t["xb"] < xhi):
                    return i, False
            return None

        clip_cache = {}

        def top_index(xc):
            tp = top_of(xc)
            return tp[0] if tp else 0

        def clip_prism(ti, clip):
            """Cutting solid for a mono-pitch ridge tile (the region plus a
            band over the ridge, so its turned-down head is kept, ending at
            an inner corner) or for the rest of a split column."""
            key = (ti, clip[0] if clip else "mono")
            if key not in clip_cache:
                t = tops[ti]
                big = 1e3
                strip = mf.CrossSection(
                    [[(t["xa"] - t["ea"], -big), (t["xb"] + t["eb"], -big),
                      (t["xb"] + t["eb"], big), (t["xa"] - t["ea"], big)]],
                    mf.FillRule.Positive)
                if key[1] == "rest":
                    reg2 = region - strip
                else:
                    band = mf.CrossSection(
                        [[(t["xa"] - t["ea"], t["yt"] - 0.05),
                          (t["xb"] + t["eb"], t["yt"] - 0.05),
                          (t["xb"] + t["eb"], t["yt"] + 0.5),
                          (t["xa"] - t["ea"], t["yt"] + 0.5)]],
                        mf.FillRule.Positive)
                    reg2 = (region + band) ^ strip
                clip_cache[key] = reg2.extrude(2.0).translate(
                    (0.0, 0.0, -1.0))
            return clip_cache[key]

        F = pl.matrix()
        recs = []                         # kind, xc, yr, xlo, xhi, clip
        for r in range(nrows):
            yr = y0 + r * L
            shift = (0.5 * cw if (spec["half"] and r % 2) else 0.0)
            extra = 1 if spec["half"] else 0
            for c in range(-extra, ncols + extra):
                xc = X0 + c * cw + shift
                kind = "tile"
                if tiles_mode and not spec["half"]:
                    kind = verge_kind(c, yr + 0.5 * Lt) or "tile"
                clip = None
                tp = top_of(xc) if tops else None
                if tp is not None:
                    ti, whole = tp
                    t = tops[ti]
                    if r > t["rt"] and whole:
                        continue                # above the mono-pitch ridge
                    if r == t["rt"]:
                        mk = {"tile": "mono", "verge_l": "mono_l",
                              "verge_r": "mono_r"}[kind] + t["sfx"]
                        if not whole:           # the other half: a course
                            recs.append((kind, xc, yr, xc + (W - Wt) * s,
                                         xc + cw, ("rest", ti)))
                        kind, clip = mk, ("mono", ti)
                bare = kind.split(":")[0]
                xlo = xc + (W - Wt) * s if bare not in ("verge_l", "mono_l") \
                    else xc - 0.02
                xhi = xc + cw + (0.02 if bare in ("verge_r", "mono_r")
                                 else 0.0)
                recs.append((kind, xc, yr, xlo, xhi, clip))
        if not recs:
            continue
        rects = np.asarray([(a, y, b, y + Lt) for _k, _x, y, a, b, _c in recs],
                           float)
        rects[:, 1] -= 0.002
        hits = _rect_hits(rects, ea, eb)
        centers = np.stack([(rects[:, 0] + rects[:, 2]) / 2,
                            (rects[:, 1] + rects[:, 3]) / 2], 1)
        inside = _inside(centers, rloops)
        for i, (kind, xc, yr, _a, _b, clip) in enumerate(recs):
            if clip is not None and clip[0] == "mono" and \
                    tops[clip[1]]["ea"] > 0 and tops[clip[1]]["eb"] > 0:
                clip = None                     # nothing special to cut
            if clip is not None:
                hits[i] = True
            if not hits[i] and not inside[i]:
                continue
            Tl = np.eye(4)
            Tl[0, 3], Tl[1, 3], Tl[2, 3] = xc, yr, p["offset"]
            S = np.eye(4)
            S[0, 0] = s
            local = Tl @ S @ tilt
            if not hits[i]:
                place.append((kind, F @ local))
                info["tiles"] += 1
                if kind.startswith("mono"):
                    info["mono_tiles"] += 1
                if kind != "tile" and not kind.startswith("mono:"):
                    info["verge"] += 1
                continue
            # a cut tile
            m = protos.manifold(kind)
            tri = None
            pr = prism
            if kind.startswith("mono") or clip is not None:
                pr = clip_prism(clip[1] if clip else top_index(xc), clip)
            if m is not None:
                A = local[:3, :]
                cut = m.transform(np.ascontiguousarray(A)) ^ pr
                if cut.is_empty():
                    continue
                mm = cut.to_mesh()
                V = np.asarray(mm.vert_properties, float)[:, :3]
                Tv = np.asarray(mm.tri_verts, dtype=np.int64)
                tri = V[Tv]
            else:
                if rtris is None:
                    flat = [q for lp in rloops for q in lp]
                    idx = mf.triangulate([np.asarray(lp, float)
                                          for lp in rloops])
                    rtris = [[flat[a], flat[b], flat[c]] for a, b, c in idx]
                loc = []
                for t3 in protos.triangles(kind):
                    P = np.c_[np.asarray(t3, float), np.ones(3)] @ local.T
                    loc.append(P[:, :3])
                ct = _clip_triangles(loc, rtris)
                if not ct:
                    continue
                tri = np.asarray(ct, float)
            if len(tri) < 4 or _tri_area(tri) < 1e-5:
                info["dropped"] += 1
                continue
            Pw = np.c_[tri.reshape(-1, 3), np.ones(len(tri) * 3)] @ F.T
            cuts.append(Pw[:, :3].reshape(-1, 3, 3))
            info["cut"] += 1
            if kind.startswith("mono"):
                info["mono_tiles"] += 1
            if kind != "tile" and not kind.startswith("mono:"):
                info["verge"] += 1
        # valley flashing
        if p["flashing"]:
            for pc in pl.pieces:
                if pc["kind"] != "valley":
                    continue
                (ax, ay), (bx, by) = pc["a"], pc["b"]
                ix, iy = pc["inw"]
                w = 0.22
                z = p["offset"] + 0.001
                quad = [(ax, ay), (bx, by), (bx + ix * w, by + iy * w),
                        (ax + ix * w, ay + iy * w)]
                flash.append([pl.to3(q, z) for q in quad])
        # the closing of a verge cut flush
        flash.extend(_verge_finish(pl, p, spec))
        # flashing round holes (skylight, chimney, dormer opening)
        if p["holeflash"]:
            for tri in _hole_flashing(pl, p, spec):
                flash.append([pl.to3((q[0], q[1]), q[2]) for q in tri])
        if progress:
            progress(int(100 * (ip + 1) / max(1, total)))
    return place, cuts, flash, info


def _verge_finish(pl, p, spec):
    """The closing of a verge where the tiles are cut flush: a mortar bead
    over the cut ends, a verge board in front of them or a verge flashing
    (sheet metal, top flange over the tiles, down-stand in front). →
    [(polygon 3D, attrs)]."""
    mode = p["verge"]
    if mode not in ("mortar", "board", "metal"):
        return []
    H = spec["A"] + spec["t"] + _lift(spec) + p["offset"]   # tile top
    if mode == "mortar":
        sec = [(-0.035, -0.04), (0.02, -0.04), (0.02, p["offset"]),
               (0.06, p["offset"]), (0.06, p["offset"] + spec["t"]),
               (0.03, H), (-0.012, H + 0.012), (-0.035, H - 0.01)]
        attrs = {"color": MORTAR_COLOR, "mat": "Verge mortar"}
    elif mode == "board":
        sec = [(-0.026, -0.22), (-0.001, -0.22), (-0.001, H + 0.012),
               (-0.026, H + 0.012)]
        attrs = {"color": BOARD_COLOR, "mat": "Verge board"}
    else:
        f = 0.0015                             # sheet thickness
        top = H + 0.004
        sec = [(-0.014, -0.12), (-0.014 + f, -0.12), (-0.014 + f, top),
               (0.10, top), (0.10, top + f), (-0.014, top + f)]
        attrs = {"color": FLASHING_COLOR, "mat": "Flashing"}
    out = []
    eov = p["eave_ov"]
    for pc in pl.pieces:
        if pc["kind"] not in ("verge_l", "verge_r"):
            continue
        (ax, ay), (bx, by) = pc["a"], pc["b"]
        dx, dy = bx - ax, by - ay
        ln = math.hypot(dx, dy)
        if ln < 1e-6:
            continue
        d = (dx / ln, dy / ln)
        nrm = (d[1], -d[0])                    # outward (right of the loop)
        ov = p["verge_ov"]
        # from below the eave overhang to the top end
        s0 = -eov if ay < by else 0.0
        s1 = ln + (eov if by < ay else 0.0)

        def at(sv, u, z):
            x = ax + d[0] * sv + nrm[0] * (ov - u)
            y = ay + d[1] * sv + nrm[1] * (ov - u)
            return pl.to3((x, y), z)

        m = len(sec)
        V = [at(s0, u, z) for u, z in sec] + [at(s1, u, z) for u, z in sec]
        F = [list(range(m - 1, -1, -1)), list(range(m, 2 * m))]
        for i in range(m):
            j = (i + 1) % m
            F.append([i, j, m + j, m + i])
        so = Solid(V, F).fix_orientation()     # every face outward
        for f in so.F:
            out.append(([so.V[i] for i in f], attrs))
    return out


def _hole_flashing(pl, p, spec):
    """Triangles (plane coordinates x, y, z) of a flashing frame round every
    hole of the plane, like the frame of a roof window: an upstand round
    the opening and a collar lying on the tiles all round it (its lower
    part is the apron over the course below)."""
    import numpy as np
    import manifold3d as mf
    holes = [lp for lp in pl.loops if _area2(lp) < 0]
    if not holes:
        return []
    h = spec["A"] + spec["t"] + _lift(spec) + p["offset"] + 0.003
    up = 0.07                                 # upstand above the tiles
    width = 0.12                              # collar on the tiles
    out = []
    miter = mf.JoinType.Miter
    for lp in holes:
        hole = mf.CrossSection([list(reversed(lp))], mf.FillRule.Positive)
        if hole.is_empty():
            continue
        ring = hole.offset(width, miter, 4.0) - hole
        wall = hole.offset(0.004, miter, 4.0) - hole
        parts = [ring.extrude(0.002).translate((0.0, 0.0, h)),
                 wall.extrude(h + up - p["offset"]).translate(
                     (0.0, 0.0, p["offset"]))]
        for m in parts:
            mm = m.to_mesh()
            V = np.asarray(mm.vert_properties, float)[:, :3]
            T = np.asarray(mm.tri_verts, dtype=np.int64)
            out.extend(V[T].tolist())
    return out


def _tri_area(tri):
    import numpy as np
    a = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    return float(0.5 * np.sum(np.linalg.norm(a, axis=1)))


# ---------------------------------------------------------------------------
# Ridge, hips, mono-pitch ridges
# ---------------------------------------------------------------------------

def cap_lines(planes, p, spec):
    """Straight lines that get ridge tiles: (kind, a3, b3, normals,
    ends_at_verge(a, b), inward for mono)."""
    raw = []
    seen = {}
    for i, pl in enumerate(planes):
        for pc in pl.pieces:
            k = pc["kind"]
            if k in ("ridge", "hip") and pc["nb"] is not None:
                key = tuple(sorted([tuple(round(v, 3) for v in pc["a3"]),
                                    tuple(round(v, 3) for v in pc["b3"])]))
                if key in seen:
                    raw[seen[key]]["normals"].append(pl.n)
                    continue
                seen[key] = len(raw)
                raw.append({"kind": k, "a": pc["a3"], "b": pc["b3"],
                            "normals": [pl.n], "inw": None, "plane": i})
            elif k == "top":
                inw3 = _add(_add((0, 0, 0), pl.ex, pc["inw"][0]), pl.ey,
                            pc["inw"][1])
                raw.append({"kind": "mono", "a": pc["a3"], "b": pc["b3"],
                            "normals": [pl.n], "inw": inw3, "plane": i})
    # join collinear pieces that touch
    lines = []
    used = [False] * len(raw)
    for i, r in enumerate(raw):
        if used[i]:
            continue
        used[i] = True
        a, b = r["a"], r["b"]
        d = _norm(_v(a, b))
        changed = True
        while changed:
            changed = False
            for j, q in enumerate(raw):
                if used[j] or q["kind"] != r["kind"]:
                    continue
                dq = _norm(_v(q["a"], q["b"]))
                if abs(_dot(d, dq)) < 0.9995:
                    continue
                for e1 in (q["a"], q["b"]):
                    e2 = q["b"] if e1 is q["a"] else q["a"]
                    if _seg_dist(e1, a, b)[0] < TOL and \
                            abs(_seg_dist(e1, a, b)[1] - 0.5) <= 0.5 + 1e-6:
                        pts = [a, b, e2]
                        ts = [_dot(_v(a, x), d) for x in pts]
                        a = pts[ts.index(min(ts))]
                        b = pts[ts.index(max(ts))]
                        used[j] = True
                        changed = True
                        break
        lines.append(dict(r, a=a, b=b))
    # verge end points: ridge ends there get extended and end caps
    vpts = []
    for pl in planes:
        for pc in pl.pieces:
            if pc["kind"] in ("verge_l", "verge_r"):
                vpts += [pc["a3"], pc["b3"]]

    def at_verge(q):
        return any(math.dist(q, v) < 0.01 for v in vpts)

    for ln in lines:
        ln["va"], ln["vb"] = at_verge(ln["a"]), at_verge(ln["b"])
    return lines


def cap_placements(lines, p, spec):
    """→ [(kind, 4×4)] for ridge tiles, end caps and mono-pitch ridge
    pieces (mono pieces are returned as solids, they differ in length)."""
    import numpy as np
    R, beta, Lr, gauge = spec["ridge"]
    b = math.radians(beta)
    w = R * math.sin(b)
    lift = _lift(spec)
    h_top = spec["A"] + spec["t"] + 0.3 * lift + p["offset"]
    out, monos = [], []
    info = {"ridge": 0, "hip": 0, "mono": 0, "endcaps": 0}
    ext_v = p["verge_ov"] + 0.015
    for ln in lines:
        k = ln["kind"]
        if k == "ridge" and not p["ridge"]:
            continue
        if k == "hip" and not p["hips"]:
            continue
        if k == "mono" and (not p["mono"] or mono_tiles_ok(p, spec)):
            continue
        a, bb = ln["a"], ln["b"]
        if k == "hip":
            if a[2] > bb[2]:
                a, bb = bb, a
        elif k == "ridge":
            if (a[0] + a[1]) > (bb[0] + bb[1]):
                a, bb = bb, a
        d = _norm(_v(a, bb))
        L = math.dist(a, bb)
        sa = sb = 0.0
        if k == "ridge":
            sa = ext_v if ln["va"] else 0.0
            sb = ext_v if ln["vb"] else 0.0
        elif k == "hip":
            sa = p["eave_ov"] / max(0.3, math.sqrt(1 - d[2] ** 2))
        elif k == "mono":
            sa = ext_v if ln["va"] else 0.0
            sb = ext_v if ln["vb"] else 0.0
        a = _add(a, d, -sa)
        L = L + sa + sb
        if k == "mono":
            n = ln["normals"][0]
            xo = _norm(_add((0, 0, 0), ln["inw"], -1.0))    # outward
            y = _cross(n, xo)
            if _dot(y, d) < 0:
                a = _add(a, d, L)
                d = (-d[0], -d[1], -d[2])
            M = np.eye(4)
            M[:3, 0], M[:3, 1], M[:3, 2] = xo, _cross(n, xo), n
            M[:3, 3] = _add(a, n, p["offset"])
            monos.append((M, L))
            info["mono"] += max(1, int(math.ceil(L / gauge)))
            continue
        ns = ln["normals"]
        bis = _norm(_add(ns[0], ns[-1]))
        bis = _norm(_add(bis, d, -_dot(bis, d)))
        xs = _cross(d, bis)
        c = -1e9
        for n in ns:
            # the face lies on the side its normal leans to
            sgn = 1.0 if _dot(xs, n) > 0 else -1.0
            sv = _add((0, 0, 0), xs, sgn)
            den = _dot(n, bis)
            if abs(den) > 1e-6:
                c = max(c, (h_top - w * _dot(n, sv)) / den)
        if c < -1e8:
            c = h_top
        origin = _add(a, bis, c)
        if L <= Lr:
            count, step = 1, 0.0
        else:
            count = int(math.ceil((L - Lr) / gauge - 1e-9)) + 1
            step = (L - Lr) / (count - 1)
        for i in range(count):
            M = np.eye(4)
            M[:3, 0], M[:3, 1], M[:3, 2] = xs, d, bis
            M[:3, 3] = _add(origin, d, i * step)
            out.append(("ridge", M))
            info["hip" if k == "hip" else "ridge"] += 1
        # the end cap reaches down past the ridge line (which lies at -c in
        # the cap's frame) and covers the open triangle between the verge
        # tiles below the ridge tile
        lip = (VERGE_DEPTH if (p["verge"] == "tiles" and not spec["half"]
                               and spec["prof"] != "custom") else spec["t"])
        den = max(0.2, min(_dot(n, bis) for n in ns))
        skirt = max(0.0, round(max(c + (lip + h_top) / den,
                                   c + lip / den + 0.02), 3))
        # fall of the roof faces in the ridge tile's cross-section
        slope = max(0.05, min(abs(_dot(n, xs)) / max(0.2, _dot(n, bis))
                              for n in ns))
        end_kind = f"ridge_end:{skirt:.3f}:{slope:.3f}:{p['endstyle']}"
        if k == "ridge" and p["endcaps"]:
            for at_end, flag in ((False, ln["va"]), (True, ln["vb"])):
                if not flag:
                    continue
                M = np.eye(4)
                if not at_end:
                    M[:3, 0], M[:3, 1], M[:3, 2] = xs, d, bis
                    M[:3, 3] = origin
                else:
                    M[:3, 0] = (-xs[0], -xs[1], -xs[2])
                    M[:3, 1] = (-d[0], -d[1], -d[2])
                    M[:3, 2] = bis
                    M[:3, 3] = _add(origin, d, L)
                out.append((end_kind, M))
                info["endcaps"] += 1
        if k == "hip" and p["endcaps"]:
            # hip starter («Gratanfänger»): the foot of the hip at the eave
            # closed with the same end piece as the ridge ends
            M = np.eye(4)
            M[:3, 0], M[:3, 1], M[:3, 2] = xs, d, bis
            M[:3, 3] = origin
            out.append((end_kind, M))
            info["endcaps"] += 1
    return out, monos, info


# ---------------------------------------------------------------------------
# Building the group
# ---------------------------------------------------------------------------

def compute(data, p, progress=None):
    """→ dict with planes, placements, cuts, flash, monos, info."""
    t0 = time.time()
    p = normalize_params(p)
    spec = tile_spec(p)
    planes = classify(build_planes(data))
    col = dict(COLORS)[p["color"]]
    attrs = {"color": col, "mat": f"Roof tile – {p['color']}"}
    protos = Protos(spec, p, attrs)
    place, cuts, flash, info = layout(planes, p, spec, protos, progress)
    lines = cap_lines(planes, p, spec)
    caps, monos, cinfo = cap_placements(lines, p, spec)
    cinfo["mono"] += info.pop("mono_tiles", 0)
    info.update(cinfo)
    info["planes"] = len(planes)
    info["edges"] = summary(planes)
    info["seconds"] = time.time() - t0
    info["spec"] = spec
    return {"planes": planes, "place": place + caps, "cuts": cuts,
            "flash": flash, "monos": monos, "info": info, "protos": protos,
            "spec": spec, "attrs": attrs}


def estimate(data, p):
    """Fast count (no cutting) for the dialog: planes, edges, tiles."""
    p = normalize_params(p)
    spec = tile_spec(p)
    planes = classify(build_planes(data))
    n = 0
    area = 0.0
    for pl in planes:
        y0, L, rows = _rows(pl, p, spec)
        area += pl.area
        n += int(pl.area / max(1e-6, spec["W"] * L) * 1.08) + rows
    return {"planes": planes, "tiles": n, "area": area,
            "edges": summary(planes), "spec": spec}


def build_group(res, p, name, data):
    import numpy as np
    from core.group import Group
    from core.mesh import Mesh
    protos, attrs, spec = res["protos"], res["attrs"], res["spec"]
    names = {"tile": "Tile", "verge_l": "Verge tile left",
             "verge_r": "Verge tile right", "ridge": "Ridge tile",
             "ridge_end": "Ridge end cap"}
    names.update({k: "Ridge end cap" for k, _M in res["place"]
                  if k.startswith("ridge_end")})
    names.update({k: "Mono-pitch ridge tile" for k, _M in res["place"]
                  if k.startswith("mono")})
    kids = []
    for kind, M in res["place"]:
        g = Group(protos.mesh(kind, M[:3, :3]), name=names.get(kind, kind))
        T = np.eye(4)
        T[:3, 3] = M[:3, 3]
        g.xform = _np_matrix(T)
        g.component = True
        kids.append(g)
    # the container's own mesh: cut tiles, flashing, mono-pitch ridges
    pos_parts, size_parts, attr_list = [], [], []
    if res["cuts"]:
        T = np.concatenate(res["cuts"], 0)
        pos_parts.append(T.reshape(-1, 3))
        size_parts.append(np.full(len(T), 3, dtype=np.int64))
        attr_list += [dict(attrs) for _ in range(len(T))]
    extra = []
    fl_attrs = {"color": FLASHING_COLOR, "mat": "Flashing"}
    for q in res["flash"]:
        extra.append(q if isinstance(q, tuple) else (q, fl_attrs))
    for M, L in res["monos"]:
        s = mono_solid(spec, L)
        for poly in _polys_of([s]):
            P = np.c_[np.asarray(poly, float), np.ones(len(poly))] @ M.T
            extra.append((P[:, :3], attrs))
    for poly, a in extra:
        pos_parts.append(np.asarray(poly, float).reshape(-1, 3))
        size_parts.append(np.asarray([len(poly)], dtype=np.int64))
        attr_list.append(dict(a))
    mesh = Mesh()
    if pos_parts:
        pos = np.ascontiguousarray(np.concatenate(pos_parts, 0), dtype=float)
        sizes = np.concatenate(size_parts)
        mesh.add_faces_bulk(pos, sizes, np.ones(len(sizes), dtype=np.int64),
                            attr_list)
        _soften_fast(mesh, pos, sizes, 35.0)
    g = Group(mesh=mesh, name=name)
    g.adopt(kids)
    g.component = False                     # a group of tiles, not a component
    rec = {"version": VERSION,
           "shapes": list(data.get("shapes") or []),
           "params": {k: v for k, v in p.items() if k not in ("force",)},
           "faces": [{"outer": [[round(float(v), 6) for v in q]
                                for q in f["outer"]],
                      "holes": [[[round(float(v), 6) for v in q] for q in h]
                                for h in f.get("holes") or []]}
                     for f in data["faces"]]}
    g.ext = {KEY: rec}
    return g


def materials_of(p):
    from core.materials import Material
    col = dict(COLORS)[p["color"]]
    return [Material(f"Roof tile – {p['color']}", col),
            Material("Flashing", FLASHING_COLOR)]


def make_roof(data, p, name="Roof Tiles", progress=None):
    p = normalize_params(p)
    res = compute(data, p, progress)
    n = len(res["place"]) + res["info"]["cut"]
    if n > MAX_TILES and not p.get("force"):
        raise RoofError(f"{n:,} pieces — over the safe limit of "
                        f"{MAX_TILES:,}.")
    return build_group(res, p, name, data), res["info"]


# ---------------------------------------------------------------------------
# Roof generator (Create Roof…): weighted straight skeleton + roof shapes
# ---------------------------------------------------------------------------


class SkelError(Exception):
    """A roof the footprint and settings cannot make."""
    pass


class _rg_Face(list):
    """A roof face that knows the footprint edge it rose from."""
    edge = None


class _rg_Oriented(list):
    """A face whose front side was chosen on purpose."""
    oriented = True


class _rg_V:
    __slots__ = ("p0", "t0", "v", "eL", "eR", "prev", "next", "lav", "alive")

    def __init__(self, p0, t0, eL, eR):
        self.p0 = p0
        self.t0 = t0
        self.eL = eL
        self.eR = eR
        self.v = (0.0, 0.0)
        self.prev = self.next = None
        self.lav = None
        self.alive = True

    def at(self, t):
        dt = t - self.t0
        return (self.p0[0] + self.v[0] * dt, self.p0[1] + self.v[1] * dt)


def _rg_span(pts):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return max(max(xs) - min(xs), max(ys) - min(ys))


def _rg_area(pts):
    s = 0.0
    n = len(pts)
    for i in range(n):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % n]
        s += x0 * y1 - x1 * y0
    return 0.5 * s


class _rg_Line:
    """n·x = c + s·(t − t0) — an edge's line moving inward at speed s."""
    __slots__ = ("n", "d", "c", "s", "t0")

    def __init__(self, a, b, s, t0):
        dx, dy = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(dx, dy)
        self.d = (dx / ln, dy / ln)
        self.n = (-self.d[1], self.d[0])          # inward (left of CCW)
        self.c = self.n[0] * a[0] + self.n[1] * a[1]
        self.s = s
        self.t0 = t0

    def off(self, t):
        return self.c + self.s * (t - self.t0)


def _rg_velocity(L1, L2):
    """Velocity of the intersection of two moving lines."""
    a, b = L1.n
    c, d = L2.n
    det = a * d - b * c
    if abs(det) < 1e-9:
        if a * c + b * d > 0:                     # parallel, same side
            s = 0.5 * (L1.s + L2.s)
            return (L1.n[0] * s, L1.n[1] * s)
        return (0.0, 0.0)                         # opposite: they met
    s1, s2 = L1.s, L2.s
    return ((s1 * d - b * s2) / det, (a * s2 - c * s1) / det)


def skeleton(polys, speeds, t_start=0.0, t_end=None, eps=1e-9):
    """``_rg_skeleton`` with a retry: a rare near-tie that the shake did not
    break is broken by another one."""
    last = None
    for attempt in range(4):
        try:
            return _rg_skeleton(polys, speeds, t_start, t_end, eps, attempt)
        except SkelError as exc:
            last = exc
    raise last


def _rg_skeleton(polys, speeds, t_start=0.0, t_end=None, eps=1e-9, attempt=0):
    """Weighted straight skeleton of simple polygons (CCW, no holes).

    ``polys``: [(points, labels)] — labels[i] names the edge points[i] →
    points[i+1]; ``speeds``: label → inward speed per unit time (time =
    height). Runs from ``t_start`` until the wavefront vanishes or until
    ``t_end``. Returns ``(segments, fronts)``: segments are
    ((x, y, t), (x, y, t), {face labels}); fronts are the wavefront
    polygons left at ``t_end`` as [(points, labels)]."""
    lines = {}
    segs = []
    lavs = []
    for pts, labels in polys:
        pts = [tuple(map(float, p)) for p in pts]
        # break the ties of symmetric outlines (several events at one
        # point at one time): a deterministic shake far below a millimetre
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        sc = max(max(xs) - min(xs), max(ys) - min(ys), 1e-3) * 2e-6 * \
            (1 + 3 * attempt)
        pts = [(x + sc * math.sin(12.9898 * i + 1.3 + attempt),
                y + sc * math.sin(78.233 * i + 2.1 + 2 * attempt))
               for i, (x, y) in enumerate(pts)]
        n = len(pts)
        if n < 3:
            continue
        if _rg_area(pts) < 0:
            raise SkelError("polygon must be counter-clockwise")
        for i in range(n):
            lab = labels[i]
            L = _rg_Line(pts[i], pts[(i + 1) % n], float(speeds[lab]), t_start)
            key = (lab, i, id(pts))
            lines[key] = L
            a, b = pts[i], pts[(i + 1) % n]
            segs.append(((a[0], a[1], t_start), (b[0], b[1], t_start), {lab}))
        verts = []
        for i in range(n):
            eL = (labels[i - 1], (i - 1) % n, id(pts))
            eR = (labels[i], i, id(pts))
            verts.append(_rg_V(pts[i], t_start, eL, eR))
        lav = {"verts": verts}
        for i, v in enumerate(verts):
            v.prev = verts[i - 1]
            v.next = verts[(i + 1) % n]
            v.lav = lav
            v.v = _rg_velocity(lines[v.eL], lines[v.eR])
        lavs.append(lav)

    def lab(e):
        return e[0]

    def arc(v, p, t):
        a = (v.p0[0], v.p0[1], v.t0)
        b = (p[0], p[1], t)
        if math.dist(a, b) > 1e-9:
            segs.append((a, b, {lab(v.eL), lab(v.eR)}))

    def members(lav):
        out = []
        start = lav["start"]
        v = start
        while True:
            out.append(v)
            v = v.next
            if v is start or len(out) > 100000:
                break
        return out

    for lav in lavs:
        lav["start"] = lav["verts"][0]

    def degenerate(lav, t):
        ms = members(lav)
        pts = [m.at(t) for m in ms]
        if len(ms) < 3:
            return True
        return abs(_rg_area(pts)) < 1e-10 * max(1.0, _rg_span(pts) ** 2)

    def finalize(lav, t):
        """A wavefront piece that has no area left: its vertices end where
        they are, the pieces between them are ridges."""
        ms = members(lav)
        pts = [m.at(t) for m in ms]
        for m, p in zip(ms, pts):
            arc(m, p, t)
        for i, m in enumerate(ms):
            a, b = pts[i], pts[(i + 1) % len(ms)]
            if math.dist(a, b) > 1e-9:
                segs.append(((a[0], a[1], t), (b[0], b[1], t),
                             {lab(m.eR), lab(ms[(i + 1) % len(ms)].eL)}))

    def reflex(v):
        d1 = lines[v.eL].d
        d2 = lines[v.eR].d
        return d1[0] * d2[1] - d1[1] * d2[0] < -1e-12

    now = t_start
    active = [l for l in lavs]
    guard = 0
    while active:
        guard += 1
        if guard > 20000:
            raise SkelError("no convergence")
        best = None                       # (t, kind, data)
        for lav in active:
            ms = members(lav)
            for A in ms:
                B = A.next
                L = lines[A.eR]
                pa = (A.p0[0] - A.v[0] * A.t0, A.p0[1] - A.v[1] * A.t0)
                pb = (B.p0[0] - B.v[0] * B.t0, B.p0[1] - B.v[1] * B.t0)
                c = (pb[0] - pa[0]) * L.d[0] + (pb[1] - pa[1]) * L.d[1]
                k = (B.v[0] - A.v[0]) * L.d[0] + (B.v[1] - A.v[1]) * L.d[1]
                if k < -1e-12:
                    t = -c / k
                    if t >= now - 1e-7:
                        t = max(t, now)
                        if best is None or t < best[0] - eps or (
                                abs(t - best[0]) <= eps and best[1] == 1):
                            best = (t, 0, (A, B))
            for V in ms:
                if not reflex(V):
                    continue
                for X in ms:
                    Y = X.next
                    if X is V or Y is V:
                        continue
                    L = lines[X.eR]
                    q = (V.p0[0] - V.v[0] * V.t0, V.p0[1] - V.v[1] * V.t0)
                    den = L.n[0] * V.v[0] + L.n[1] * V.v[1] - L.s
                    if den > -1e-12:
                        continue
                    num = L.c - L.s * L.t0 - (L.n[0] * q[0] + L.n[1] * q[1])
                    t = num / den
                    if t < now - 1e-7:
                        continue
                    t = max(t, now)
                    if best is not None and t > best[0] + eps:
                        continue
                    P = V.at(t)
                    xa, ya = X.at(t)
                    xb, yb = Y.at(t)
                    u = (P[0] - xa) * L.d[0] + (P[1] - ya) * L.d[1]
                    ub = (xb - xa) * L.d[0] + (yb - ya) * L.d[1]
                    tol = 1e-7
                    if ub < tol or u < tol or u > ub - tol:
                        continue
                    if best is None or t < best[0] - eps:
                        best = (t, 1, (V, X, Y))
        if best is None:
            break
        t, kind, data = best
        if t_end is not None and t > t_end + eps:
            break
        now = t
        if kind == 0:
            A, B = data
            lav = A.lav
            P = A.at(t)
            Pb = B.at(t)
            P = ((P[0] + Pb[0]) / 2, (P[1] + Pb[1]) / 2)
            arc(A, P, t)
            arc(B, P, t)
            A.alive = B.alive = False
            if A.prev is B.next:              # a triangle collapses
                C = A.prev
                arc(C, P, t)
                C.alive = False
                active.remove(lav)
                continue
            N = _rg_V(P, t, A.eL, B.eR)
            N.prev, N.next = A.prev, B.next
            A.prev.next = N
            B.next.prev = N
            N.lav = lav
            N.v = _rg_velocity(lines[N.eL], lines[N.eR])
            lav["start"] = N
            ms = members(lav)
            if len(ms) >= 3 and degenerate(lav, t):
                finalize(lav, t)
                active.remove(lav)
            elif len(ms) == 2:
                o = N.next
                po = o.at(t)
                arc(o, po, t)
                if math.dist(P, po) > 1e-9:
                    segs.append(((P[0], P[1], t), (po[0], po[1], t),
                                 {lab(N.eL), lab(N.eR)}))
                active.remove(lav)
        else:
            V, X, Y = data
            lav = V.lav
            P = V.at(t)
            arc(V, P, t)
            V.alive = False
            V1 = _rg_V(P, t, V.eL, X.eR)
            V2 = _rg_V(P, t, X.eR, V.eR)
            # chain 1: V.prev → V1 → Y …
            V1.prev, V1.next = V.prev, Y
            V.prev.next = V1
            Y.prev = V1
            # chain 2: X → V2 → V.next …
            V2.prev, V2.next = X, V.next
            X.next = V2
            V.next.prev = V2
            active.remove(lav)
            for N in (V1, V2):
                N.v = _rg_velocity(lines[N.eL], lines[N.eR])
                nl = {"start": N}
                ms = members(nl)
                for m in ms:
                    m.lav = nl
                if len(ms) >= 3 and degenerate(nl, t):
                    finalize(nl, t)
                elif len(ms) >= 3:
                    active.append(nl)
                elif len(ms) == 2:
                    o = N.next
                    po = o.at(t)
                    arc(o, po, t)
                    if math.dist(P, po) > 1e-9:
                        segs.append(((P[0], P[1], t), (po[0], po[1], t),
                                     {lab(N.eL), lab(N.eR)}))
    fronts = []
    if active and t_end is not None:
        for lav in active:
            ms = members(lav)
            pts, labels = [], []
            for m in ms:
                p = m.at(t_end)
                arc(m, p, t_end)
                pts.append(p)
            for m in ms:
                labels.append(lab(m.eR))
            for i, m in enumerate(ms):
                a = pts[i]
                b = pts[(i + 1) % len(ms)]
                if math.dist(a, b) > 1e-9:
                    segs.append(((a[0], a[1], t_end), (b[0], b[1], t_end),
                                 {lab(m.eR)}))
            # drop zero-length edges
            cp, cl = [], []
            for i in range(len(pts)):
                if math.dist(pts[i], pts[(i + 1) % len(pts)]) > 1e-7:
                    cp.append(pts[i])
                    cl.append(labels[i])
            if len(cp) >= 3 and _rg_area(cp) > 1e-9:
                fronts.append((cp, cl))
    elif active:
        for lav in active:
            if degenerate(lav, now):
                finalize(lav, now)
            else:
                raise SkelError("the wavefront did not close")
    return segs, fronts


def _rg_snap(segs, tol):
    """Weld points closer than ``tol`` and drop the segments that vanish."""
    reps = []
    grid = {}

    def rep(p):
        k = (int(math.floor(p[0] / tol)), int(math.floor(p[1] / tol)),
             int(math.floor(p[2] / tol)))
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for j in grid.get((k[0] + dx, k[1] + dy, k[2] + dz), ()):
                        if math.dist(reps[j], p) <= tol:
                            return j
        reps.append(p)
        grid.setdefault(k, []).append(len(reps) - 1)
        return len(reps) - 1
    out = []
    seen = {}
    for a, b, f in segs:
        ia, ib = rep(a), rep(b)
        if ia == ib:
            continue
        key = (min(ia, ib), max(ia, ib))
        if key in seen:
            seen[key][2].update(f)
            continue
        item = (reps[ia], reps[ib], set(f))
        seen[key] = item
        out.append(item)
    return out


def faces_from_segments(segs, labels, tol=1e-4):
    """Face label → closed 3D loops, walked along the segments of that
    face."""
    segs = _rg_snap(segs, tol)
    out = {}
    for f in labels:
        mine = [s for s in segs if f in s[2]]
        if not mine:
            continue
        rest = list(mine)
        while rest:
            loop, used = _rg_walk(rest)
            if not used:
                break
            if loop and len(loop) >= 3:
                out.setdefault(f, []).append(loop)
            rest = [s for i, s in enumerate(rest) if i not in used]
    return out


def _rg_walk(segs):
    def key(p):
        return (p[0], p[1], p[2])
    adj = {}
    for i, (a, b, _f) in enumerate(segs):
        adj.setdefault(key(a), []).append((i, b, a))
        adj.setdefault(key(b), []).append((i, a, b))
    used = set()
    a0, b0, _ = segs[0]
    loop = [a0]
    used.add(0)
    cur = b0
    for _ in range(len(segs) + 2):
        if key(cur) == key(a0):
            return loop, used
        loop.append(cur)
        nxt = None
        for i, other, _me in adj.get(key(cur), []):
            if i not in used:
                nxt = (i, other)
                break
        if nxt is None:
            return None, used
        used.add(nxt[0])
        cur = nxt[1]
    return None, used


# ---------------------------------------------------------------------------
# Roof shapes
# ---------------------------------------------------------------------------

ROOF_TYPES = [
    # key, label, family
    ("gable", "Gable (Satteldach) — also L/T/U: cross gable"),
    ("hip", "Hip (Walmdach) — also L/T/U: cross hip"),
    ("halfhip", "Half-hip / jerkinhead (Krüppelwalmdach)"),
    ("dutch", "Dutch gable / gablet (Fußwalm, Irimoya)"),
    ("pyramid", "Pyramid / pavilion (Zeltdach)"),
    ("mono", "Mono-pitch / shed / skillion (Pultdach)"),
    ("split", "Split-level shed / clerestory (versetztes Pultdach)"),
    ("saltbox", "Saltbox / catslide (asymmetric gable)"),
    ("mansard", "Mansard, all sides (Mansardwalmdach)"),
    ("gambrel", "Gambrel / barn (Mansarddach)"),
    ("bonnet", "Bonnet / bell-cast eaves (Aufschiebling)"),
    ("butterfly", "Butterfly / V-roof (Schmetterlingsdach)"),
    ("mroof", "M-roof / double gable (Doppelsatteldach)"),
    ("sawtooth", "Sawtooth (Sheddach)"),
    ("barrel", "Barrel / arched (Tonnendach)"),
    ("spire", "Spire / cone (Turmhelm, Kegeldach)"),
    ("dome", "Dome (Kuppeldach)"),
    ("helm", "Rhenish helm (Rhombendach)"),
    ("aframe", "A-frame"),
    ("flat", "Flat roof with fall (Flachdach)"),
]

TYPE_DEFAULTS = {
    # pitch, pitch2, ratio/break, count
    "gable": dict(pitch=38.0), "hip": dict(pitch=30.0),
    "halfhip": dict(pitch=40.0, pitch2=55.0, ratio=0.65),
    "dutch": dict(pitch=35.0, pitch2=35.0, ratio=0.45),
    "pyramid": dict(pitch=35.0), "mono": dict(pitch=12.0),
    "split": dict(pitch=15.0, offset=0.8),
    "saltbox": dict(pitch=40.0, pitch2=25.0),
    "mansard": dict(pitch=70.0, pitch2=25.0, brk=2.4),
    "gambrel": dict(pitch=65.0, pitch2=30.0, brk=2.2),
    "bonnet": dict(pitch=22.0, pitch2=45.0, brk=0.7),
    "butterfly": dict(pitch=10.0), "mroof": dict(pitch=35.0),
    "sawtooth": dict(pitch=25.0, count=3), "barrel": dict(pitch=35.0),
    "spire": dict(pitch=70.0), "dome": dict(pitch=45.0),
    "helm": dict(pitch=50.0), "aframe": dict(pitch=60.0),
    "flat": dict(pitch=2.0),
}

# which parameters a type uses (for the dialog)
TYPE_PARAMS = {
    "gable": ("pitch", "gables", "rotate"), "hip": ("pitch",),
    "halfhip": ("pitch", "pitch2", "ratio", "gables", "rotate"),
    "dutch": ("pitch", "pitch2", "ratio", "gables", "rotate"),
    "pyramid": ("pitch",), "mono": ("pitch", "eave"),
    "split": ("pitch", "offset", "rotate"),
    "saltbox": ("pitch", "pitch2", "rotate"),
    "mansard": ("pitch", "pitch2", "brk"),
    "gambrel": ("pitch", "pitch2", "brk", "gables", "rotate"),
    "bonnet": ("pitch", "pitch2", "brk"),
    "butterfly": ("pitch", "rotate"), "mroof": ("pitch", "rotate"),
    "sawtooth": ("pitch", "count", "rotate"), "barrel": ("pitch", "rotate"),
    "spire": ("pitch",), "dome": ("pitch",), "helm": ("pitch", "rotate"),
    "aframe": ("pitch", "gables", "rotate"), "flat": ("pitch", "eave"),
}


def _rg_cot(deg):
    return 1.0 / math.tan(math.radians(max(1e-3, min(89.5, deg))))


def _rg_tan(deg):
    return math.tan(math.radians(max(0.0, min(89.5, deg))))


def clean_outline(pts, tol=1e-4):
    """Counter-clockwise, without repeated or collinear points."""
    pts = [tuple(map(float, p[:2])) for p in pts]
    out = []
    for p in pts:
        if not out or math.dist(out[-1], p) > tol:
            out.append(p)
    if len(out) > 1 and math.dist(out[0], out[-1]) <= tol:
        out.pop()
    changed = True
    while changed and len(out) > 3:
        changed = False
        for i in range(len(out)):
            a, b, c = out[i - 1], out[i], out[(i + 1) % len(out)]
            cr = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
            if abs(cr) < tol * max(math.dist(a, b), math.dist(b, c), 1e-9):
                out.pop(i)
                changed = True
                break
    if _rg_area(out) < 0:
        out.reverse()
    return out


def _rg_convex(pts, i):
    a, b, c = pts[i - 1], pts[i], pts[(i + 1) % len(pts)]
    return (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0]) > 0


def auto_gables(pts, rotate=False):
    """Edges that become gables: ends of the building (both corners convex)
    no longer than their neighbours — or, turned, the long sides."""
    n = len(pts)
    L = [math.dist(pts[i], pts[(i + 1) % n]) for i in range(n)]
    out = set()
    for i in range(n):
        if not (_rg_convex(pts, i) and _rg_convex(pts, (i + 1) % n)):
            continue
        a, b = L[i - 1], L[(i + 1) % n]
        if not rotate and L[i] <= a + 1e-6 and L[i] <= b + 1e-6:
            out.add(i)
        if rotate and L[i] >= a - 1e-6 and L[i] >= b - 1e-6:
            out.add(i)
    if n == 4:
        out = {0, 2} if (L[0] <= L[1] + 1e-9) != rotate else {1, 3}
        return out
    for i in sorted(out):                     # never two gables side by side
        if i in out and (i + 1) % n in out:
            out.discard((i + 1) % n)
    return out


def _rg_offset_outline(pts, dists):
    """Each edge i moved outward by dists[i]; corners where the moved lines
    meet."""
    n = len(pts)
    lines = []
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        dx, dy = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(dx, dy)
        nx, ny = dy / ln, -dx / ln               # outward (right of CCW)
        d = dists[i]
        lines.append(((a[0] + nx * d, a[1] + ny * d), (dx / ln, dy / ln)))
    out = []
    for i in range(n):
        (p, d0) = lines[i - 1]
        (q, d1) = lines[i]
        cr = d0[0] * d1[1] - d0[1] * d1[0]
        if abs(cr) < 1e-9:
            out.append(q)
            continue
        wx, wy = q[0] - p[0], q[1] - p[1]
        s = (wx * d1[1] - wy * d1[0]) / cr
        out.append((p[0] + d0[0] * s, p[1] + d0[1] * s))
    return out


def _rg_skel_faces(pts, phases, z_base, T):
    """phases: [(speeds by edge, t_end or None)] → 3D roof polygons.
    Time = height above z_base − T."""
    polys = [(pts, [(0, i) for i in range(len(pts))])]
    faces = []
    t = 0.0
    for k, (speeds, t_end) in enumerate(phases):
        sp = {}
        for poly, labels in polys:
            for lab in labels:
                sp[lab] = speeds[lab[1]]
        segs, fronts = skeleton(polys, sp, t_start=t, t_end=t_end)
        labels = sorted({lab for _p, ls in polys for lab in ls})
        F = faces_from_segments(segs, labels)
        for lab, loops in F.items():
            for lp in loops:
                f = _rg_Face((x, y, z_base - T + tt) for x, y, tt in lp)
                f.edge = lab[1]
                faces.append(f)
        if t_end is None or not fronts:
            break
        t = t_end
        polys = [(p, [(k + 1, lab[1]) for lab in ls]) for p, ls in fronts]
    return faces


def _rg_ridge_time(pts, speeds):
    segs, _f = skeleton([(pts, list(range(len(pts))))],
                        {i: speeds[i] for i in range(len(pts))})
    return max(p[2] for s in segs for p in s[:2])


def _rg_obb(pts):
    """Smallest oriented rectangle round the outline: (origin, ux, uy,
    length along ux, depth along uy); ux is the long side."""
    best = None
    n = len(pts)
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        dx, dy = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(dx, dy)
        if ln < 1e-9:
            continue
        ux = (dx / ln, dy / ln)
        uy = (-ux[1], ux[0])
        xs = [(p[0] - a[0]) * ux[0] + (p[1] - a[1]) * ux[1] for p in pts]
        ys = [(p[0] - a[0]) * uy[0] + (p[1] - a[1]) * uy[1] for p in pts]
        area = (max(xs) - min(xs)) * (max(ys) - min(ys))
        if best is None or area < best[0] - 1e-9:
            o = (a[0] + ux[0] * min(xs) + uy[0] * min(ys),
                 a[1] + ux[1] * min(xs) + uy[1] * min(ys))
            best = (area, o, ux, uy, max(xs) - min(xs), max(ys) - min(ys))
    _a, o, ux, uy, L, D = best
    if D > L:                                    # ux along the long side
        o = (o[0] + ux[0] * L, o[1] + ux[1] * L)
        ux, uy, L, D = uy, (-ux[0], -ux[1]), D, L
    return o, ux, uy, L, D


def _rg_rect_frame(pts, rotate):
    o, ux, uy, L, D = _rg_obb(pts)
    if rotate:                                   # the ridge across
        o = (o[0] + uy[0] * D, o[1] + uy[1] * D)
        ux, uy, L, D = (-uy[0], -uy[1]), ux, D, L
    def P(x, y, z):
        return (o[0] + ux[0] * x + uy[0] * y, o[1] + ux[1] * x + uy[1] * y, z)
    return P, L, D


def build_roof(outline, z0, rtype, p):
    """→ (roof faces, wall faces) as lists of 3D polygons.

    ``outline``: the footprint (2D, any orientation), ``z0`` its height
    (top of the walls); ``p``: pitch, pitch2, ratio, brk, offset, count,
    overhang (horizontal, at the eaves), gable_ov (at gables), rotate,
    gables (set of edge indices or None = auto), eave (edge index for a
    mono-pitch roof or None = longest)."""
    pts = clean_outline(outline)
    if len(pts) < 3:
        raise SkelError("The footprint needs at least three corners.")
    n = len(pts)
    ov = max(0.0, float(p.get("overhang", 0.5)))
    gov = max(0.0, float(p.get("gable_ov", 0.3)))
    a1 = float(p.get("pitch", 35.0))
    a2 = float(p.get("pitch2", a1))
    rot = bool(p.get("rotate", False))
    gables = p.get("gables")
    if gables is None:
        gables = auto_gables(pts, rot)
    gables = {g for g in gables if 0 <= g < n}
    roof, walls = [], []

    def skel(phase_speeds, ends, main_pitch, eave_gov=None):
        """phase_speeds: list of per-edge speed lists (0 = gable) with
        phase end heights above z0 (None for the last)."""
        T = ov * _rg_tan(main_pitch)
        first = phase_speeds[0]
        dists = [first[i] * T if first[i] > 0 else gov for i in range(n)]
        P2 = _rg_offset_outline(pts, dists)
        if _rg_area(P2) <= 0:
            raise SkelError("The overhang is too large for this footprint.")
        phases = []
        for sp, h in zip(phase_speeds, ends):
            phases.append((sp, None if h is None else h + T))
        return _rg_skel_faces(P2, phases, z0, T)

    c1, c2 = _rg_cot(a1), _rg_cot(a2)
    if rtype in ("gable", "aframe"):
        if not gables:
            raise SkelError("No gable sides — use Hip, or tick gable sides.")
        sp = [0.0 if i in gables else c1 for i in range(n)]
        roof = skel([sp], [None], a1)
    elif rtype in ("hip", "pyramid", "spire"):
        roof = skel([[c1] * n], [None], a1)
    elif rtype == "halfhip":
        sp1 = [0.0 if i in gables else c1 for i in range(n)]
        H = _rg_ridge_time(pts, sp1)
        h1 = max(0.05, min(0.98, float(p.get("ratio", 0.65)))) * H
        sp2 = [c2 if i in gables else c1 for i in range(n)]
        roof = skel([sp1, sp2], [h1, None], a1)
    elif rtype == "dutch":
        sp1 = [c2 if i in gables else c1 for i in range(n)]
        H = _rg_ridge_time(pts, sp1)
        h1 = max(0.05, min(0.95, float(p.get("ratio", 0.45)))) * H
        sp2 = [0.0 if i in gables else c1 for i in range(n)]
        roof = skel([sp1, sp2], [h1, None], a2 if gables else a1)
    elif rtype in ("mansard", "gambrel", "bonnet"):
        g = gables if rtype == "gambrel" else set()
        sp1 = [0.0 if i in g else c1 for i in range(n)]
        sp2 = [0.0 if i in g else c2 for i in range(n)]
        brk = max(0.05, float(p.get("brk", 2.0)))
        H = _rg_ridge_time(pts, sp1)
        if brk >= H:                       # the steep part closes first
            roof = skel([sp1], [None], a1)
        else:
            roof = skel([sp1, sp2], [brk, None], a1)
    elif rtype == "saltbox":
        o, ux, uy, L, D = _rg_obb(pts)
        if rot:
            uy = (-uy[0], -uy[1])
        sp = []
        for i in range(n):
            a, b = pts[i], pts[(i + 1) % n]
            dx, dy = b[0] - a[0], b[1] - a[1]
            ln = math.hypot(dx, dy)
            nin = (-dy / ln, dx / ln)            # inward normal
            dot = nin[0] * uy[0] + nin[1] * uy[1]
            if abs(dot) < 0.3:
                sp.append(0.0)                   # the ends: gables
            else:
                sp.append(c1 if dot > 0 else c2)
        roof = skel([sp], [None], a1)
    elif rtype in ("mono", "flat"):
        roof, walls = _rg_mono(pts, z0, a1, ov, gov, p.get("eave"))
    elif rtype == "split":
        roof, walls = _rg_split(pts, z0, a1, float(p.get("offset", 0.8)), ov,
                             gov, rot)
    elif rtype == "butterfly":
        roof, walls = _rg_butterfly(pts, z0, a1, ov, gov, rot)
    elif rtype == "mroof":
        roof, walls = _rg_mroof(pts, z0, a1, ov, gov, rot)
    elif rtype == "sawtooth":
        roof, walls = _rg_sawtooth(pts, z0, a1, int(p.get("count", 3)), ov, gov,
                                rot)
    elif rtype == "barrel":
        roof, walls = _rg_barrel(pts, z0, a1, ov, gov, rot)
    elif rtype == "dome":
        roof = _rg_dome(pts, z0, a1, ov)
    elif rtype == "helm":
        roof, walls = _rg_helm(pts, z0, a1, ov, rot)
    else:
        raise SkelError(f"Unknown roof type {rtype}.")
    roof = [f for f in roof if len(f) >= 3 and _rg_area3(f) > 1e-6]
    vertical, sloped = [], []
    for f in roof:
        if abs(_rg_newell(f)[2]) < 0.04 * _rg_area3(f):
            e = getattr(f, "edge", None)
            if e is not None:                 # a gable: faces like its edge
                a, b = pts[e], pts[(e + 1) % n]
                vertical.append(_rg_Oriented(_rg_facing(
                    f, (b[1] - a[1], -(b[0] - a[0])))))
            else:
                vertical.append(f)
        else:
            sloped.append(_rg_up(f))
    roof = sloped
    if rtype in RECT_TYPES:
        # shapes laid on the bounding rectangle: cut them to the footprint
        # (plus its overhang), so nothing hangs over a courtyard
        dists = [max(ov, gov)] * n
        region = _rg_offset_outline(pts, dists)
        roof = _rg_clip_faces(roof, region)
        walls = _rg_clip_walls(walls, pts)
        vertical = _rg_clip_walls(vertical, pts)
    walls = walls + vertical                  # gablets inside the roof
    if p.get("walls", True) and rtype not in ("dome", "helm", "spire",
                                              "pyramid", "hip"):
        walls = walls + _rg_walls(pts, z0, roof)
    if not p.get("walls", True):
        walls = [f for f in walls if f in vertical]
    centre = (sum(q[0] for q in pts) / n, sum(q[1] for q in pts) / n)
    walls = [w if getattr(w, "oriented", False) else _rg_outward(w, centre)
             for w in walls]
    walls = [f for f in walls if len(f) >= 3 and _rg_area3(f) > 1e-6]
    thick = float(p.get("thick", 0.0))
    slab = _rg_slab(roof, thick)
    roof, walls, slab, nfix = orient_check(roof, walls, slab, pts, z0, thick)
    ORIENT_LOG["flipped"] = nfix
    return roof, walls + slab


ORIENT_LOG = {"flipped": 0}


def _pip(x, y, poly):
    inside = False
    m = len(poly)
    for i in range(m):
        ax, ay = poly[i][0], poly[i][1]
        bx, by = poly[(i - 1) % m][0], poly[(i - 1) % m][1]
        if (ay > y) != (by > y):
            if x < ax + (y - ay) * (bx - ax) / (by - ay):
                inside = not inside
    return inside


def _face_point(f):
    """A point well inside the face (centre of its biggest triangle) — the
    centre of a bent face may lie outside it."""
    best, pt = -1.0, None
    for a, b, c in _poly_tris(f):
        A, B, C = f[a], f[b], f[c]
        ar = _rg_area3([A, B, C])
        if ar > best:
            best = ar
            pt = tuple((A[k] + B[k] + C[k]) / 3.0 for k in range(3))
    return pt


def orient_check(roof, walls, slab, pts, z0, thick):
    """Checks every face of a generated roof and turns the ones that face
    into the solid: a point just in front of a face must lie outside, a
    point just behind it inside. Two solids are tested — the roof slab
    (between the roof faces and their underside) and the building (the
    footprint from the wall foot up to the roof). Faces where the test
    can't decide keep their side. → roof, walls, slab, number turned."""
    roof = [_rg_up(f) for f in roof]           # the roof faces face up
    tops = []
    for f in roof:
        n = _rg_newell(f)
        ln = math.sqrt(n[0] ** 2 + n[1] ** 2 + n[2] ** 2) or 1.0
        if n[2] <= 1e-9:
            continue
        q = f[0]
        d = n[0] * q[0] + n[1] * q[1] + n[2] * q[2]
        dz = max(thick * ln / max(n[2], 0.2 * ln), 0.03)
        xs = [v[0] for v in f]
        ys = [v[1] for v in f]
        tops.append((f, n, d, dz, min(xs), max(xs), min(ys), max(ys)))

    def top_z(x, y):
        out = []
        for f, n, d, dz, x0, x1, y0, y1 in tops:
            if x0 - 1e-9 <= x <= x1 + 1e-9 and y0 - 1e-9 <= y <= y1 + 1e-9 \
                    and _pip(x, y, f):
                out.append(((d - n[0] * x - n[1] * y) / n[2], dz))
        return out

    def in_slab(p):
        return any(z - dz < p[2] < z for z, dz in top_z(p[0], p[1]))

    def in_building(p):
        if p[2] <= z0 or not _pip(p[0], p[1], pts):
            return False
        zs = top_z(p[0], p[1])
        return bool(zs) and p[2] < max(z for z, _dz in zs)

    def in_attic(p):                         # under the roof, over z0
        if p[2] <= z0:                         # (also over the gable overhang)
            return False
        zs = top_z(p[0], p[1])
        return bool(zs) and p[2] < max(z - dz for z, dz in zs)

    eps = 0.01 if thick <= 0 else min(0.01, thick / 3.0)

    def fix(faces, tests):
        out, cnt = [], 0
        ORIENT_LOG["undecided"] = 0
        for f in faces:
            keep = f
            n = _rg_newell(f)
            ln = math.sqrt(n[0] ** 2 + n[1] ** 2 + n[2] ** 2)
            c = _face_point(list(f)) if ln > 1e-12 else None
            if c is not None:
                u = (n[0] / ln * eps, n[1] / ln * eps, n[2] / ln * eps)
                pf = (c[0] + u[0], c[1] + u[1], c[2] + u[2])
                pb = (c[0] - u[0], c[1] - u[1], c[2] - u[2])
                for inside in tests:           # the first test that decides
                    front, back = inside(pf), inside(pb)
                    if front != back:
                        if front:
                            keep = list(reversed(f))
                            cnt += 1
                        break
                else:
                    ORIENT_LOG["undecided"] = ORIENT_LOG.get("undecided", 0) + 1
            out.append(keep)
        return out, cnt

    walls, a = fix(walls, (in_building,
                           lambda q: in_building(q) or in_slab(q),
                           in_attic,
                           lambda q: in_attic(q) or in_slab(q)))
    und = ORIENT_LOG["undecided"]
    slab, b = fix(slab, (in_slab,))
    ORIENT_LOG["undecided"] += und
    return roof, walls, slab, a + b


RECT_TYPES = ("split", "butterfly", "mroof", "sawtooth", "barrel", "helm",
              "dome")


def _rg_slab(roof, thick):
    """The roof as a slab of ``thick`` (measured square to each face): the
    underside (facing down, so it shows its front side from below — under
    the overhang, through a courtyard) and the fascia round the open
    edges."""
    if thick <= 1e-4:
        return []
    out = []
    shifted = []
    for f in roof:
        n = _rg_newell(f)
        ln = math.sqrt(n[0] ** 2 + n[1] ** 2 + n[2] ** 2) or 1.0
        dz = thick * ln / max(abs(n[2]), 0.2 * ln)
        low = [(q[0], q[1], q[2] - dz) for q in f]
        shifted.append(low)
        out.append(list(reversed(low)))
    edges = []                               # every edge of every face
    for j, f in enumerate(roof):
        m = len(f)
        for i in range(m):
            edges.append((j, f[i], f[(i + 1) % m]))

    def covered(j, a, b):
        """How much of the edge a–b another face's edges cover (an edge
        split at a T-junction still counts as shared, not as open)."""
        d = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
        L = math.sqrt(d[0] ** 2 + d[1] ** 2 + d[2] ** 2)
        if L < 1e-9:
            return []
        u = (d[0] / L, d[1] / L, d[2] / L)
        spans = []
        for k, p, q in edges:
            if k == j:
                continue
            ok = True
            ts = []
            for r in (p, q):
                w = (r[0] - a[0], r[1] - a[1], r[2] - a[2])
                t = w[0] * u[0] + w[1] * u[1] + w[2] * u[2]
                e = (w[0] - t * u[0], w[1] - t * u[1], w[2] - t * u[2])
                if e[0] ** 2 + e[1] ** 2 + e[2] ** 2 > 1e-6:
                    ok = False
                    break
                ts.append(t)
            if ok:
                lo, hi = max(0.0, min(ts)), min(L, max(ts))
                if hi > lo:
                    spans.append((lo, hi))
        spans.sort()
        free, cur = [], 0.0                   # the parts no one covers
        for lo, hi in spans:
            if lo > cur + 1e-4:
                free.append((cur / L, lo / L))
            cur = max(cur, hi)
        if cur < L - 1e-4:
            free.append((cur / L, 1.0))
        return free

    for j, (f, low) in enumerate(zip(roof, shifted)):
        m = len(f)
        for i in range(m):
            a, b = f[i], f[(i + 1) % m]
            la, lb = low[i], low[(i + 1) % m]
            ex, ey = b[0] - a[0], b[1] - a[1]
            ccw = _rg_area([(q[0], q[1]) for q in f]) > 0
            for t0, t1 in covered(j, a, b):

                def at(p, q, t):
                    return tuple(p[k] + (q[k] - p[k]) * t for k in range(3))
                quad = [at(a, b, t0), at(a, b, t1), at(la, lb, t1),
                        at(la, lb, t0)]
                if _rg_area3(quad) < 1e-6:
                    continue
                # outward: away from the face, across the edge
                out.append(_rg_Oriented(_rg_facing(quad, (ey, -ex))
                                        if ccw else
                                        _rg_facing(quad, (-ey, ex))))
    return out


def _rg_clip_faces(faces, region):
    """Each planar face cut to the plan region (a polygon, CCW); the cut
    points are lifted back onto the face's own plane."""
    import manifold3d as mf
    reg = mf.CrossSection([region], mf.FillRule.Positive)
    out = []
    for f in faces:
        n = _rg_newell(f)
        if abs(n[2]) < 1e-9:
            out.append(f)
            continue
        loop = [(q[0], q[1]) for q in f]
        if _rg_area(loop) < 0:
            loop.reverse()
        cs = mf.CrossSection([loop], mf.FillRule.Positive) ^ reg
        q0 = f[0]
        d = n[0] * q0[0] + n[1] * q0[1] + n[2] * q0[2]
        for lp in cs.to_polygons():
            if len(lp) < 3 or abs(_rg_area([tuple(q) for q in lp])) < 1e-6:
                continue
            poly = [(float(x), float(y),
                     (d - n[0] * x - n[1] * y) / n[2]) for x, y in lp]
            out.append(_rg_up(poly))
    return out


def _rg_clip_walls(walls, pts):
    """Vertical faces kept only where they stand over the footprint."""
    import manifold3d as mf
    reg = mf.CrossSection([pts], mf.FillRule.Positive).offset(
        0.001, mf.JoinType.Miter, 4.0)
    out = []
    for w in walls:
        n = _rg_newell(w)
        ln = math.hypot(n[0], n[1])
        if ln < 1e-12:
            out.append(w)
            continue
        ux = (-n[1] / ln, n[0] / ln)              # along the wall
        o = w[0]
        uz = [((q[0] - o[0]) * ux[0] + (q[1] - o[1]) * ux[1], q[2])
              for q in w]
        u0 = min(u for u, _z in uz)
        u1 = max(u for u, _z in uz)
        # where the wall's line is inside the footprint (thin strip test)
        strip = mf.CrossSection([[(o[0] + ux[0] * u0 - ux[1] * 1e-4,
                                   o[1] + ux[1] * u0 + ux[0] * 1e-4),
                                  (o[0] + ux[0] * u1 - ux[1] * 1e-4,
                                   o[1] + ux[1] * u1 + ux[0] * 1e-4),
                                  (o[0] + ux[0] * u1 + ux[1] * 1e-4,
                                   o[1] + ux[1] * u1 - ux[0] * 1e-4),
                                  (o[0] + ux[0] * u0 + ux[1] * 1e-4,
                                   o[1] + ux[1] * u0 - ux[0] * 1e-4)]],
                                mf.FillRule.EvenOdd) ^ reg
        spans = []
        for lp in strip.to_polygons():
            us = [(x - o[0]) * ux[0] + (y - o[1]) * ux[1] for x, y in lp]
            spans.append((min(us), max(us)))
        if not spans:
            continue
        if len(spans) == 1 and spans[0][0] <= u0 + 1e-3 and \
                spans[0][1] >= u1 - 1e-3:
            out.append(w)
            continue
        for a, b in spans:
            poly = _rg_clip_u(uz, a, b)
            if len(poly) >= 3:
                piece = [(o[0] + ux[0] * u, o[1] + ux[1] * u, z)
                         for u, z in poly]
                out.append(_rg_Oriented(_rg_facing(piece, (n[0], n[1]))))
    return out


def _rg_clip_u(poly, a, b):
    """A (u, z) polygon cut to a ≤ u ≤ b."""
    for lim, sgn in ((a, 1.0), (b, -1.0)):
        res = []
        m = len(poly)
        for i in range(m):
            P, Q = poly[i], poly[(i + 1) % m]
            dp, dq = sgn * (P[0] - lim), sgn * (Q[0] - lim)
            if dp >= 0:
                res.append(P)
            if (dp >= 0) != (dq >= 0):
                t = dp / (dp - dq)
                res.append((P[0] + (Q[0] - P[0]) * t,
                            P[1] + (Q[1] - P[1]) * t))
        poly = res
        if not poly:
            break
    return poly


def _rg_newell(f):
    nx = ny = nz = 0.0
    m = len(f)
    for i in range(m):
        a, b = f[i], f[(i + 1) % m]
        nx += (a[1] - b[1]) * (a[2] + b[2])
        ny += (a[2] - b[2]) * (a[0] + b[0])
        nz += (a[0] - b[0]) * (a[1] + b[1])
    return nx, ny, nz


def _rg_area3(f):
    return 0.5 * math.sqrt(sum(c * c for c in _rg_newell(f)))


def _rg_facing(f, d):
    """``f`` turned so that its normal points along the horizontal
    direction ``d``."""
    n = _rg_newell(f)
    return list(reversed(f)) if n[0] * d[0] + n[1] * d[1] < 0 else list(f)


def _rg_outward(f, centre):
    m = len(f)
    cx = sum(q[0] for q in f) / m
    cy = sum(q[1] for q in f) / m
    return _rg_facing(f, (cx - centre[0], cy - centre[1]))


def _rg_up(f):
    n = _rg_newell(f)
    return list(reversed(f)) if n[2] < 0 else list(f)


def _rg_mono(pts, z0, a, ov, gov, eave):
    n = len(pts)
    L = [math.dist(pts[i], pts[(i + 1) % n]) for i in range(n)]
    e = int(eave) % n if eave is not None else max(range(n), key=lambda i: L[i])
    A, B = pts[e], pts[(e + 1) % n]
    dx, dy = B[0] - A[0], B[1] - A[1]
    ln = math.hypot(dx, dy)
    nin = (-dy / ln, dx / ln)
    t = _rg_tan(a)
    dists = [gov] * n
    dists[e] = ov
    P2 = _rg_offset_outline(pts, dists)

    def z(q):
        return z0 + ((q[0] - A[0]) * nin[0] + (q[1] - A[1]) * nin[1]) * t
    return [[(q[0], q[1], z(q)) for q in P2]], []


def _rg_split(pts, z0, a, off, ov, gov, rot):
    P, L, D = _rg_rect_frame(pts, rot)
    t = _rg_tan(a)
    m = D / 2
    xs = (-gov, L + gov)
    zf = lambda y: z0 + y * t                    # front, rises to the middle
    zb = lambda y: z0 + (D - y) * t + off        # back, higher in the middle
    front = [P(xs[0], -ov, zf(-ov)), P(xs[1], -ov, zf(-ov)),
             P(xs[1], m, zf(m)), P(xs[0], m, zf(m))]
    back = [P(xs[0], m, zb(m)), P(xs[1], m, zb(m)),
            P(xs[1], D + ov, zb(D + ov)), P(xs[0], D + ov, zb(D + ov))]
    band = [P(0, m, zf(m)), P(L, m, zf(m)), P(L, m, zb(m)), P(0, m, zb(m))]
    a, b = P(0, 0, 0), P(0, -1, 0)
    band = _rg_Oriented(_rg_facing(band, (b[0] - a[0], b[1] - a[1])))
    return [front, back], [band]


def _rg_butterfly(pts, z0, a, ov, gov, rot):
    P, L, D = _rg_rect_frame(pts, rot)
    t = _rg_tan(a)
    m = D / 2
    xs = (-gov, L + gov)
    z = lambda y: z0 + abs(y - m) * t
    f1 = [P(xs[0], -ov, z(-ov)), P(xs[1], -ov, z(-ov)),
          P(xs[1], m, z(m)), P(xs[0], m, z(m))]
    f2 = [P(xs[0], m, z(m)), P(xs[1], m, z(m)),
          P(xs[1], D + ov, z(D + ov)), P(xs[0], D + ov, z(D + ov))]
    return [f1, f2], []


def _rg_mroof(pts, z0, a, ov, gov, rot):
    P, L, D = _rg_rect_frame(pts, rot)
    t = _rg_tan(a)
    q = D / 4
    xs = (-gov, L + gov)
    out = []
    for y0, y1, ym in ((-ov, D / 2, q), (D / 2, D + ov, 3 * q)):
        z = lambda y, ym=ym: z0 + (q - abs(y - ym)) * t
        out.append([P(xs[0], y0, z(y0)), P(xs[1], y0, z(y0)),
                    P(xs[1], ym, z(ym)), P(xs[0], ym, z(ym))])
        out.append([P(xs[0], ym, z(ym)), P(xs[1], ym, z(ym)),
                    P(xs[1], y1, z(y1)), P(xs[0], y1, z(y1))])
    return out, []


def _rg_sawtooth(pts, z0, a, count, ov, gov, rot):
    P, L, D = _rg_rect_frame(pts, rot)
    count = max(1, min(30, count))
    t = _rg_tan(a)
    w = D / count
    xs = (-gov, L + gov)
    roof, walls = [], []
    for k in range(count):
        y0, y1 = k * w, (k + 1) * w
        ya = y0 - (ov if k == 0 else 0.0)
        h = z0 + w * t
        roof.append([P(xs[0], ya, z0 - (y0 - ya) * t), P(xs[1], ya,
                                                          z0 - (y0 - ya) * t),
                     P(xs[1], y1, h), P(xs[0], y1, h)])
        if k < count - 1:                    # the last one is an end wall
            q = [P(0, y1, z0), P(L, y1, z0), P(L, y1, h), P(0, y1, h)]
            a, b = P(0, 0, 0), P(0, 1, 0)
            walls.append(_rg_Oriented(_rg_facing(q, (b[0] - a[0], b[1] - a[1]))))
    return roof, walls


def _rg_barrel(pts, z0, a, ov, gov, rot, segs=16):
    P, L, D = _rg_rect_frame(pts, rot)
    a = max(5.0, min(89.0, a))
    R = (D / 2) / math.sin(math.radians(a))
    yc = D / 2
    zc = z0 - R * math.cos(math.radians(a))
    xs = (-gov, L + gov)
    half = math.radians(a) + (ov / R)
    out = []
    angs = [-half + 2 * half * i / segs for i in range(segs + 1)]
    for f0, f1 in zip(angs, angs[1:]):
        y0, y1 = yc + R * math.sin(f0), yc + R * math.sin(f1)
        z0_, z1_ = zc + R * math.cos(f0), zc + R * math.cos(f1)
        out.append([P(xs[0], y0, z0_), P(xs[1], y0, z0_),
                    P(xs[1], y1, z1_), P(xs[0], y1, z1_)])
    return out, []


def _rg_dome(pts, z0, a, ov, rings=10):
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    r = sum(math.dist(p, (cx, cy)) for p in pts) / len(pts)
    H = r * max(0.2, min(2.0, _rg_tan(a)))
    base = [(cx + (p[0] - cx) * (1 + ov / r), cy + (p[1] - cy) * (1 + ov / r))
            for p in pts]
    out = []
    prev = [(x, y, z0 - 0.0) for x, y in base]
    n = len(base)
    for k in range(1, rings + 1):
        th = 0.5 * math.pi * k / rings
        s = math.cos(th)
        z = z0 + H * math.sin(th)
        if k == rings:
            apex = (cx, cy, z0 + H)
            for i in range(n):
                out.append([prev[i], prev[(i + 1) % n], apex])
            break
        cur = [(cx + (x - cx) * s, cy + (y - cy) * s, z) for x, y in base]
        for i in range(n):
            out.append([prev[i], prev[(i + 1) % n], cur[(i + 1) % n], cur[i]])
        prev = cur
    return out


def _rg_helm(pts, z0, a, ov, rot):
    P, L, D = _rg_rect_frame(pts, rot)
    t = _rg_tan(a)
    hg = z0 + min(L, D) / 2 * t                  # gable peaks
    H = z0 + 2 * (hg - z0)                       # apex: rhombi stay planar
    c = [P(0, 0, z0), P(L, 0, z0), P(L, D, z0), P(0, D, z0)]
    g = [P(L / 2, 0, hg), P(L, D / 2, hg), P(L / 2, D, hg), P(0, D / 2, hg)]
    apex = P(L / 2, D / 2, H)
    roof, walls = [], []
    for i in range(4):
        # rhombus round corner i: gable peak of the side before, corner,
        # gable peak of the side after, apex
        q = [g[i - 1], c[i], g[i], apex]
        if abs(L - D) < 1e-6 * max(L, D):
            roof.append(q)
        else:
            roof.append([q[0], q[1], q[3]])
            roof.append([q[1], q[2], q[3]])
        walls.append([c[i], c[(i + 1) % 4], g[i]])
    del ov
    return roof, walls


def _rg_walls(pts, z0, roof):
    """A wall under every part of the roof that stands above the wall top
    along the footprint (gables, the high side of a shed …)."""
    try:
        import manifold3d as mf
    except Exception:  # noqa: BLE001
        return []
    out = []
    n = len(pts)
    for i in range(n):
        A, B = pts[i], pts[(i + 1) % n]
        dx, dy = B[0] - A[0], B[1] - A[1]
        Ln = math.hypot(dx, dy)
        if Ln < 1e-6:
            continue
        ux = (dx / Ln, dy / Ln)
        nn = (-ux[1], ux[0])
        trap = []
        for f in roof:
            # cut the face with the wall's vertical plane
            ds = [(q[0] - A[0]) * nn[0] + (q[1] - A[1]) * nn[1] for q in f]
            cut = []
            m = len(f)
            for j in range(m):
                q0, q1 = f[j], f[(j + 1) % m]
                d0, d1 = ds[j], ds[(j + 1) % m]
                if abs(d0) < 1e-7:
                    cut.append(q0)
                if (d0 > 1e-7 and d1 < -1e-7) or (d0 < -1e-7 and d1 > 1e-7):
                    s = d0 / (d0 - d1)
                    cut.append(tuple(q0[k] + (q1[k] - q0[k]) * s
                                     for k in range(3)))
            if len(cut) < 2:
                continue
            uz = [((q[0] - A[0]) * ux[0] + (q[1] - A[1]) * ux[1], q[2])
                  for q in cut]
            uz.sort()
            (u0, za), (u1, zb) = uz[0], uz[-1]
            if u1 - u0 < 1e-6:
                continue
            # clip to the wall's length
            def zat(u):
                return za + (zb - za) * (u - u0) / (u1 - u0)
            lo, hi = max(0.0, u0), min(Ln, u1)
            if hi - lo < 1e-6:
                continue
            z_lo, z_hi = zat(lo), zat(hi)
            if max(z_lo, z_hi) <= z0 + 0.01:
                continue
            trap.append([(lo, z0), (hi, z0), (hi, max(z0, z_hi)),
                         (lo, max(z0, z_lo))])
        if not trap:
            continue
        cs = mf.CrossSection.batch_boolean(
            [mf.CrossSection([t], mf.FillRule.Positive)
             if _rg_area(t) > 0 else mf.CrossSection([t[::-1]],
                                                  mf.FillRule.Positive)
             for t in trap], mf.OpType.Add)
        for lp in cs.to_polygons():
            if len(lp) < 3 or abs(_rg_area([tuple(q) for q in lp])) < 1e-4:
                continue
            w = [(A[0] + ux[0] * u, A[1] + ux[1] * u, z) for u, z in lp]
            out.append(_rg_Oriented(_rg_facing(w, (ux[1], -ux[0]))))
    return out


# ---------------------------------------------------------------------------
# Undo
# ---------------------------------------------------------------------------

def _make_command_class():
    from core.history import Command, InsertGroupCommand

    class RoofTilesCommand(Command):
        """Insert a new covering, or replace ``old`` by ``new`` in place.
        ``select=False`` (the preview) leaves the user's selection alone."""

        def __init__(self, new, old=None, select=True, mats=()):
            self.new = new
            self.old = old
            self.select = select
            self.mats = list(mats)
            self._saved = None
            self._insert = InsertGroupCommand(new) if old is None else None
            self._owner = None
            self._index = None

        def _owner_of(self, scene, g):
            if g in scene.groups:
                return scene.groups
            ctx = getattr(scene, "edit_group", None)
            kids = getattr(ctx, "children", None)
            if kids is not None and g in kids:
                return kids
            return None

        def do(self, scene):
            reg = getattr(scene, "materials", None)
            if isinstance(reg, dict):
                try:
                    from core.materials import register
                    for m in self.mats:
                        register(reg, m)
                except Exception:  # noqa: BLE001 — names only, never fatal
                    pass
            self._saved = set(scene.selection)
            if self._insert is not None:
                self._insert.do(scene)
            else:
                owner = self._owner_of(scene, self.old)
                if owner is None:
                    raise RuntimeError("The roof covering is no longer in "
                                       "the model.")
                i = owner.index(self.old)
                owner[i] = self.new
                self._owner, self._index = owner, i
                scene.selection.discard(self.old)
            scene.selection.clear()
            if self.select:
                scene.selection.add(self.new)
            else:
                scene.selection.update(self._saved - {self.old})
            scene.version += 1

        def undo(self, scene):
            if self._insert is not None:
                self._insert.undo(scene)
            elif self._owner is not None and self.new in self._owner:
                self._owner[self._owner.index(self.new)] = self.old
            scene.selection.discard(self.new)
            if self.select:
                if self.old is not None:
                    scene.selection.add(self.old)
            elif self.old is not None and self._saved and \
                    self.old in self._saved:
                scene.selection.add(self.old)
            scene.version += 1

    return RoofTilesCommand


_CMD = None


def run_roof(viewport, data, p, old=None, progress=None, select=True):
    """Build and insert (or replace ``old``) as one undo step. Returns the
    command (``cmd.info`` holds the statistics)."""
    global _CMD
    if _CMD is None:
        _CMD = _make_command_class()
    name = old.name if old is not None else _next_name(viewport.scene)
    g, info = make_roof(data, p, name, progress)
    if old is not None:
        g.layer = old.layer
    else:
        lay = getattr(viewport.scene, "current_layer", None)
        if isinstance(lay, str):
            g.layer = lay
    cmd = _CMD(g, old, select, materials_of(normalize_params(p)))
    cmd.info = info
    hist = viewport.history
    hist.execute(cmd)
    err = getattr(hist, "last_error", None)
    if err:
        raise RuntimeError(err)
    notify = getattr(viewport, "notify_scene_changed", None)
    if notify:
        notify()
    viewport.update()
    return cmd


def _next_name(scene):
    used = {g.name for g in scene.groups}
    if "Roof Tiles" not in used:
        return "Roof Tiles"
    n = 2
    while f"Roof Tiles {n}" in used:
        n += 1
    return f"Roof Tiles {n}"


def _unit():
    try:
        from core import units
        code = units.model_unit()
        short = {"in": "in", "in-frac": "in", "ft": "ft", "ft-in": "ft",
                 "ft-in-frac": "ft"}.get(code, code)
        return units.bare_number_scale(), short
    except Exception:  # noqa: BLE001
        return 1.0, "m"


def _fmt(v, scale, unit, dec=2):
    return f"{v / scale:,.{dec}f} {unit}"


def result_text(info):
    parts = [f"{info['tiles'] + info['cut']:,} tiles "
             f"({info['cut']:,} cut)"]
    if info.get("verge"):
        parts.append(f"{info['verge']} verge tiles")
    rt = info.get("ridge", 0) + info.get("hip", 0)
    if rt:
        parts.append(f"{rt} ridge/hip tiles")
    if info.get("mono"):
        parts.append(f"{info['mono']} mono-pitch ridge tiles")
    g = info.get("gauge") or []
    if g:
        lo, hi = min(g) * 100, max(g) * 100
        parts.append(f"gauge {lo:.1f} cm" if hi - lo < 0.05
                     else f"gauge {lo:.1f}–{hi:.1f} cm")
    st = info.get("stretch") or []
    if st:
        dev = max(st, key=lambda v: abs(v - 1.0))
        if abs(dev - 1.0) > 0.0005:
            parts.append(f"cover width fitted {100 * (dev - 1):+.1f} %")
    return " · ".join(parts)


# ---------------------------------------------------------------------------
# The dialog
# ---------------------------------------------------------------------------

def _make_dialog_class():
    from PySide6.QtCore import QEventLoop, Qt, QTimer
    from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox,
                                   QDialog, QDoubleSpinBox, QFileDialog,
                                   QFormLayout, QGridLayout, QGroupBox,
                                   QHBoxLayout, QLabel, QMessageBox,
                                   QPushButton, QVBoxLayout)

    class RoofTilesDialog(QDialog):
        _PV_ON = ("QPushButton { background: #2e9e4f; color: white; "
                  "font-weight: bold; border: 1px solid #1f7a3a; "
                  "border-radius: 3px; padding: 3px 8px; }")
        _BANNER = {
            "live": "background: #1f5f33; color: #e8ffe9;",
            "busy": "background: #7a5a12; color: #fff6e0;",
            "paused": "background: #5c4a1a; color: #ffe9b8;",
            "error": "background: #7a1f1f; color: #ffecec;",
        }

        def __init__(self, viewport, data, old=None, parent=None):
            super().__init__(parent)
            self.viewport = viewport
            self.data = data
            self.old = old
            self.scale_m, self.ulabel = _unit()
            self.p = (normalize_params(roof_data(old).get("params"))
                      if old is not None else load_params())
            if self.p["preset"] == CUSTOM and not self.p.get("custom"):
                self.p["preset"] = "frankfurt"
            self.est = None
            self._preview_cmd = None
            self._block = None
            self._busy = False
            self._computing = False
            self._timer = QTimer(self)
            self._timer.setSingleShot(True)
            self._timer.setInterval(350)
            self._timer.timeout.connect(self._refresh_preview)
            what = "Edit Roof Tiles" if old is not None else "Cover Roof"
            self.setWindowTitle(f"{TITLE} {VERSION} — {what}")
            self.setModal(False)
            self.setAttribute(Qt.WA_DeleteOnClose, True)
            self._sel_note = ""
            self._sig = self._selection_sig()
            self._sel_timer = QTimer(self)
            self._sel_timer.setInterval(400)
            self._sel_timer.timeout.connect(self._poll_selection)
            self._build_ui()
            self._load_into_ui()
            self._sel_timer.start()

        # ---- UI ------------------------------------------------------------
        def _dspin(self, lo, hi, dec=3, tip=""):
            s = QDoubleSpinBox(self)
            sc = self.scale_m
            s.setRange(lo / sc, hi / sc)
            s.setDecimals(dec)
            s.setSingleStep(0.01 / sc if sc <= 1.0 else 0.01)
            s.setSuffix(f" {self.ulabel}")
            s.setKeyboardTracking(False)
            s.setMinimumWidth(105)
            s.setToolTip(tip)
            s.valueChanged.connect(self._changed)
            return s

        def _check(self, text, tip=""):
            c = QCheckBox(text, self)
            c.setToolTip(tip)
            c.toggled.connect(self._changed)
            return c

        def _build_ui(self):
            lay = QVBoxLayout(self)

            src = QGroupBox("Roof", self)
            sl = QVBoxLayout(src)
            self.src_lbl = QLabel(self)
            self.src_lbl.setWordWrap(True)
            self.src_lbl.setMinimumWidth(420)
            sl.addWidget(self.src_lbl)
            srow = QHBoxLayout()
            self.follow = QCheckBox("Follow selection", self)
            self.follow.setToolTip(
                "While the dialog is open, a changed selection is read again "
                "by itself: add or remove roof faces and the covering "
                "follows.")
            self.follow.toggled.connect(self._follow_toggled)
            srow.addWidget(self.follow)
            srow.addStretch(1)
            self.b_read = QPushButton("↻ Read selection", self)
            self.b_read.setToolTip("Take the selected roof faces as the "
                                   "roof now.")
            self.b_read.clicked.connect(lambda: self._read_selection(True))
            srow.addWidget(self.b_read)
            sl.addLayout(srow)
            lay.addWidget(src)

            tbox = QGroupBox("Tile", self)
            tl = QFormLayout(tbox)
            self.preset = QComboBox(self)
            for pr in PRESETS:
                self.preset.addItem(pr["name"], pr["id"])
            self.preset.insertSeparator(self.preset.count())
            self.preset.addItem("Custom tile (.igz / .obj / selection)",
                                CUSTOM)
            self.preset.currentIndexChanged.connect(self._preset_changed)
            tl.addRow("Tile:", self.preset)
            self.tile_lbl = QLabel(self)
            self.tile_lbl.setWordWrap(True)
            tl.addRow(self.tile_lbl)
            crow = QHBoxLayout()
            self.b_load = QPushButton("Load tile…", self)
            self.b_load.setToolTip(
                "A tile of your own from an .igz or .obj file: modelled "
                "lying flat (Z up), the length along the slope. The longer "
                "side is taken as its length.")
            self.b_load.clicked.connect(self._load_file)
            self.b_sel = QPushButton("From selection", self)
            self.b_sel.setToolTip(
                "Use the selected group (or faces) as the tile: modelled "
                "lying flat (Z up). Select the roof faces again afterwards.")
            self.b_sel.clicked.connect(self._load_selection)
            crow.addWidget(self.b_load)
            crow.addWidget(self.b_sel)
            crow.addStretch(1)
            self.custom_row = QLabel("Custom tile:", self)
            tl.addRow(self.custom_row, crow)
            self._crow_widgets = (self.b_load, self.b_sel)
            self.W = self._dspin(0.03, 2.0, 3,
                                 "Cover width (Deckbreite): how far one tile "
                                 "reaches across the roof. Between two "
                                 "verges it is fitted so the tiles end "
                                 "exactly on both.")
            tl.addRow("Cover width:", self.W)
            grow = QHBoxLayout()
            self.Lmin = self._dspin(0.03, 2.0, 3, "Shortest batten gauge "
                                    "(Lattweite) the tile allows.")
            self.Lmax = self._dspin(0.03, 2.0, 3, "Longest batten gauge the "
                                    "tile allows. The gauge is fitted "
                                    "between eave and ridge inside this "
                                    "range, so every course is a full one.")
            grow.addWidget(self.Lmin)
            grow.addWidget(QLabel("to", self))
            grow.addWidget(self.Lmax)
            grow.addStretch(1)
            tl.addRow("Batten gauge:", grow)
            self.detail = QComboBox(self)
            self.detail.addItem("Low (fast)", "low")
            self.detail.addItem("Medium", "medium")
            self.detail.addItem("High (close-ups)", "high")
            self.detail.setToolTip("How round the tile profile is drawn.")
            self.detail.currentIndexChanged.connect(self._changed)
            tl.addRow("Detail:", self.detail)
            self.color = QComboBox(self)
            for name, _c in COLORS:
                self.color.addItem(name, name)
            self.color.setToolTip("Paints the tiles with the named material "
                                  "«Roof tile – …» — change it later in the "
                                  "materials like any other.")
            self.color.currentIndexChanged.connect(self._changed)
            tl.addRow("Colour:", self.color)
            lay.addWidget(tbox)

            lbox = QGroupBox("Laying", self)
            gl = QGridLayout(lbox)
            self.eave_ov = self._dspin(0, 0.5, 3, "How far the first course "
                                       "reaches past the eave (into the "
                                       "gutter).")
            self.ridge_gap = self._dspin(0, 0.5, 3, "Space between the top "
                                         "course and the ridge line (under "
                                         "the ridge tiles).")
            self.verge = QComboBox(self)
            for k in VERGE_MODES:
                self.verge.addItem(VERGE_LABELS[k], k)
            self.verge.setToolTip(
                "Verge tiles (left and right) with a lip down over the gable, "
                "the cover width fitted between them — or the plain tiles cut "
                "at the verge and the edge closed: a mortar bead over the cut "
                "ends (Mediterranean), a verge board, a verge flashing of "
                "sheet metal — or left open.")
            self.verge.currentIndexChanged.connect(self._changed)
            self.verge_ov = self._dspin(0, 0.5, 3, "How far the tiles reach "
                                        "past the gable edge.")
            self.valley_gap = self._dspin(0, 0.5, 3, "Open valley: the tiles "
                                          "stop this far from the valley "
                                          "line, on each side.")
            self.hip_gap = self._dspin(0, 0.5, 3, "The tiles stop this far "
                                       "from the hip line (under the hip "
                                       "tiles).")
            self.cut_gap = self._dspin(0, 0.5, 3, "Gap at holes (chimney, "
                                       "skylight) and at edges against a "
                                       "wall.")
            self.offset = self._dspin(-0.5, 0.5, 3,
                                      "Lift the whole covering off the "
                                      "selected faces (e.g. the height of "
                                      "battens and counter-battens when the "
                                      "faces are the rafters).")
            rows = [("Eave overhang:", self.eave_ov, "Verge:", self.verge),
                    ("Gap at ridge:", self.ridge_gap, "Verge overhang:",
                     self.verge_ov),
                    ("Gap at valley:", self.valley_gap, "Gap at hip:",
                     self.hip_gap),
                    ("Gap at holes:", self.cut_gap, "Lift off faces:",
                     self.offset)]
            for r, (a, wa, b, wb) in enumerate(rows):
                gl.addWidget(QLabel(a, self), r, 0)
                gl.addWidget(wa, r, 1)
                gl.addWidget(QLabel(b, self), r, 2)
                gl.addWidget(wb, r, 3)
            lay.addWidget(lbox)

            rbox = QGroupBox("Ridge, hips, valleys and holes", self)
            rl = QGridLayout(rbox)
            self.c_ridge = self._check("Ridge tiles", "Ridge tiles along "
                                       "every ridge.")
            self.c_hips = self._check("Hip tiles", "Ridge tiles along every "
                                      "hip, laid from the eave upwards.")
            self.c_mono = self._check("Mono-pitch ridge",
                                      "A ridge piece with a lip down along "
                                      "the free top edge of a mono-pitch "
                                      "roof.")
            self.c_end = self._check("Ridge ends:", "Close the ridge at "
                                     "the gables.")
            self.endstyle = QComboBox(self)
            for key, label in END_STYLES:
                self.endstyle.addItem(label, key)
            self.endstyle.setToolTip(
                "End stone: domed front with an apron down over the verge "
                "tiles (like a classic ridge end stone). End disc: a flat "
                "disc with the same apron. Ornamental disc: a larger disc "
                "with a fan.")
            self.endstyle.currentIndexChanged.connect(self._changed)
            self.c_flash = self._check("Valley flashing", "A metal strip "
                                       "under every valley.")
            rl.addWidget(self.c_ridge, 0, 0)
            rl.addWidget(self.c_hips, 0, 1)
            rl.addWidget(self.c_mono, 0, 2)
            erow = QHBoxLayout()
            erow.addWidget(self.c_end)
            erow.addWidget(self.endstyle, 1)
            rl.addLayout(erow, 1, 0, 1, 2)
            rl.addWidget(self.c_flash, 1, 2)
            self.c_hole = self._check(
                "Hole flashing", "A flashing frame round every hole in the "
                "roof faces (roof window, chimney, dormer opening): an "
                "upstand round the opening and a collar lying on the tiles.")
            rl.addWidget(self.c_hole, 2, 0)
            lay.addWidget(rbox)

            self.est_lbl = QLabel(self)
            self.est_lbl.setWordWrap(True)
            lay.addWidget(self.est_lbl)
            self.force = self._check(
                "Build anyway — at my own risk",
                "Over the safe limit IngeTrazo may become very slow. Never "
                "remembered.")
            lay.addWidget(self.force)

            self.pv_lbl = QLabel(self)
            self.pv_lbl.setWordWrap(True)
            self.pv_lbl.setVisible(False)
            lay.addWidget(self.pv_lbl)

            row = QHBoxLayout()
            self.preview = QPushButton("Preview", self)
            self.preview.setCheckable(True)
            self.preview.toggled.connect(self._preview_toggled)
            reset = QPushButton("Reset", self)
            reset.setToolTip("Back to the default settings of this tile.")
            reset.clicked.connect(self._reset)
            self.ok_btn = QPushButton("OK", self)
            self.ok_btn.setDefault(True)
            self.ok_btn.clicked.connect(self.accept)
            cancel = QPushButton("Cancel", self)
            cancel.clicked.connect(self.reject)
            row.addWidget(self.preview)
            row.addWidget(reset)
            row.addStretch(1)
            row.addWidget(self.ok_btn)
            row.addWidget(cancel)
            lay.addLayout(row)
            self._style_preview(False)

        def _set_len(self, spin, v):
            spin.setValue(v / self.scale_m)

        def _load_into_ui(self):
            self._busy = True
            p = self.p
            self.preset.setCurrentIndex(max(0, self.preset.findData(
                p["preset"])))
            for spin, k in ((self.W, "W"), (self.Lmin, "Lmin"),
                            (self.Lmax, "Lmax"), (self.eave_ov, "eave_ov"),
                            (self.ridge_gap, "ridge_gap"),
                            (self.verge_ov, "verge_ov"),
                            (self.valley_gap, "valley_gap"),
                            (self.hip_gap, "hip_gap"),
                            (self.cut_gap, "cut_gap"),
                            (self.offset, "offset")):
                self._set_len(spin, p[k])
            self.detail.setCurrentIndex(max(0, self.detail.findData(
                p["detail"])))
            self.color.setCurrentIndex(max(0, self.color.findData(
                p["color"])))
            self.verge.setCurrentIndex(max(0, self.verge.findData(
                p["verge"])))
            self.c_ridge.setChecked(p["ridge"])
            self.c_hips.setChecked(p["hips"])
            self.c_mono.setChecked(p["mono"])
            self.c_end.setChecked(p["endcaps"])
            self.endstyle.setCurrentIndex(max(0, self.endstyle.findData(
                p["endstyle"])))
            self.endstyle.setEnabled(p["endcaps"])
            self.c_flash.setChecked(p["flashing"])
            self.c_hole.setChecked(p["holeflash"])
            self.follow.setChecked(p["follow"])
            self.force.setChecked(False)
            p["force"] = False
            self._busy = False
            self._sync()

        def _read_ui(self):
            p, s = self.p, self.scale_m
            p["preset"] = self.preset.currentData() or "frankfurt"
            for spin, k in ((self.W, "W"), (self.Lmin, "Lmin"),
                            (self.Lmax, "Lmax"), (self.eave_ov, "eave_ov"),
                            (self.ridge_gap, "ridge_gap"),
                            (self.verge_ov, "verge_ov"),
                            (self.valley_gap, "valley_gap"),
                            (self.hip_gap, "hip_gap"),
                            (self.cut_gap, "cut_gap"),
                            (self.offset, "offset")):
                p[k] = spin.value() * s
            p["detail"] = self.detail.currentData()
            p["color"] = self.color.currentData()
            p["verge"] = self.verge.currentData()
            p["ridge"] = self.c_ridge.isChecked()
            p["hips"] = self.c_hips.isChecked()
            p["mono"] = self.c_mono.isChecked()
            p["endcaps"] = self.c_end.isChecked()
            p["endstyle"] = self.endstyle.currentData() or "stone"
            self.endstyle.setEnabled(p["endcaps"])
            p["flashing"] = self.c_flash.isChecked()
            p["holeflash"] = self.c_hole.isChecked()
            p["follow"] = self.follow.isChecked()
            p["force"] = self.force.isChecked()
            custom = p.get("custom")
            self.p = normalize_params(p)
            self.p["custom"] = custom

        def _preset_changed(self, *_a):
            if self._busy:
                return
            pid = self.preset.currentData()
            if pid == CUSTOM:
                if not self.p.get("custom"):
                    self._busy = True
                    self.preset.setCurrentIndex(max(0, self.preset.findData(
                        self.p["preset"] if self.p["preset"] != CUSTOM
                        else "frankfurt")))
                    self._busy = False
                    self._sync()
                    self.viewport.flash_status(
                        f"{TITLE}: load a tile first (Load tile… or From "
                        f"selection).", 5000)
                    return
                c = self.p["custom"]
                vals = {"W": round(c["Wt"] * 0.9, 3),
                        "Lmin": round(c["Lt"] * 0.78, 3),
                        "Lmax": round(c["Lt"] * 0.78, 3)}
                verge = "board"
            else:
                pr = PRESET_BY_ID[pid]
                vals = {"W": pr["W"], "Lmin": pr["Lmin"], "Lmax": pr["Lmax"]}
                verge = pr["verge"]
            self._busy = True
            for k, spin in (("W", self.W), ("Lmin", self.Lmin),
                            ("Lmax", self.Lmax)):
                self._set_len(spin, vals[k])
            self.verge.setCurrentIndex(max(0, self.verge.findData(verge)))
            self._busy = False
            self._changed()

        def _set_custom(self, rec):
            self.p["custom"] = rec
            self._busy = True
            self.preset.setCurrentIndex(self.preset.findData(CUSTOM))
            self._busy = False
            self._preset_changed()

        def _load_file(self):
            path, _f = QFileDialog.getOpenFileName(
                self, "Load tile", "", "Tile (*.igz *.obj)")
            if not path:
                return
            try:
                rec = custom_from_file(path)
            except Exception as exc:  # noqa: BLE001
                QMessageBox.warning(self, TITLE, f"Could not load the tile:\n"
                                    f"{exc}")
                return
            self._set_custom(rec)

        def _load_selection(self):
            try:
                rec = custom_from_scene(self.viewport.scene)
            except Exception as exc:  # noqa: BLE001
                QMessageBox.warning(self, TITLE, str(exc))
                return
            was = self.follow.isChecked()
            if was:                          # the tile is no roof
                self.follow.setChecked(False)
            self._set_custom(rec)
            self.viewport.flash_status(
                f"{TITLE}: tile taken from the selection "
                f"({len(rec['polys'])} faces).", 5000)

        def _sync(self):
            """Roof text, tile text, estimate — no building."""
            p = self.p
            s, u = self.scale_m, self.ulabel
            is_c = p["preset"] == CUSTOM
            spec = tile_spec(p)
            if is_c:
                c = p["custom"]
                txt = (f"<b>{c['name']}</b> — custom, "
                       f"{_fmt(c['Wt'], s, u, 3)} × {_fmt(c['Lt'], s, u, 3)},"
                       f" {len(c['polys'])} faces")
            else:
                pr = PRESET_BY_ID[p["preset"]]
                txt = (f"{pr['region']} · {_fmt(pr['Wt'], s, u, 3)} × "
                       f"{_fmt(pr['Lt'], s, u, 3)}")
            gm = 0.5 * (spec["Lmin"] + spec["Lmax"])
            txt += f" · ≈ {1.0 / (spec['W'] * gm):.1f} tiles/m²"
            self.tile_lbl.setText(txt)
            try:
                self.est = estimate(self.data, p)
            except RoofError as exc:
                self.est = None
                self.src_lbl.setText(f"<b>{exc}</b>")
                self.est_lbl.setText("")
                self.force.setVisible(False)
                self.ok_btn.setEnabled(False)
                self._block = str(exc)
                return
            except Exception as exc:  # noqa: BLE001
                self.est = None
                self.src_lbl.setText(f"<b>The roof cannot be read:</b> {exc}")
                self.ok_btn.setEnabled(False)
                self._block = str(exc)
                return
            e = self.est
            np_ = len(e["planes"])
            order = ["eave", "ridge", "hip", "valley", "verge",
                     "mono-pitch ridge", "break", "abutment", "cut edge"]
            ed = e["edges"]
            parts = [f"{ed[k]} {k}{'s' if ed[k] > 1 and k[-1] != 's' else ''}"
                     for k in order if ed.get(k)]
            tilts = sorted({round(pl.tilt) for pl in e["planes"]})
            ttxt = ", ".join(f"{t}°" for t in tilts[:6])
            txt = (f"{np_} roof plane{'s' if np_ > 1 else ''} · "
                   f"{e['area']:,.1f} m² · pitch {ttxt}<br>"
                   + " · ".join(parts))
            if self._sel_note:
                txt += f"<br><span style='color:#5fbf73'>{self._sel_note}</span>"
            elif self.old is not None:
                txt += "<br>Roof faces stored with the covering."
            self.src_lbl.setText(txt)
            n = e["tiles"]
            too_big = n > MAX_TILES
            if too_big:
                msg = (f"<b>≈ {n:,} tiles — too many</b> (safe limit "
                       f"{MAX_TILES:,}).")
                col = "#e0483e"
            elif n > WARN_TILES:
                msg, col = f"≈ {n:,} tiles — large, slow to build.", "#e8912d"
            else:
                msg, col = f"≈ {n:,} tiles.", ""
            if p["verge"] == "tiles" and ed.get("verge") and spec["half"]:
                msg += (" <span style='color:#e8912d'>Verge tiles are not "
                        "made for tiles laid half-offset — cut flush is "
                        "used.</span>")
            self.est_lbl.setText(msg)
            self.est_lbl.setStyleSheet(f"color: {col};" if col else "")
            if not too_big and self.force.isChecked():
                self.force.blockSignals(True)
                self.force.setChecked(False)
                self.force.blockSignals(False)
                p["force"] = False
            self.force.setVisible(too_big)
            allowed = (not too_big) or self.force.isChecked()
            self.ok_btn.setEnabled(allowed)
            self._block = None if allowed else (
                f"Over the safe limit of {MAX_TILES:,} tiles — tick «Build "
                f"anyway».")
            if self.isVisible():
                QTimer.singleShot(0, self.adjustSize)

        def _banner(self, kind, text):
            self.pv_lbl.setStyleSheet(
                self._BANNER[kind] + " padding: 6px 8px; border-radius: 3px;")
            self.pv_lbl.setText(text)
            self.pv_lbl.setVisible(True)

        def _style_preview(self, on):
            if on:
                self.preview.setText("● Live Preview ON")
                self.preview.setStyleSheet(self._PV_ON)
                self.preview.setToolTip("The preview follows every change by "
                                        "itself — click to switch it off.")
            else:
                self.preview.setText("Preview")
                self.preview.setStyleSheet("")
                self.preview.setToolTip("Show the covering in the model; it "
                                        "then updates by itself on every "
                                        "change.")
                self.pv_lbl.setVisible(False)
            if self.isVisible():
                QTimer.singleShot(0, self.adjustSize)

        def _changed(self, *_a):
            if self._busy:
                return
            self._read_ui()
            self._sync()
            if self.preview.isChecked():
                if not self._block:
                    self._banner("busy", "⟳ Updating the preview…")
                self._timer.start()

        def _reset(self):
            keep = self.p.get("custom")
            pid = self.p["preset"]
            self.p = default_params()
            self.p["custom"] = keep
            self.p["preset"] = pid if (pid != CUSTOM or keep) else "frankfurt"
            if pid in PRESET_BY_ID:
                pr = PRESET_BY_ID[pid]
                self.p.update(W=pr["W"], Lmin=pr["Lmin"], Lmax=pr["Lmax"],
                              verge=pr["verge"])
            self._load_into_ui()
            if pid == CUSTOM and keep:
                self._preset_changed()
            else:
                self._changed()

        # ---- building ------------------------------------------------------
        def _progress(self, pct):
            self._banner("busy", f"⟳ Laying the tiles… {pct} %")
            QApplication.processEvents(QEventLoop.ExcludeUserInputEvents)

        def _selection_sig(self):
            try:
                return frozenset(id(e) for e in self.viewport.scene.selection)
            except Exception:  # noqa: BLE001
                return frozenset()

        def _poll_selection(self):
            if self._computing or not self.follow.isChecked():
                return
            sig = self._selection_sig()
            if sig != self._sig:
                self._sig = sig
                self._read_selection(False)

        def _follow_toggled(self, on):
            if self._busy:
                return
            self.p["follow"] = bool(on)
            if on:
                self._sig = self._selection_sig()
                self._read_selection(False)

        @staticmethod
        def _key(data):
            return sorted(json.dumps([[round(v, 5) for v in q]
                                      for q in f["outer"]])
                          + json.dumps([[[round(v, 5) for v in q] for q in h]
                                        for h in f.get("holes") or []])
                          for f in data["faces"])

        def _read_selection(self, manual):
            if self._computing:
                return
            data = gather(self.viewport.scene)
            if not data["faces"]:
                if manual:
                    self.viewport.flash_status(
                        f"{TITLE}: no sloped faces in the selection — the "
                        f"roof stays as it is.", 4000)
                return
            if not manual and self._key(data) == self._key(self.data):
                return
            self.data = data
            self._sel_note = (f"↻ Selection read again "
                              f"({time.strftime('%H:%M:%S')}): "
                              f"{len(data['faces'])} faces")
            self._sync()
            if self.preview.isChecked():
                if not self._block:
                    self._banner("busy", "⟳ Updating the preview…")
                self._timer.start()

        def _run(self, select=True):
            self._computing = True
            try:
                return run_roof(self.viewport, self.data, self.p, self.old,
                                self._progress, select)
            finally:
                self._computing = False

        def _undo_preview(self):
            cmd = self._preview_cmd
            self._preview_cmd = None
            if cmd is None:
                return
            stack = getattr(self.viewport.history, "undo_stack", [])
            if stack and stack[-1] is cmd:
                self.viewport.history.undo()
                self.viewport.update()

        def _refresh_preview(self):
            if self._computing:
                self._timer.start()
                return
            self._undo_preview()
            if not self.preview.isChecked():
                return
            if self._block:
                self._banner("paused", f"⏸ <b>Preview paused</b> — "
                             f"{self._block} It comes back by itself.")
                return
            self._banner("busy", "⟳ Updating the preview…")
            QApplication.processEvents(QEventLoop.ExcludeUserInputEvents)
            try:
                self._preview_cmd = self._run(select=False)
                self._preview_cmd.key = self._state_key()
                info = self._preview_cmd.info
                self._banner("live", "● <b>LIVE PREVIEW</b> — "
                             + result_text(info)
                             + f" ({info['seconds']:.1f} s)"
                             + " · changes apply instantly")
            except Exception as exc:  # noqa: BLE001
                self._preview_cmd = None
                self._banner("error", f"Preview failed: {exc}")

        def _preview_toggled(self, on):
            self._style_preview(on)
            if on:
                self._refresh_preview()
            else:
                self._timer.stop()
                self._undo_preview()

        # ---- close ---------------------------------------------------------
        def _state_key(self):
            p = {k: v for k, v in self.p.items() if k != "follow"}
            return (self._key(self.data), json.dumps(p, sort_keys=True))

        def _keep_preview(self):
            cmd = self._preview_cmd
            if cmd is None or getattr(cmd, "key", None) != self._state_key():
                return None
            stack = getattr(self.viewport.history, "undo_stack", [])
            if not stack or stack[-1] is not cmd:
                return None
            scene = self.viewport.scene
            cmd.select = True
            scene.selection.clear()
            scene.selection.add(cmd.new)
            scene.version += 1
            self._preview_cmd = None
            notify = getattr(self.viewport, "notify_scene_changed", None)
            if notify:
                notify()
            self.viewport.update()
            return cmd

        def accept(self):
            if self._computing:
                return
            self._sel_timer.stop()
            self._read_ui()
            self._timer.stop()
            save_params(self.p)
            cmd = self._keep_preview()
            if cmd is None:
                self._undo_preview()
                try:
                    cmd = self._run()
                except Exception as exc:  # noqa: BLE001
                    QMessageBox.warning(self, TITLE, str(exc))
                    self._sel_timer.start()
                    return
            info = cmd.info
            self.viewport.flash_status(
                f"{TITLE}: «{cmd.new.name}» — {result_text(info)} in "
                f"{info['seconds']:.1f} s (one undo step)", 7000)
            super().accept()

        def reject(self):
            if self._computing:
                return
            self._sel_timer.stop()
            self._timer.stop()
            self._undo_preview()
            self._read_ui()
            save_params(self.p)
            super().reject()

    return RoofTilesDialog


_DIALOG = None
_OPEN = None


def _dialog(viewport, data, old, parent):
    global _DIALOG, _OPEN
    if _DIALOG is None:
        _DIALOG = _make_dialog_class()
    if _OPEN is not None:
        try:
            _OPEN.reject()
        except RuntimeError:
            pass
    dlg = _DIALOG(viewport, data, old, parent or viewport.window())
    _OPEN = dlg
    dlg.show()
    dlg.raise_()
    return dlg


def selected_roof(scene):
    from core.group import Group
    for ent in scene.selection:
        if isinstance(ent, Group) and roof_data(ent) is not None:
            return ent
    return None


def show_cover(viewport, parent=None):
    data = gather(viewport.scene)
    if not data["faces"]:
        viewport.flash_status(
            f"{TITLE}: select the roof faces (or the group that holds them) "
            f"first.", 5000)
        return None
    return _dialog(viewport, data, None, parent)


def show_edit(viewport, parent=None):
    g = selected_roof(viewport.scene)
    if g is None:
        viewport.flash_status(
            f"{TITLE}: select a roof covering made with this plugin first.",
            5000)
        return None
    rec = roof_data(g)
    data = {"faces": [{"outer": [tuple(q) for q in f["outer"]],
                       "holes": [[tuple(q) for q in h]
                                 for h in f.get("holes") or []]}
                      for f in rec.get("faces", [])],
            "shapes": list(rec.get("shapes") or [])}
    return _dialog(viewport, data, g, parent)

# ---------------------------------------------------------------------------
# Create Roof… — the roof shape from a footprint
# ---------------------------------------------------------------------------

SHAPE_KIND = "roof_shape"
GEN_SETTINGS_KEY = "plugins/roof_tile_tool/shape"
PITCH_LABEL = {"mansard": "Lower pitch:", "gambrel": "Lower pitch:",
               "bonnet": "Kick pitch:", "saltbox": "Front pitch:",
               "halfhip": "Pitch:", "dutch": "Pitch:", "dome": "Rise:"}
PITCH2_LABEL = {"halfhip": "Hip pitch (top):", "dutch": "Hip pitch (ends):",
                "saltbox": "Back pitch:", "mansard": "Upper pitch:",
                "gambrel": "Upper pitch:", "bonnet": "Main pitch:"}
RATIO_LABEL = {"halfhip": "Hip starts at:", "dutch": "Gablet starts at:"}
BRK_LABEL = {"mansard": "Break height:", "gambrel": "Break height:",
             "bonnet": "Kick height:"}


def gen_default_params() -> dict:
    p = {"type": "gable", "pitch": 38.0, "pitch2": 38.0, "ratio": 0.65,
         "brk": 2.4, "offset": 0.8, "count": 3, "overhang": 0.5,
         "gable_ov": 0.3, "thick": 0.25, "rotate": False, "auto": True,
         "gables": [],
         "eave": -1, "walls": True, "cover": False, "follow": False}
    p.update(TYPE_DEFAULTS["gable"])
    return p


def gen_normalize(p) -> dict:
    out = gen_default_params()
    if isinstance(p, dict):
        for k in out:
            if k in p:
                out[k] = p[k]
    if out["type"] not in dict(ROOF_TYPES):
        out["type"] = "gable"
    for k, lo, hi in (("pitch", 0.5, 89.0), ("pitch2", 0.5, 89.0),
                      ("ratio", 0.05, 0.98), ("brk", 0.05, 50.0),
                      ("offset", 0.0, 10.0), ("overhang", 0.0, 5.0),
                      ("thick", 0.0, 2.0),
                      ("gable_ov", 0.0, 5.0)):
        try:
            out[k] = min(hi, max(lo, float(out[k])))
        except (TypeError, ValueError):
            out[k] = gen_default_params()[k]
    try:
        out["count"] = max(1, min(30, int(out["count"])))
        out["eave"] = int(out["eave"])
    except (TypeError, ValueError):
        out["count"], out["eave"] = 3, -1
    out["gables"] = sorted({int(g) for g in (out.get("gables") or [])
                            if isinstance(g, (int, float))})
    for k in ("rotate", "auto", "walls", "cover", "follow"):
        out[k] = bool(out[k])
    return out


def gen_load_params() -> dict:
    try:
        from PySide6.QtCore import QSettings
        raw = QSettings().value(GEN_SETTINGS_KEY)
        return gen_normalize(json.loads(raw) if raw else None)
    except Exception:  # noqa: BLE001
        return gen_default_params()


def gen_save_params(p) -> None:
    try:
        from PySide6.QtCore import QSettings
        q = {k: v for k, v in p.items() if k not in ("gables", "eave")}
        QSettings().setValue(GEN_SETTINGS_KEY, json.dumps(q))
    except Exception:  # noqa: BLE001
        pass


def shape_data(group):
    data = (getattr(group, "ext", None) or {}).get(KEY)
    return (data if isinstance(data, dict) and data.get("kind") == SHAPE_KIND
            else None)


def gather_footprint(scene):
    """The footprint from the selection: horizontal faces (their top side
    up) — loose, or the highest ones inside a selected group (a building
    body). → {"outline": [(x, y)…], "z0": z, "holes": n} or None."""
    import manifold3d as mf
    from core.group import Group, world_mesh
    from core.mesh import Face
    cand = []
    for ent in scene.selection:
        if isinstance(ent, Face):
            fs = [ent]
        elif isinstance(ent, Group) and roof_data(ent) is None and \
                shape_data(ent) is None:
            fs = list(world_mesh(ent).faces)
        else:
            continue
        flat = []
        for f in fs:
            pts = [_p3(v) for v in f.vertices]
            n = _newell(pts)
            if n is None or abs(n[2]) < 0.995:
                continue
            flat.append((sum(q[2] for q in pts) / len(pts), pts, f))
        if not flat:
            continue
        if isinstance(ent, Group):
            top = max(z for z, _p, _f in flat)
            flat = [x for x in flat if abs(x[0] - top) < 0.005]
        cand.extend(flat)
    if not cand:
        return None
    z0 = max(z for z, _p, _f in cand)
    cand = [x for x in cand if abs(x[0] - z0) < 0.005]
    parts = []
    holes = 0
    for _z, pts, f in cand:
        loop = [(q[0], q[1]) for q in pts]
        if _area2(loop) < 0:
            loop.reverse()
        parts.append(mf.CrossSection([loop], mf.FillRule.Positive))
        holes += len(f.holes or [])
    cs = parts[0] if len(parts) == 1 else \
        mf.CrossSection.batch_boolean(parts, mf.OpType.Add)
    polys = [[(float(x), float(y)) for x, y in lp] for lp in cs.to_polygons()]
    outer = [lp for lp in polys if _area2(lp) > 0]
    if not outer:
        return None
    best = max(outer, key=_area2)
    holes += len(polys) - 1
    outline = clean_outline(best)
    if len(outline) < 3:
        return None
    return {"outline": outline, "z0": z0, "holes": holes,
            "parts": len(outer)}


def shape_params(p, outline):
    """The generator's parameters from the dialog's."""
    q = dict(p)
    q["gables"] = None if p["auto"] else set(p["gables"])
    q["eave"] = None if p["eave"] < 0 else p["eave"]
    return q


def make_shape(fp, p, name="Roof"):
    from core.group import Group
    from core.mesh import Mesh
    import numpy as np
    t0 = time.time()
    p = gen_normalize(p)
    roof, walls = build_roof(fp["outline"], fp["z0"], p["type"],
                             shape_params(p, fp["outline"]))
    if not roof:
        raise SkelError("No roof faces came out — check the settings.")
    polys = [list(f) for f in roof] + [list(f) for f in walls]
    mesh = Mesh()
    pos = np.asarray([q for f in polys for q in f], dtype=float)
    sizes = np.asarray([len(f) for f in polys], dtype=np.int64)
    mesh.add_faces_bulk(pos, sizes, np.ones(len(sizes), dtype=np.int64))
    soften(mesh, 12.0)                 # a barrel or dome looks round
    g = Group(mesh=mesh, name=name)
    g.ext = {KEY: {"kind": SHAPE_KIND, "version": VERSION,
                   "params": {k: v for k, v in p.items()},
                   "outline": [[round(x, 6), round(y, 6)]
                               for x, y in fp["outline"]],
                   "z0": round(fp["z0"], 6)}}
    top = max(q[2] for f in roof for q in f)
    info = {"faces": len(roof), "walls": len(walls),
            "height": top - fp["z0"], "flipped": ORIENT_LOG["flipped"],
            "seconds": time.time() - t0}
    return g, info


def run_shape(viewport, fp, p, old=None, select=True):
    global _CMD
    if _CMD is None:
        _CMD = _make_command_class()
    name = old.name if old is not None else _next_shape_name(viewport.scene)
    g, info = make_shape(fp, p, name)
    if old is not None:
        g.layer = old.layer
        g.uid = old.uid                  # the tiles made on it stay linked
        g.material = getattr(old, "material", None)
    else:
        lay = getattr(viewport.scene, "current_layer", None)
        if isinstance(lay, str):
            g.layer = lay
    cmd = _CMD(g, old, select, [])
    cmd.info = info
    hist = viewport.history
    hist.execute(cmd)
    err = getattr(hist, "last_error", None)
    if err:
        raise RuntimeError(err)
    notify = getattr(viewport, "notify_scene_changed", None)
    if notify:
        notify()
    viewport.update()
    return cmd


def recover_tiles(viewport, shape):
    """After the roof shape changed: lay again every roof covering that was
    made on it (its own undo step each). → number of coverings."""
    from core.group import Group

    class _Sel:
        selection = {shape}
    data = gather(_Sel())
    if not data["faces"]:
        return 0
    n = 0
    for g in list(viewport.scene.groups):
        rec = roof_data(g) if isinstance(g, Group) else None
        if rec is None or shape.uid not in (rec.get("shapes") or []):
            continue
        p = normalize_params(rec.get("params"))
        p["force"] = True
        run_roof(viewport, data, p, old=g, select=False)
        n += 1
    return n


def _next_shape_name(scene):
    used = {g.name for g in scene.groups}
    if "Roof" not in used:
        return "Roof"
    n = 2
    while f"Roof {n}" in used:
        n += 1
    return f"Roof {n}"


# the footprint's edge numbers, drawn in the viewport while the dialog is
# open (set by the dialog, drawn by the overlay registered in setup)
_GEN_OVERLAY = {"fp": None, "gables": set(), "eave": None}
_APP = None


def _draw_overlay(viewport, painter):
    fp = _GEN_OVERLAY.get("fp")
    if not fp or _APP is None:
        return
    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtGui import QColor, QFont, QPen
    import numpy as np
    pts = fp["outline"]
    n = len(pts)
    z = fp["z0"]
    P = np.asarray([(x, y, z) for x, y in pts] +
                   [((pts[i][0] + pts[(i + 1) % n][0]) / 2,
                     (pts[i][1] + pts[(i + 1) % n][1]) / 2, z)
                    for i in range(n)], dtype=float)
    try:
        px, py, front = _APP.world_to_pixels(P)
    except Exception:  # noqa: BLE001
        return
    gab = _GEN_OVERLAY.get("gables") or set()
    eave = _GEN_OVERLAY.get("eave")
    for i in range(n):
        j = (i + 1) % n
        if not (front[i] and front[j]):
            continue
        col = QColor(243, 115, 41) if i in gab else (
            QColor(46, 158, 79) if i == eave else QColor(60, 120, 220))
        painter.setPen(QPen(col, 3.0 if (i in gab or i == eave) else 1.5))
        painter.drawLine(QPointF(px[i], py[i]), QPointF(px[j], py[j]))
    f = QFont()
    f.setBold(True)
    f.setPointSize(9)
    painter.setFont(f)
    for i in range(n):
        k = n + i
        if not front[k]:
            continue
        col = QColor(243, 115, 41) if i in gab else (
            QColor(46, 158, 79) if i == eave else QColor(60, 120, 220))
        r = QRectF(px[k] - 11, py[k] - 9, 22, 18)
        painter.setPen(Qt.NoPen)
        painter.setBrush(col)
        painter.drawRoundedRect(r, 4, 4)
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(r, Qt.AlignCenter, str(i + 1))


def _make_shape_dialog_class():
    from PySide6.QtCore import QEventLoop, Qt, QTimer
    from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox,
                                   QDialog, QDoubleSpinBox, QFormLayout,
                                   QGroupBox, QHBoxLayout, QLabel,
                                   QListWidget, QListWidgetItem, QMessageBox,
                                   QPushButton, QSpinBox, QVBoxLayout)

    class CreateRoofDialog(QDialog):
        _PV_ON = ("QPushButton { background: #2e9e4f; color: white; "
                  "font-weight: bold; border: 1px solid #1f7a3a; "
                  "border-radius: 3px; padding: 3px 8px; }")
        _BANNER = {
            "live": "background: #1f5f33; color: #e8ffe9;",
            "busy": "background: #7a5a12; color: #fff6e0;",
            "paused": "background: #5c4a1a; color: #ffe9b8;",
            "error": "background: #7a1f1f; color: #ffecec;",
        }

        def __init__(self, viewport, fp, old=None, parent=None):
            super().__init__(parent)
            self.viewport = viewport
            self.fp = fp
            self.old = old
            self.scale_m, self.ulabel = _unit()
            self.p = (gen_normalize(shape_data(old).get("params"))
                      if old is not None else gen_load_params())
            self._preview_cmd = None
            self._block = None
            self._busy = False
            self._computing = False
            self._timer = QTimer(self)
            self._timer.setSingleShot(True)
            self._timer.setInterval(250)
            self._timer.timeout.connect(self._refresh_preview)
            what = "Edit Roof Shape" if old is not None else "Create Roof"
            self.setWindowTitle(f"{TITLE} {VERSION} — {what}")
            self.setModal(False)
            self.setAttribute(Qt.WA_DeleteOnClose, True)
            self._sel_note = ""
            self._sig = self._selection_sig()
            self._sel_timer = QTimer(self)
            self._sel_timer.setInterval(400)
            self._sel_timer.timeout.connect(self._poll_selection)
            self._build_ui()
            self._load_into_ui()
            self._sel_timer.start()

        # ---- UI ------------------------------------------------------------
        def _len(self, lo, hi, tip=""):
            s = QDoubleSpinBox(self)
            sc = self.scale_m
            s.setRange(lo / sc, hi / sc)
            s.setDecimals(3)
            s.setSingleStep(0.05 / sc if sc <= 1.0 else 0.05)
            s.setSuffix(f" {self.ulabel}")
            s.setKeyboardTracking(False)
            s.setToolTip(tip)
            s.valueChanged.connect(self._changed)
            return s

        def _deg(self, tip=""):
            s = QDoubleSpinBox(self)
            s.setRange(0.5, 89.0)
            s.setDecimals(1)
            s.setSuffix(" °")
            s.setKeyboardTracking(False)
            s.setToolTip(tip)
            s.valueChanged.connect(self._changed)
            return s

        def _build_ui(self):
            lay = QVBoxLayout(self)
            src = QGroupBox("Footprint", self)
            sl = QVBoxLayout(src)
            self.src_lbl = QLabel(self)
            self.src_lbl.setWordWrap(True)
            self.src_lbl.setMinimumWidth(420)
            sl.addWidget(self.src_lbl)
            row = QHBoxLayout()
            self.follow = QCheckBox("Follow selection", self)
            self.follow.setToolTip("While the dialog is open, a newly "
                                   "selected footprint is taken by itself.")
            self.follow.toggled.connect(self._follow_toggled)
            row.addWidget(self.follow)
            row.addStretch(1)
            b = QPushButton("↻ Read selection", self)
            b.setToolTip("Take the selected footprint now.")
            b.clicked.connect(lambda: self._read_selection(True))
            row.addWidget(b)
            sl.addLayout(row)
            lay.addWidget(src)

            tb = QGroupBox("Roof", self)
            self.form = QFormLayout(tb)
            self.rtype = QComboBox(self)
            for key, label in ROOF_TYPES:
                self.rtype.addItem(label, key)
            self.rtype.setToolTip(
                "Roof shapes from Europe, the UK, the USA and Asia. Gable, "
                "hip and their kin work on any footprint (L, T, U …: cross "
                "gables, valleys and hips come by themselves); the shapes "
                "marked for rectangles use the footprint's bounding "
                "rectangle.")
            self.rtype.currentIndexChanged.connect(self._type_changed)
            self.form.addRow("Type:", self.rtype)
            self.pitch = self._deg("Roof pitch.")
            self.pitch2 = self._deg("Second pitch (see its label).")
            self.ratio = QDoubleSpinBox(self)
            self.ratio.setRange(5, 98)
            self.ratio.setDecimals(0)
            self.ratio.setSuffix(" %")
            self.ratio.setKeyboardTracking(False)
            self.ratio.setToolTip("Where the change of shape starts, in % "
                                  "of the roof's height.")
            self.ratio.valueChanged.connect(self._changed)
            self.brk = self._len(0.05, 50.0, "Height above the wall top "
                                 "where the pitch changes.")
            self.offset = self._len(0.0, 10.0, "Height step between the two "
                                    "halves (room for clerestory windows).")
            self.count = QSpinBox(self)
            self.count.setRange(1, 30)
            self.count.setKeyboardTracking(False)
            self.count.setToolTip("Number of teeth.")
            self.count.valueChanged.connect(self._changed)
            self.eave = QSpinBox(self)
            self.eave.setRange(0, 999)
            self.eave.setSpecialValueText("Longest edge")
            self.eave.setKeyboardTracking(False)
            self.eave.setToolTip("The low side (eave) of the roof: the edge "
                                 "number shown in the viewport.")
            self.eave.valueChanged.connect(self._changed)
            self.rotate = QCheckBox("Turn the ridge 90°", self)
            self.rotate.setToolTip("Ridge across instead of along the "
                                   "building (or the other gable ends).")
            self.rotate.toggled.connect(self._changed)
            self.lbl = {}
            for key, w, label in (("pitch", self.pitch, "Pitch:"),
                                  ("pitch2", self.pitch2, "Pitch 2:"),
                                  ("ratio", self.ratio, "Starts at:"),
                                  ("brk", self.brk, "Break height:"),
                                  ("offset", self.offset, "Height step:"),
                                  ("count", self.count, "Teeth:"),
                                  ("eave", self.eave, "Eave side:"),
                                  ("rotate", self.rotate, "")):
                lb = QLabel(label, self)
                self.lbl[key] = (lb, w)
                self.form.addRow(lb, w)
            self.overhang = self._len(0.0, 5.0, "Eave overhang, measured "
                                      "horizontally from the wall.")
            self.gable_ov = self._len(0.0, 5.0, "Overhang at the gables "
                                      "(verge).")
            self.form.addRow("Eave overhang:", self.overhang)
            self.form.addRow("Gable overhang:", self.gable_ov)
            lay.addWidget(tb)

            gb = QGroupBox("Gable sides", self)
            self.gbox = gb
            gl = QVBoxLayout(gb)
            self.auto = QCheckBox("Automatic (the ends of the building)", self)
            self.auto.setToolTip("Short end sides become gables. Untick to "
                                 "choose the gable sides yourself — the "
                                 "numbers are shown on the footprint in the "
                                 "viewport.")
            self.auto.toggled.connect(self._auto_toggled)
            gl.addWidget(self.auto)
            self.glist = QListWidget(self)
            self.glist.setMaximumHeight(130)
            self.glist.setMinimumHeight(90)
            self.glist.itemChanged.connect(self._gable_item)
            gl.addWidget(self.glist)
            lay.addWidget(gb)

            ob = QGroupBox("Output", self)
            ol = QVBoxLayout(ob)
            self.walls = QCheckBox("Gable walls (close the gables down to "
                                   "the wall top)", self)
            self.walls.toggled.connect(self._changed)
            trow = QHBoxLayout()
            trow.addWidget(QLabel("Roof thickness:", self))
            self.thick = self._len(0.0, 2.0, "The roof as a slab: underside "
                                   "and fascia, so it looks right from below "
                                   "and at the edges. 0 = only the roof "
                                   "surface.")
            trow.addWidget(self.thick)
            trow.addStretch(1)
            self.cover = QCheckBox("Cover with tiles after OK", self)
            self.cover.setToolTip("Opens Cover Roof… for the new roof.")
            ol.addWidget(self.walls)
            ol.addLayout(trow)
            ol.addWidget(self.cover)
            lay.addWidget(ob)

            self.info_lbl = QLabel(self)
            self.info_lbl.setWordWrap(True)
            lay.addWidget(self.info_lbl)
            self.pv_lbl = QLabel(self)
            self.pv_lbl.setWordWrap(True)
            self.pv_lbl.setVisible(False)
            lay.addWidget(self.pv_lbl)
            row = QHBoxLayout()
            self.preview = QPushButton("Preview", self)
            self.preview.setCheckable(True)
            self.preview.toggled.connect(self._preview_toggled)
            reset = QPushButton("Reset", self)
            reset.setToolTip("Back to the default settings of this roof "
                             "type.")
            reset.clicked.connect(self._reset)
            self.ok_btn = QPushButton("OK", self)
            self.ok_btn.setDefault(True)
            self.ok_btn.clicked.connect(self.accept)
            cancel = QPushButton("Cancel", self)
            cancel.clicked.connect(self.reject)
            row.addWidget(self.preview)
            row.addWidget(reset)
            row.addStretch(1)
            row.addWidget(self.ok_btn)
            row.addWidget(cancel)
            lay.addLayout(row)
            self._style_preview(False)

        def _set_len(self, spin, v):
            spin.setValue(v / self.scale_m)

        def _load_into_ui(self):
            self._busy = True
            p = self.p
            self.rtype.setCurrentIndex(max(0, self.rtype.findData(p["type"])))
            self.pitch.setValue(p["pitch"])
            self.pitch2.setValue(p["pitch2"])
            self.ratio.setValue(round(p["ratio"] * 100))
            self._set_len(self.brk, p["brk"])
            self._set_len(self.offset, p["offset"])
            self.count.setValue(p["count"])
            self.eave.setValue(p["eave"] + 1)
            self.rotate.setChecked(p["rotate"])
            self._set_len(self.overhang, p["overhang"])
            self._set_len(self.gable_ov, p["gable_ov"])
            self._set_len(self.thick, p["thick"])
            self.auto.setChecked(p["auto"])
            self.walls.setChecked(p["walls"])
            self.cover.setChecked(p["cover"])
            self.follow.setChecked(p["follow"])
            self._busy = False
            self._sync()

        def _read_ui(self):
            p, s = self.p, self.scale_m
            p["type"] = self.rtype.currentData()
            p["pitch"] = self.pitch.value()
            p["pitch2"] = self.pitch2.value()
            p["ratio"] = self.ratio.value() / 100.0
            p["brk"] = self.brk.value() * s
            p["offset"] = self.offset.value() * s
            p["count"] = self.count.value()
            p["eave"] = self.eave.value() - 1
            p["rotate"] = self.rotate.isChecked()
            p["overhang"] = self.overhang.value() * s
            p["gable_ov"] = self.gable_ov.value() * s
            p["thick"] = self.thick.value() * s
            p["auto"] = self.auto.isChecked()
            p["walls"] = self.walls.isChecked()
            p["cover"] = self.cover.isChecked()
            p["follow"] = self.follow.isChecked()
            self.p = gen_normalize(p)

        def _type_changed(self, *_a):
            if self._busy:
                return
            key = self.rtype.currentData()
            d = TYPE_DEFAULTS.get(key, {})
            self._busy = True
            self.pitch.setValue(d.get("pitch", 35.0))
            self.pitch2.setValue(d.get("pitch2", d.get("pitch", 35.0)))
            if "ratio" in d:
                self.ratio.setValue(round(d["ratio"] * 100))
            if "brk" in d:
                self._set_len(self.brk, d["brk"])
            if "offset" in d:
                self._set_len(self.offset, d["offset"])
            if "count" in d:
                self.count.setValue(d["count"])
            self._busy = False
            self._changed()

        def _auto_toggled(self, on):
            if self._busy:
                return
            if not on and self.fp:                # start from the automatic
                self.p["gables"] = sorted(auto_gables(
                    self.fp["outline"], self.p["rotate"]))
            self._changed()

        def _gable_item(self, item):
            if self._busy or self.auto.isChecked():
                return
            sel = []
            for i in range(self.glist.count()):
                if self.glist.item(i).checkState() == Qt.Checked:
                    sel.append(i)
            self.p["gables"] = sel
            self._changed()

        def _current_gables(self):
            pts = self.fp["outline"] if self.fp else []
            if not pts:
                return set()
            if self.p["auto"]:
                return auto_gables(pts, self.p["rotate"])
            return {g for g in self.p["gables"] if g < len(pts)}

        def _sync(self):
            p = self.p
            key = p["type"]
            used = TYPE_PARAMS.get(key, ())
            for k, (lb, w) in self.lbl.items():
                vis = k in used
                lb.setVisible(vis)
                w.setVisible(vis)
            self.lbl["pitch"][0].setText(PITCH_LABEL.get(key, "Pitch:"))
            self.lbl["pitch2"][0].setText(PITCH2_LABEL.get(key, "Pitch 2:"))
            self.lbl["ratio"][0].setText(RATIO_LABEL.get(key, "Starts at:"))
            self.lbl["brk"][0].setText(BRK_LABEL.get(key, "Break height:"))
            self.gbox.setVisible("gables" in used)
            fp = self.fp
            s, u = self.scale_m, self.ulabel
            if fp is None:
                self.src_lbl.setText("<b>Select a horizontal face (the "
                                     "footprint) or a building body.</b>")
                self.ok_btn.setEnabled(False)
                self._block = "No footprint."
                _GEN_OVERLAY["fp"] = None
                return
            pts = fp["outline"]
            n = len(pts)
            area = abs(_rg_area(pts))
            txt = (f"{n} corners · {area:,.1f} m² · wall top at "
                   f"{_fmt(fp['z0'], s, u)}")
            if fp.get("holes"):
                txt += ("<br><span style='color:#e8912d'>Courtyards (holes) "
                        "are left out — the roof covers the outline.</span>")
            if fp.get("parts", 1) > 1:
                txt += ("<br><span style='color:#e8912d'>Several separate "
                        "faces — the largest is used.</span>")
            if self._sel_note:
                txt += f"<br><span style='color:#5fbf73'>{self._sel_note}</span>"
            elif self.old is not None:
                txt += "<br>Footprint stored with the roof."
            self.src_lbl.setText(txt)
            # the gable list
            gab = self._current_gables()
            self._busy = True
            if self.glist.count() != n:
                self.glist.clear()
                for i in range(n):
                    it = QListWidgetItem(self.glist)
                    it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            for i in range(n):
                ln = math.dist(pts[i], pts[(i + 1) % n])
                it = self.glist.item(i)
                it.setText(f"Side {i + 1} — {_fmt(ln, s, u)}")
                it.setCheckState(Qt.Checked if i in gab else Qt.Unchecked)
            self.glist.setEnabled(not p["auto"])
            self.eave.setMaximum(n)
            self._busy = False
            if not p["auto"]:
                self.p["gables"] = sorted(gab)
            _GEN_OVERLAY["fp"] = fp
            _GEN_OVERLAY["gables"] = gab if "gables" in used else set()
            _GEN_OVERLAY["eave"] = (
                (p["eave"] if p["eave"] >= 0 else
                 max(range(n), key=lambda i: math.dist(pts[i],
                                                       pts[(i + 1) % n])))
                if "eave" in used else None)
            self.viewport.update()
            self.ok_btn.setEnabled(True)
            self._block = None
            if self.isVisible():
                QTimer.singleShot(0, self.adjustSize)

        def _banner(self, kind, text):
            self.pv_lbl.setStyleSheet(
                self._BANNER[kind] + " padding: 6px 8px; border-radius: 3px;")
            self.pv_lbl.setText(text)
            self.pv_lbl.setVisible(True)

        def _style_preview(self, on):
            if on:
                self.preview.setText("● Live Preview ON")
                self.preview.setStyleSheet(self._PV_ON)
                self.preview.setToolTip("The preview follows every change by "
                                        "itself — click to switch it off.")
            else:
                self.preview.setText("Preview")
                self.preview.setStyleSheet("")
                self.preview.setToolTip("Show the roof in the model; it then "
                                        "updates by itself on every change.")
                self.pv_lbl.setVisible(False)
            if self.isVisible():
                QTimer.singleShot(0, self.adjustSize)

        def _changed(self, *_a):
            if self._busy:
                return
            self._read_ui()
            self._sync()
            if self.preview.isChecked():
                if not self._block:
                    self._banner("busy", "⟳ Updating the preview…")
                self._timer.start()

        def _reset(self):
            key = self.p["type"]
            self.p = gen_default_params()
            self.p["type"] = key
            self.p.update(TYPE_DEFAULTS.get(key, {}))
            self.p["pitch2"] = TYPE_DEFAULTS.get(key, {}).get(
                "pitch2", self.p["pitch"])
            self._load_into_ui()
            self._changed()

        # ---- selection -----------------------------------------------------
        def _selection_sig(self):
            try:
                return frozenset(id(e) for e in self.viewport.scene.selection)
            except Exception:  # noqa: BLE001
                return frozenset()

        def _poll_selection(self):
            if self._computing or not self.follow.isChecked():
                return
            sig = self._selection_sig()
            if sig != self._sig:
                self._sig = sig
                self._read_selection(False)

        def _follow_toggled(self, on):
            if self._busy:
                return
            self.p["follow"] = bool(on)
            if on:
                self._sig = self._selection_sig()
                self._read_selection(False)

        def _read_selection(self, manual):
            if self._computing:
                return
            fp = gather_footprint(self.viewport.scene)
            if fp is None:
                if manual:
                    self.viewport.flash_status(
                        f"{TITLE}: no horizontal face in the selection — the "
                        f"footprint stays as it is.", 4000)
                return
            if self.fp is not None and fp["outline"] == self.fp["outline"] \
                    and abs(fp["z0"] - self.fp["z0"]) < 1e-9:
                return
            self.fp = fp
            self._sel_note = (f"↻ Footprint read again "
                              f"({time.strftime('%H:%M:%S')}): "
                              f"{len(fp['outline'])} corners")
            self._sync()
            if self.preview.isChecked():
                self._banner("busy", "⟳ Updating the preview…")
                self._timer.start()

        # ---- building ------------------------------------------------------
        def _run(self, select=True):
            self._computing = True
            try:
                return run_shape(self.viewport, self.fp, self.p, self.old,
                                 select)
            finally:
                self._computing = False

        def _result_text(self, info):
            s, u = self.scale_m, self.ulabel
            return (f"{info['faces']} roof faces, {info['walls']} walls · "
                    f"ridge {_fmt(info['height'], s, u)} above the wall top"
                    + (f" · {info['flipped']} faces turned outward"
                       if info.get("flipped") else " · faces checked"))

        def _undo_preview(self):
            cmd = self._preview_cmd
            self._preview_cmd = None
            if cmd is None:
                return
            stack = getattr(self.viewport.history, "undo_stack", [])
            if stack and stack[-1] is cmd:
                self.viewport.history.undo()
                self.viewport.update()

        def _refresh_preview(self):
            if self._computing:
                self._timer.start()
                return
            self._undo_preview()
            if not self.preview.isChecked():
                return
            if self._block:
                self._banner("paused", f"⏸ <b>Preview paused</b> — "
                             f"{self._block}")
                return
            QApplication.processEvents(QEventLoop.ExcludeUserInputEvents)
            try:
                self._preview_cmd = self._run(select=False)
                self._preview_cmd.key = self._state_key()
                self._banner("live", "● <b>LIVE PREVIEW</b> — "
                             + self._result_text(self._preview_cmd.info)
                             + " · changes apply instantly")
            except Exception as exc:  # noqa: BLE001
                self._preview_cmd = None
                self._banner("error", f"Preview failed: {exc}")

        def _preview_toggled(self, on):
            self._style_preview(on)
            if on:
                self._refresh_preview()
            else:
                self._timer.stop()
                self._undo_preview()

        def _state_key(self):
            p = {k: v for k, v in self.p.items() if k not in ("follow",
                                                              "cover")}
            return (json.dumps(self.fp["outline"]), self.fp["z0"],
                    json.dumps(p, sort_keys=True))

        def _keep_preview(self):
            cmd = self._preview_cmd
            if cmd is None or getattr(cmd, "key", None) != self._state_key():
                return None
            stack = getattr(self.viewport.history, "undo_stack", [])
            if not stack or stack[-1] is not cmd:
                return None
            scene = self.viewport.scene
            cmd.select = True
            scene.selection.clear()
            scene.selection.add(cmd.new)
            scene.version += 1
            self._preview_cmd = None
            notify = getattr(self.viewport, "notify_scene_changed", None)
            if notify:
                notify()
            self.viewport.update()
            return cmd

        def _close_overlay(self):
            _GEN_OVERLAY["fp"] = None
            self.viewport.update()

        def accept(self):
            if self._computing or self.fp is None:
                return
            self._sel_timer.stop()
            self._read_ui()
            self._timer.stop()
            gen_save_params(self.p)
            cmd = self._keep_preview()
            if cmd is None:
                self._undo_preview()
                try:
                    cmd = self._run()
                except Exception as exc:  # noqa: BLE001
                    QMessageBox.warning(self, TITLE, str(exc))
                    self._sel_timer.start()
                    return
            self._close_overlay()
            msg = (f"{TITLE}: «{cmd.new.name}» — "
                   f"{self._result_text(cmd.info)} (one undo step)")
            if self.old is not None:
                try:
                    n = recover_tiles(self.viewport, cmd.new)
                except Exception as exc:  # noqa: BLE001
                    n = 0
                    msg += f" — the tiles could not follow: {exc}"
                if n:
                    msg += (f" — {n} roof covering{'s' if n > 1 else ''} "
                            f"laid again on the new shape (own undo step)")
            self.viewport.flash_status(msg, 8000)
            cover = self.p["cover"]
            vp, par = self.viewport, self.parent()
            super().accept()
            if cover:
                QTimer.singleShot(0, lambda: show_cover(vp, par))

        def reject(self):
            if self._computing:
                return
            self._sel_timer.stop()
            self._timer.stop()
            self._undo_preview()
            self._read_ui()
            gen_save_params(self.p)
            self._close_overlay()
            super().reject()

    return CreateRoofDialog


_SHAPE_DIALOG = None
_SHAPE_OPEN = None


def _shape_dialog(viewport, fp, old, parent):
    global _SHAPE_DIALOG, _SHAPE_OPEN
    if _SHAPE_DIALOG is None:
        _SHAPE_DIALOG = _make_shape_dialog_class()
    if _SHAPE_OPEN is not None:
        try:
            _SHAPE_OPEN.reject()
        except RuntimeError:
            pass
    dlg = _SHAPE_DIALOG(viewport, fp, old, parent or viewport.window())
    _SHAPE_OPEN = dlg
    dlg.show()
    dlg.raise_()
    return dlg


def selected_shape(scene):
    from core.group import Group
    for ent in scene.selection:
        if isinstance(ent, Group) and shape_data(ent) is not None:
            return ent
    return None


def show_create(viewport, parent=None):
    fp = gather_footprint(viewport.scene)
    if fp is None:
        viewport.flash_status(
            f"{TITLE}: select the footprint first — a horizontal face (the "
            f"top of the walls) or a building body.", 6000)
        return None
    return _shape_dialog(viewport, fp, None, parent)


def show_edit_shape(viewport, parent=None):
    g = selected_shape(viewport.scene)
    if g is None:
        viewport.flash_status(
            f"{TITLE}: select a roof made with Create Roof… first.", 5000)
        return None
    rec = shape_data(g)
    fp = {"outline": [tuple(q) for q in rec.get("outline", [])],
          "z0": float(rec.get("z0", 0.0)), "holes": 0}
    return _shape_dialog(viewport, fp, g, parent)


# ---------------------------------------------------------------------------
# Toolbar (PESI3D): icons drawn in IngeTrazo's own icon style
# ---------------------------------------------------------------------------

def _pesi3d_icons():
    """Icon key → draw(painter, ink, accent) on a 48 px canvas."""
    import math  # noqa: F401
    from PySide6.QtCore import QPointF, QRectF, Qt  # noqa: F401
    from PySide6.QtGui import (QBrush, QColor, QPainterPath, QPen,  # noqa: F401
                               QPolygonF)

    def _a(c, alpha):
        return QColor(c.red(), c.green(), c.blue(), alpha)

    def _dot(p, acc, x, y, r=3.2, color=None):
        p.save()
        p.setPen(Qt.NoPen)
        p.setBrush(color or acc)
        p.drawEllipse(QPointF(x, y), r, r)
        p.restore()

    def _poly(pts):
        return QPolygonF([QPointF(x, y) for x, y in pts])

    def _pencil(p, ink, acc):
        """Small pencil in the lower right corner = «Edit …»."""
        p.save()
        p.translate(35.5, 34.5)
        p.rotate(45)
        pen = QPen(ink, 2.2)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
        p.setBrush(acc)
        p.drawRect(QRectF(-3.6, -11.0, 7.2, 13.0))
        p.setBrush(QBrush(ink))
        p.drawPolygon(_poly([(-3.6, 2.0), (3.6, 2.0), (0.0, 8.0)]))
        p.restore()

    def _roof(p, ink, acc):
        # A roof plane seen at an angle: tile courses (scalloped tails),
        # ridge tiles along the top, verge on the left.
        e0, e1, r1, r0 = (5.0, 39.0), (35.0, 39.0), (43.0, 11.0), (13.0, 11.0)
        p.save()
        p.setPen(Qt.NoPen)
        p.setBrush(_a(acc, 70))
        p.drawPolygon(_poly([e0, e1, r1, r0]))
        p.restore()
        p.save()
        pen = QPen(acc, 2.4)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        for y in (20.0, 29.0, 38.0):           # course tails
            t = (39.0 - y) / 28.0
            x0 = e0[0] + (r0[0] - e0[0]) * t + 1.0
            x1 = e1[0] + (r1[0] - e1[0]) * t - 1.0
            n = 3
            w = (x1 - x0) / n
            for i in range(n):
                p.drawArc(QRectF(x0 + i * w, y - 4.0, w, 7.0),
                          180 * 16, 180 * 16)
        p.restore()
        p.setBrush(Qt.NoBrush)
        p.drawPolygon(_poly([e0, e1, r1, r0]))
        thick = QPen(ink, 5.5)
        thick.setCapStyle(Qt.RoundCap)
        p.save()
        p.setPen(thick)
        p.drawLine(QPointF(*r0), QPointF(*r1))   # ridge tiles
        p.restore()
        _dot(p, acc, 13.0, 11.0, 3.4)
        _dot(p, acc, 43.0, 11.0, 3.4)

    def roof_cover(p, ink, acc):
        _roof(p, ink, acc)

    def roof_edit(p, ink, acc):
        p.save()
        p.translate(-2, -3)
        _roof(p, ink, acc)
        p.restore()
        _pencil(p, ink, acc)

    def _house(p, ink, acc):
        # a house: walls and a gable roof over them (the roof in accent)
        p.save()
        p.setPen(Qt.NoPen)
        p.setBrush(_a(acc, 200))
        p.drawPolygon(_poly([(5, 24), (24, 8), (43, 24)]))
        p.restore()
        p.setBrush(Qt.NoBrush)
        p.drawPolygon(_poly([(5, 24), (24, 8), (43, 24)]))
        p.drawPolyline(_poly([(10, 24), (10, 41), (38, 41), (38, 24)]))
        p.drawLine(QPointF(20, 41), QPointF(20, 32))
        p.drawLine(QPointF(20, 32), QPointF(27, 32))
        p.drawLine(QPointF(27, 32), QPointF(27, 41))

    def roof_create(p, ink, acc):
        _house(p, ink, acc)

    def roof_shape_edit(p, ink, acc):
        p.save()
        p.translate(-2, -3)
        _house(p, ink, acc)
        p.restore()
        _pencil(p, ink, acc)

    return {"cover": roof_cover, "edit": roof_edit, "create": roof_create,
            "shape_edit": roof_shape_edit}


def _pesi3d_toolbar(app, title, entries):
    """A toolbar of this plugin's own — one icon per command (PESI3D).

    ``entries`` = (icon key, text, tip, callable). The icons are drawn
    like IngeTrazo's own (views/icons.py: 48 px, ink = the palette's text
    colour, 3 px pen, the orange accent) and redrawn when the theme flips.
    The toolbar moves, floats and hides like the built-in ones (right-click
    on any toolbar); its place is kept by its objectName."""
    try:
        from PySide6.QtCore import QEvent, QObject, QSize, Qt
        from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPen, QPixmap
        from PySide6.QtWidgets import QApplication, QToolBar
    except Exception:  # noqa: BLE001 — no Qt, no toolbar
        return None
    win = getattr(app, "window", None)
    if win is None:
        return None
    draws = _pesi3d_icons()

    def make_icon(key):
        draw = draws.get(key)
        if draw is None:
            return QIcon()
        qa = QApplication.instance()
        ink = (QColor(qa.palette().windowText().color()) if qa is not None
               else QColor(40, 44, 52))
        pm = QPixmap(48, 48)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing, True)
        pen = QPen(ink, 3.0)
        pen.setJoinStyle(Qt.RoundJoin)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        try:
            draw(p, ink, QColor(243, 115, 41))
        finally:
            p.end()
        return QIcon(pm)

    name = f"pesi3d_{getattr(app, 'key', title)}"
    tb = None
    make = getattr(win, "_new_toolbar", None)     # the host's own builder
    if callable(make):
        try:
            tb = make(title, name)
        except Exception:  # noqa: BLE001
            tb = None
    if tb is None:
        tb = QToolBar(title, win)
        tb.setObjectName(name)
        tb.setMovable(True)
        tb.setFloatable(True)
        try:
            from views.icons import toolbar_icon_px
            px = int(toolbar_icon_px())
        except Exception:  # noqa: BLE001
            px = 24
        tb.setIconSize(QSize(px, px))
        tb.setToolButtonStyle(Qt.ToolButtonIconOnly)
        win.addToolBar(Qt.TopToolBarArea, tb)

    actions = []
    for key, text, tip, fn in entries:
        act = QAction(make_icon(key), text, tb)
        act.setToolTip(f"{text}\n{tip}" if tip else text)
        if tip:
            act.setStatusTip(tip)
        act.triggered.connect(lambda _c=False, f=fn: f())
        tb.addAction(act)
        actions.append((act, key))

    class _ThemeWatch(QObject):
        def eventFilter(self, obj, event):  # noqa: N802 — Qt override
            if event.type() in (QEvent.PaletteChange,
                                QEvent.ApplicationPaletteChange,
                                QEvent.StyleChange):
                for a, k in actions:
                    a.setIcon(make_icon(k))
            return False

    watch = _ThemeWatch(tb)
    tb.installEventFilter(watch)
    tb._pesi3d_watch = watch
    _pesi3d_place_later(win)
    return tb


def _pesi3d_place_later(win):
    """A toolbar the saved window layout does not know yet lands at the end
    of the top row, squeezed behind the built-in ones. Once the window is
    laid out, put new PESI3D toolbars on a row of their own under the
    built-in ones — only the first time each one appears; after that the
    user's own arrangement (saved with the window) wins. Every PESI3D
    plugin carries this code; the first one to get here does it for all."""
    if getattr(win, "_pesi3d_place_pending", False):
        return
    win._pesi3d_place_pending = True
    from PySide6.QtCore import QSettings, Qt, QTimer
    from PySide6.QtWidgets import QToolBar

    def place():
        win._pesi3d_place_pending = False
        try:
            st = QSettings()
            key = "plugins/pesi3d/placed_toolbars"
            placed = st.value(key) or []
            if isinstance(placed, str):
                placed = [placed]
            placed = list(placed)
            bars = [t for t in win.findChildren(QToolBar)
                    if t.objectName().startswith("pesi3d_")]
            new = [t for t in bars if t.objectName() not in placed]
            if not new:
                return
            fresh = not placed            # no PESI3D row yet → open one
            for i, t in enumerate(sorted(new, key=lambda t: t.objectName())):
                shown = not t.isHidden()
                win.removeToolBar(t)
                if fresh and i == 0:
                    win.addToolBarBreak(Qt.TopToolBarArea)
                win.addToolBar(Qt.TopToolBarArea, t)
                t.setVisible(shown)
            st.setValue(key, placed + [t.objectName() for t in new])
        except Exception:  # noqa: BLE001 — layout only, never break the app
            pass

    QTimer.singleShot(0, place)


def setup(app) -> None:
    global _APP
    from PySide6.QtCore import QTimer
    _APP = app
    sub = app.add_menu(TITLE)
    sub.addAction("Create Roof…", lambda: show_create(app.viewport, app.window))
    sub.addAction("Edit Roof Shape…",
                  lambda: show_edit_shape(app.viewport, app.window))
    sub.addSeparator()
    sub.addAction("Cover Roof…", lambda: show_cover(app.viewport, app.window))
    sub.addAction("Edit Roof Tiles…",
                  lambda: show_edit(app.viewport, app.window))

    def later(fn):
        return lambda _c=False: QTimer.singleShot(
            0, lambda: fn(app.viewport, app.window))

    def context(menu, selection) -> None:
        scene = app.viewport.scene
        if not scene.selection:
            return
        menu.addSeparator()
        if selected_roof(scene) is not None:
            menu.addAction("Edit Roof Tiles…").triggered.connect(
                later(show_edit))
            return
        sm = menu.addMenu(TITLE)
        if selected_shape(scene) is not None:
            sm.addAction("Edit Roof Shape…").triggered.connect(
                later(show_edit_shape))
        else:
            sm.addAction("Create Roof…").triggered.connect(later(show_create))
        sm.addAction("Cover Roof…").triggered.connect(later(show_cover))

    app.add_context_menu(context)
    try:
        app.add_overlay(_draw_overlay)
    except Exception:  # noqa: BLE001 — the edge numbers are a help only
        pass

    _pesi3d_toolbar(app, TITLE, [
        ("create", "Create Roof…",
         "Build a roof (gable, hip, mansard, …) on the selected footprint.",
         lambda: show_create(app.viewport, app.window)),
        ("shape_edit", "Edit Roof Shape…",
         "Change the shape and settings of the selected roof.",
         lambda: show_edit_shape(app.viewport, app.window)),
        ("cover", "Cover Roof…",
         "Cover the selected roof faces with roof tiles.",
         lambda: show_cover(app.viewport, app.window)),
        ("edit", "Edit Roof Tiles…",
         "Change the tiles and settings of the selected roof covering.",
         lambda: show_edit(app.viewport, app.window)),
    ])
