# Marker art

A marker is **one PNG with transparency**, drawn on a radar at a place you
name.  `MapLoop` scales it to a height, tints it if you asked for a color,
and puts it down so that **the middle of the picture lands on the location**.

That last sentence is the whole of it.  Everything else here follows from
where your art has to sit inside its own canvas for its middle to be the
thing you meant.

Six ship, in the plugin that draws them:

    PiClock3/MapLoop/markers/teardrop.png
    PiClock3/MapLoop/markers/teardrop-dot.png
    PiClock3/MapLoop/markers/teardrop-home.png
    PiClock3/MapLoop/markers/teardrop-work.png
    PiClock3/MapLoop/markers/teardrop-school.png
    PiClock3/MapLoop/markers/teardrop-family.png

They are one drawing with a different symbol punched into each - identical
to the pixel otherwise - and `markers.xcf` beside them is the GIMP file they
came from.  Which marker a radar draws, and where, is a config's to say:
see [WRITING-A-CONFIG.md](WRITING-A-CONFIG.md).

## The middle is the anchor

There is no "point at the bottom" rule, no hotspot to declare.  The center
pixel of your image is put on the coordinate, and that is all `MapLoop`
knows.  So the art has to be drawn with the thing you want on the spot
already in the middle of the canvas.

Two shapes come out of that, and they use their canvas very differently.

**Tip-anchored** - a teardrop, a pin, an arrow.  What lands on the spot is
the point at the bottom, so the ink has to sit **entirely in the top half**
and the bottom half is empty padding whose only job is to push the tip down
to the center.  Such a marker can never use more than half its canvas.  The
six that ship are exactly this: 64x64 with every inked pixel in rows 0-31.

**Centered** - a dot, a ring, a crosshair, a circle drawn round a town.
What lands on the spot is the middle of the symbol, so it can fill the whole
canvas.

    tip-anchored, 64x64            centered, 64x64
    +---------------+              +---------------+
    |               |              |               |
    |     ( o )     |              |               |
    |      \ /      |              |      -+-      |  <- the anchor
    |       v       |              |               |
    +-------X-------+  <- the      |               |
    |               |     anchor   |               |
    |    (empty)    |              |               |
    |               |              |               |
    +---------------+              +---------------+

Draw a pin that fills its canvas and it will straddle the spot rather than
point at it, by half its own height.  Nothing will warn you; it will simply
be wrong, and look like you drew it off-center.

## Size is a fraction of the map

`size:` is a height, and a bare number is a fraction of the **map's** height
- `marker-size:` on the radar sets it for every pin that says nothing, and
is 0.2 unless a config or a theme says otherwise.  A value with units is
used as written.  The three names `small`, `mid` and `tiny` are proportions
of that default, kept from v1, which used 64, 70 and 40 pixels against 80.

What this means for your drawing: **the number is the height of your whole
image, not of the visible mark.**  A tip-anchored marker at `0.2` on a 350px
map is a 70px canvas holding a 35px pin, because half of it is padding.  A
centered one at `0.2` is 70px of visible mark.  Two markers at the same
`size:` are not the same size on screen unless they pad the same way.

Width follows the aspect ratio; only height is asked for.

The shipped art is 64 tall, so at the default it is usually being scaled
**up** a little.  Draw yours larger than you need - the scale is smooth, and
a 128 or 256 tall drawing costs nothing but disk and survives a big screen.

## Greyscale, so `color:` can work

`color:` multiplies each channel of your image by that color and keeps the
alpha.  The consequences are worth knowing before you draw:

- **Grey becomes that color at that brightness.**  A pin drawn in greys
  keeps all its shading when tinted, which is why the shipped six are pure
  greyscale - 510 inked pixels, not one of them off-grey.
- **Black stays black.**  Zero times anything is zero, so a symbol drawn in
  `#000000` is never tinted.  That is how the house stays black on a red
  pin, and it is the way to keep part of a marker out of the tint.
- **Color can only be darkened.**  Multiplying a red pin by green gives you
  nearly nothing.  Draw in grey and let the config choose, or draw in the
  color you want and never set `color:`.
- **The brightest pixel caps the result.**  The shipped art tops out at 229,
  not 255, so `color: red` gives `#e50000` rather than pure red.  Draw to
  255 if you want a tint to reach full saturation.

## Transparency

Alpha is what makes a marker sit on a map instead of in a box, and partial
alpha is most of what makes it look drawn rather than pasted.  Of the 510
inked pixels in the shipped art, 145 are partial - the antialiased rim, and
a soft shadow falling down and to the right of the tip.

That shadow is worth copying.  The anchor is a few pixels below the pin's
solid tip, and the shadow fills that gap, so the pin reads as standing on
the spot rather than floating above it.

Alpha is preserved through both the tint and the scale, so nothing you do
in the config will harden your edges.

## Where the file is found

`image:` in a config names your marker.  A bare name comes from **the set**
the radar draws from - `PiClock3/MapLoop/markers`, unless a theme names
another - and `.png` is added if you leave the extension off.

A name with a path in it, `art/mine.png`, is read from where it says.  That
is the way to use one drawing without shipping a whole set.

One older route is still honoured ahead of both: a config that names
`folders: marker:` has that folder looked in first.  It is deprecated and
nothing shipped uses it, but a config written before sets existed keeps
drawing its own pins.

**A set is just a folder of PNGs.**  To restyle every pin without touching
anybody's locations, ship a folder holding the same names and point a theme
at it:

```yaml
# themes/mine/theme.yaml
kind-settings:
  radar:
    marker-images-folder: markers
    marker-images-base-folder: '{this-folder}'
```

Now `image: teardrop-home` in any config finds
`themes/mine/markers/teardrop-home.png` instead of the shipped one, and no
config has to be edited for it - see
[WRITING-A-THEME.md](WRITING-A-THEME.md).

## Checking your work

Run the clock and look at it; there is no preview tool.  Worth checking
specifically:

- **the anchor.** Put one marker on a coordinate you can recognise - a
  bridge, a runway, a lake's north tip - and look at two zoom levels.  The
  same feature should be under the same part of your art both times.  If it
  is off by half the marker's height, the ink is not where you think it is
  in the canvas.
- **a small radar and a large one on the same clock.** The classic layout
  gives a radar about a third the height of the bigmaps one, and `size:`
  being a fraction means your marker should look the same on both.
- **the tint**, if you drew in grey: set `color:` to something saturated and
  check nothing that should have stayed black has taken the color.
- **against weather.** A marker sits under nothing - it is drawn over the
  radar - so the thing to check is the reverse: that a storm behind it does
  not swallow it.  Outline or shadow is what saves it.
- **the log at `debug`**, which prints `drawImage x y` for each marker drawn
  and warns by name for any it could not find.
