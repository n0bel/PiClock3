# Breaking configuration change - August 23, 2026

## Does this apply to you?

**Only if you already had a working PiClock3 configuration from before
August 23, 2026.**  If you are setting PiClock3 up for the first time, or you
started from the shipped `Config-Example.yaml` on or after that date, there is
nothing here for you - use the README.

## Start over.  Do not convert.

Copy `Config-Example.yaml` over your `Config.yaml` and set it up again.

Do not try to migrate the old file.  Pages no longer carry a tree of blocks,
the regions have different names, layouts and themes did not exist as files,
and the frame settings have no equivalent in the old format.  There is no
mapping that produces a working config, and a half-converted one fails in ways
that are tedious to read.

It is a smaller job than it sounds, because nearly everything you actually
chose is a value rather than a structure.

## What to carry across by hand

| from your old config | |
|---|---|
| `location:` | your latitude and longitude |
| `METAR:` | your station |
| which providers you used | mapbox or googlemaps, rainviewer or librewxr |
| radar `zoom:` and `markers:` | if you tuned them |

`ApiKeys.yaml` is untouched.  Keep the file exactly as it is.

Everything else - pages, blocks, styles, border images, folder settings - is
replaced rather than moved.

## Then change one thing at a time

`Config-Example.yaml` ships two pages, two layouts and five themes that
already work together.  Get that running unmodified first, then edit.

To pick a different look, change a page's `theme:`:

```yaml
pages:
  clock-page: {order: 0, layout: classic, theme: circuit}
  maps-page:  {order: 1, layout: bigmaps, theme: stag}
```

The shipped themes are `circuit`, `stag`, `meadow`, `archer`, `london`
and `hairline`.

For writing your own theme, or drawing frame art, see
`PiClock3/themes/FRAME-ART.md`.
