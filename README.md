# Roof Tiles — build roofs and cover them with real 3D tiles in IngeTrazo

![Roof Tiles](screenshot.webp)

Two tools in one plugin:

1. **Create Roof…** builds a roof on a footprint: 20 roof shapes from Germany, Europe, the UK, the USA and Asia.
2. **Cover Roof…** covers any roof faces with real 3D roof tiles, with verge tiles, ridge tiles, hip and ridge end pieces.

## Install
Download `roof_tile_tool.py` from the [latest release](../../releases/latest), copy it into the plugins folder (Extensions ▸ Open plugins folder; on Windows `%APPDATA%\ingetrazo\plugins`) and restart IngeTrazo. Needs IngeTrazo ≥ 0.5.7.

You find it under **Extensions ▸ Roof Tiles**, in the right-click menu and in the «Roof Tiles» toolbar (4 icons).

## Create Roof…
Select a horizontal face (the top of the walls) or a building body (group) ▸ **Create Roof…**. The sides of the footprint are numbered in the viewport.

![Roof shapes](images/dachformen.png)

- Shapes: gable, hip, half-hip / jerkinhead, Dutch gable / gablet / irimoya, pyramid, mono-pitch / shed, split-level shed, saltbox / catslide, mansard, gambrel / barn, bonnet / bell-cast, butterfly, M-roof, sawtooth, barrel, spire / cone, dome, Rhenish helm, A-frame, flat with fall.
- Gable, hip and their kin work on **any footprint** (L, T, U, skewed …): hips, valleys and cross gables come by themselves (weighted straight skeleton). The other shapes are cut to the footprint.
- **Gable sides**: automatic or chosen in a list; **Turn the ridge 90°**.
- Per shape: **Pitch**, **Pitch 2**, **Starts at**, **Break height**, **Height step**, **Teeth**, **Eave side**, **Eave overhang**, **Gable overhang**, **Gable walls**, **Roof thickness** (a closed roof slab with fascia).
- Every face is checked after building and turned outward where needed.
- **Cover with tiles after OK** opens Cover Roof… right away. **Edit Roof Shape…** changes the roof later; a covering on it is laid again by itself.

## Cover Roof…
Select the roof faces (or the roof group) ▸ **Cover Roof…**. Eaves, ridges, hips, valleys, verges, mono-pitch ridges, mansard breaks and holes are read by themselves. Any pitch can be covered.

![Tiles](images/ziegeltypen.png)

- 10 tiles: Frankfurt pan, Harz pan, Toscana, flat interlocking tile, Marseille tile, plain tile «Biberschwanz», monk and nun, English pantile, English plain tile, Spanish tile — or a tile of your own (.igz / .obj / selection). Typical dimensions, not any maker's data.
- Batten gauge and cover width are fitted, also to inner verges (the step of an L).
- **Verge**: one-piece verge tiles — or the tiles cut flush and closed with a **mortar bead**, a **verge board** or a **verge flashing**.
- Half-round ridge tiles; **Ridge ends** at the ridge and the foot of every hip: End stone (domed), End disc, Ornamental disc (fan).
- **Mono-pitch ridge tiles**: the tile's profile turned down over the top edge.
- **Valley flashing** and a flashing frame round roof windows and chimneys (**Hole flashing**).
- Whole tiles are instances, edge tiles are real cuts (manifold3d). One undo step, Live Preview, **Edit Roof Tiles…**.

| | |
|---|---|
| ![Verge tile](images/ortgangziegel_einteilig.png) | ![Ridge ends](images/firstenden_varianten.png) |
| ![Mono-pitch ridge tiles](images/pultfirstziegel.png) | ![Verge finish](images/ortgang_abschluss.png) |

## Note
Product names only describe the tile shape; this plugin is not affiliated with any tile maker.

License GPL-3.0-or-later · Pesi, [pesi3d.de](https://pesi3d.de) — German: [LIESMICH.md](LIESMICH.md)
