# Breaking configuration change - 23 August 2026

## Does this apply to you?

**Only if you already had a working PiClock3 configuration from before
23 August 2026.**  If you are setting PiClock3 up for the first time, or you
started from the shipped `Config-Example.yaml` on or after that date, there is
nothing here for you - stop reading and use the README.

If you do have an older config, it will not load.  PiClock3 says so and points
here rather than failing obscurely.

## What happened

On 23 August 2026 pages stopped carrying their own block tree and started
naming a layout and a theme instead.  Nothing was deprecated first, because
the maps and radar half of PiClock3 was only published days earlier and there
was no released version to stay compatible with.  Breaking it then was cheaper
than carrying two config formats forever.

## What changed, and why

`ClockPage.yaml` was 193 lines that mixed four unrelated things: where a block
sat, what it looked like, how deeply it nested, and which plugin drew in it.
You could not move anything without re-deciding its styling, and the nine
forecast boxes were written out nine times with hand-computed offsets.

That is now three files with one job each:

| file | owns |
|---|---|
| `layouts/<name>.yaml` | named regions and their geometry |
| `themes/<name>.yaml` | colors, fonts, background, frames |
| `Config.yaml` | which layout and theme each page uses, and the plugins |

## Your Config.yaml

Pages used to include a tree of blocks:

```yaml
pages:
  clock-page: !include ClockPage.yaml
  clock-page--:
    order: 0
  maps-page: !include MapsPage.yaml
  maps-page--:
    order: 1

styles:
  default:
    font-size: 12px
    color: '#bef'
```

They now name a layout and a theme, and `styles:` moves into the theme:

```yaml
pages:
  clock-page: {order: 0, layout: classic, theme: kevin}
  maps-page:  {order: 1, layout: bigmaps, theme: chris}
```

`ClockPage.yaml` and `MapsPage.yaml` are gone.  Their content ships as
`PiClock3/layouts/classic.yaml`, `PiClock3/layouts/bigmaps.yaml` and
`PiClock3/themes/{kevin,chris,jean,kelly}.yaml`.

## Block names

Every plugin's `block:` needs updating.  The shipped plugin manifests are
already done; this matters for anything you set yourself in `Config.yaml`.

| old block | new region |
|---|---|
| `clock-face` | `clock` |
| `top-line` | `date` |
| `bottom-line` | `bottom` |
| `current` | `current` |
| `clock-radar1` | `maps.1` |
| `clock-radar2` | `maps.2` |
| `maps-radar1` | `radars.1` |
| `maps-radar2` | `radars.2` |
| `maps-bottom-line` | `caption` |

The `.1` / `.2` suffixes are cells of a repeating region.  The nine forecast
boxes are `forecast.1` through `forecast.9`, and in the layout that is one
line rather than ninety-nine:

```yaml
forecast: {right: 0.0, top: 0.0, width: 0.2, height: 1.0,
           border: true, repeat: {count: 9, direction: down}}
```

Change `count:` to get a tenth box.  The theme's `first` and `last` frame
variants are applied automatically, so the stack still reads as one column.

## Where your own files go

`layouts/` and `themes/` beside `Config.yaml` are yours; the ones we ship live
in `PiClock3/layouts/` and `PiClock3/themes/`.  Yours are looked at first, so
dropping in `themes/kevin.yaml` overrides the shipped one without touching it.

Both are single `.yaml` files named after the layout or theme - a folder is
not searched, so something cloned from a git repository has to be unpacked
rather than left as a checkout.

## Writing a theme

```yaml
name: Kevin
background: '{folders.image}/clockbackground-kevin.png'

default:                     # cascades to everything on the page
  font-size: 0.02            # a fraction of the screen height
  color: '#bef'

borders:
  default:
    art: '{folders.image}/frame-amber.png'
    width: 0.012             # frame weight, a fraction of screen height
    inset: 0.5               # where content lands, a fraction of width
  radar:
    art: '{folders.image}/frame-amber.png'
    width: 0.012
    inset: 0.5

styles:                      # named, raw Qt stylesheet properties
  date:
    font-size: 0.75          # a bare number is a fraction of region height
    qproperty-alignment: AlignCenter
```

A layout asks for a frame with `border: true` for the default one, or
`border: radar` for a named one.  An unknown name falls back to `default`, so
any theme still works with any layout.

## A note on frames

A frame is one PNG holding a 3x3 grid: four corners, four edges and a
transparent middle.  The corners stay corners and the edges stretch, so one
file frames a box of any shape.

`bb1.png` and `bb2.png` turned out to be the same drawing at two canvas sizes,
and both are replaced by `frame-amber.png`.  The frames now ship as a color
family - `frame-amber.png`, `frame-blue.png`, `frame-green.png` - which
restores something the old single-theme config had lost: PiClock v1 gave Jean
a blue frame and everyone else an amber one, so `themes/jean.yaml` asks for
`frame-blue.png` and the rest ask for `frame-amber.png`.  Green is the color
v1 used for its bedside and night configs; no shipped theme uses it yet.

A fourth frame, `frame-hairline.png`, is not part of that family: it is a
solid hard-edged line rather than a glow, and `themes/hairline.yaml` pairs it
with the chris background.  It is the one shipped example of a drop-off edge,
so it sets `inset: 1.0` where the others set `0.5`.

The superseded artwork has been deleted - the unused `ba*`, `bb*`, `border*`
and `squares*` PNGs, and two unused wallpapers.  The `.xcf` files stay: those
are the GIMP masters, not output.

Three things are worth knowing if you write a theme.

**The slice is not a setting.**  It is a third of the sheet each way, worked
out from the image.  The art describes its own geometry and a theme cannot
disagree with it.  The old `slice`, `first` and `last` keys are gone.

**`width` is a fraction of screen height, not of the box.**  Every framed box
on a page gets the same weight, whether it is a large map or a small forecast
cell.  Before this, the frame was stretched over each box, so an identical
theme drew a 1px line on a forecast cell and an 11px one on a big radar.

**`inset` says where content lands, and the artwork cannot.**  A frame with a
hard inner edge tells you where content goes - right against the drop.  A
frame that fades, like this one, has no such boundary: its alpha just tails
off.  So the theme names the landing, as a fraction of `width`.  `1.0` keeps
the whole frame clear of the content; `0.5` brings content up to the middle
of the line so the inner half of the glow falls across it.  The frame is
drawn over the content, so the glow lies on top the way a light would.

There is a fuller guide for whoever draws the art in
`PiClock3/images/FRAME-ART.md`.

## Repeats are framed as a group

A repeated region is framed **once**, around the whole group, and the cells
are separated by straight rules:

```yaml
maps: {left: 0.0, top: 0.3333, width: 0.2, height: 0.6667,
       border: radar, repeat: {count: 2, direction: down}}
```

That is two maps inside one frame with a rule between them - not two framed
boxes stacked up.  Framing each cell separately draws two lines at every
join, and puts corner art where the line should run straight through; corner
art fades out, because a corner is where a line ends, so it leaves a notch.

Nothing about a layout or a theme is measured in screen pixels, so the same
files work at 800x600, at 1920x1080 and at 3840x2160.

## What did not change

Plugins, `ApiKeys.yaml`, `location`, `language`, `folders`, and every plugin
option.  Only pages, block names and styling moved.
