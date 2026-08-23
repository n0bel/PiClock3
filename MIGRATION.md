# Migrating to layouts and themes

**This is a breaking change.**  Configs written before August 2026 will not
load.  PiClock3 says so and points here rather than failing obscurely.

Nothing was deprecated first, because the maps and radar half of PiClock3 was
only published days before this and there was no released version to be
compatible with.  Breaking it now was cheaper than carrying two config formats
forever.

## What changed, and why

`ClockPage.yaml` was 193 lines that mixed four unrelated things: where a block
sat, what it looked like, how deeply it nested, and which plugin drew in it.
You could not move anything without re-deciding its styling, and the nine
forecast boxes were written out nine times with hand-computed offsets.

That is now three files with one job each:

| file | owns |
|---|---|
| `layouts/<name>.yaml` | named regions and their geometry |
| `themes/<name>.yaml` | colours, fonts, background, frames |
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

`layouts/` and `themes/` in the PiClock3 directory are yours; the ones we ship
live in `PiClock3/layouts/` and `PiClock3/themes/`.  Yours are looked at first,
so dropping in `themes/kevin.yaml` overrides the shipped one without touching
it.

## Writing a theme

```yaml
name: Kevin
background: '{folders.image}/clockbackground-kevin.png'

default:                     # cascades to everything on the page
  font-size: 12px
  color: '#bef'

borders:
  default:
    image: '{folders.image}/bb2.png'
    slice: [10, 5, 10, 5]    # top right bottom left
    first: [5, 5, 10, 5]     # first cell of a repeat
    last:  [10, 5, 5, 5]     # last cell
  radar:
    image: '{folders.image}/bb1.png'
    slice: [10, 5, 10, 5]

styles:                      # named, raw Qt stylesheet properties
  date:
    font-size: 0.75          # a bare number is a fraction of region height
    qproperty-alignment: AlignCenter
```

A layout asks for a frame with `border: true` for the default one, or
`border: radar` for a named one.  An unknown name falls back to `default`, so
any theme still works with any layout.

## A note on frames

The shipped frame images are pictures of a frame, stretched across the region -
not true 9-slice art.  So the frame is drawn **over** the content, in an
overlay, and the content sits in an inner widget inset by the slice values.
That is what the old config was doing by hand with three nested blocks per
bordered radar; it is now done once in the loader.

If you make a genuine 9-slice frame with transparent middle, it will work the
same way.

## What did not change

Plugins, `ApiKeys.yaml`, `location`, `language`, `folders`, and every plugin
option.  Only pages, block names and styling moved.
