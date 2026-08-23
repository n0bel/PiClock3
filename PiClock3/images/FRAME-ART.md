# Drawing a frame for PiClock3

A frame is **one PNG holding a 3x3 grid of cells**.  PiClock3 slices it into
nine pieces, keeps the corners as corners, and stretches the edges along
whatever box it is framing.  One file frames a box of any size, on any screen.

Four frames ship.  `frame-amber.png`, `frame-blue.png` and `frame-green.png`
are one soft-edged drawing in three colors, 60x60, so 20x20 cells.
`frame-hairline.png` is a different drawing entirely - a solid hard-edged
line, 24x24, so 8x8 cells - and the two kinds want different settings, which
the rest of this explains.

## The sheet

Nine cells in reading order:

    +-----------+-----------+-----------+
    | top-left  |    top    | top-right |
    +-----------+-----------+-----------+
    |   left    |  center   |   right   |
    +-----------+-----------+-----------+
    |bottomleft |  bottom   |bottomright|
    +-----------+-----------+-----------+

- The image must divide evenly into three across and three down.  The cell
  size is derived from the image: width / 3 and height / 3.  It is never
  written down in a theme, so the art cannot disagree with the config.
- **Keep the cells square.**  Every piece is drawn into a square of the
  frame's thickness, so a tall cell gets squashed.  Non-square sheets still
  load; they just distort the corners.
- **The center cell must be fully transparent.**  It is stretched across the
  whole interior of the box; anything in it covers the content.

## How the pieces are used

| piece | drawn | scaled |
|---|---|---|
| the four corners | at the box's four corners | to thickness x thickness |
| top, bottom | between the top and bottom corners | stretched horizontally |
| left, right | between the left and right corners | stretched vertically |
| center | the interior | not drawn (transparent) |

Edges are **stretched, not tiled**.  A repeating motif along an edge will
smear when the box is wide.  If you want texture along an edge, put it in
the corners where it keeps its shape.

## Thickness: `width`

The theme says how heavy the frame is, as a fraction of **screen height**:

```yaml
borders:
  default:
    art: '{folders.image}/frame-amber.png'
    width: 0.012      # about 13px on a 1080p screen
```

That is deliberately not a fraction of the box.  Every framed box on the
page gets the same weight, whether it is a big map or a small forecast cell,
and the whole page scales together from 800x600 to 1920x1080.

**What this means for you:** the cell's pixel size is not the frame's size on
screen.  Every piece is rescaled to `width`.  Draw at whatever resolution
gives you enough detail.  20px cells are plenty for a soft glow; a crisp
bevel wants more.

**Fill the cell edge to edge.**  This is the one rule that trips people up.
Blank margin inside a cell does not disappear - it scales up with
everything else and becomes dead space that holds content away from the
frame.  The first cut of the shipped frame had 4px of padding in a 24px cell,
and it showed up on screen as a dark gap under the line.

## Where content lands: `inset`

This is the part the artwork cannot tell us, so you have to.

A frame with a **drop-off edge** - a hard inner boundary, like a bevel or a
solid rule - says where content goes: right up against the drop.  A frame
with a **fading edge** - a glow, a soft airbrushed line - has no boundary at
all.  Its alpha just tails off, and there is no pixel that means "content
starts here".

The three color frames are the second kind.  Alpha rises and falls
symmetrically across the 20px cell, peaking dead center:

    0  0  2  6 16 41 91 164 213 237 | 244 237 213 164 91 41 16  6  2  1

So the theme names the landing, as a fraction of the frame's thickness:

```yaml
    inset: 0.5
```

| `inset` | content edge lands at | looks like |
|---|---|---|
| `1.0` | the inner end of the frame | the whole frame stays clear of the content |
| `0.75` | part way into the fade | a little of the glow falls across the content |
| `0.5` | the middle of the line | the inner half of the glow lies on the content |

Values below 0.5 are clamped: two cells sharing a rule would start
overlapping each other.

The frame is drawn **over** the content, so at `0.5` the glow falls across
the map the way a light would.  If content were drawn on top instead it
would slice the tube in half and turn your fading edge into a drop-off one.

`frame-hairline.png` is the first kind, and shows what that changes.  Every
cell but the center is solid, so the line has no falloff at all - at any
width it is N pixels of flat color and then content.  Its theme sets
`inset: 1.0`, because there is no fade to pull content back out of; content
sits flush against the edge.  Set `0.5` on a frame like that and you would
simply hide half the line under the content.

## Repeats, rules and corners

A layout can repeat a region - nine forecast boxes, two stacked maps:

```yaml
forecast: {right: 0.0, top: 0.0, width: 0.2, height: 1.0,
           border: true, repeat: {count: 9, direction: down}}
```

The group is framed **once**, and the cells are separated by straight rules.
Each rule is one edge of your sheet on its own, with no corner pieces:

- a horizontal rule uses your **top** cell, stretched across
- a vertical rule uses your **left** cell, stretched down

Corner pieces are drawn only at the group's four real corners.  This matters
because a corner is where a line *ends* - corner art usually turns and fades
out.  Putting it at an internal join leaves a notch in the line running
through it.

**Two things to design for:**

1. **Your top and left cells get reused as rules.**  A symmetric glow works
   either way.  A frame lit from above - a bevel with a highlight on
   the top edge and a shadow on the bottom - will look like a top edge, not
   like a divider, when it is used between two cells.  If your frame has a
   light direction, its edges will not make convincing rules.
2. **Edges must meet corners cleanly.**  The join between an edge piece and
   a corner piece is a hard cut at the cell boundary.  Whatever the edge
   looks like at its ends has to match what the corner looks like where they
   meet, or you get a visible step.

## Color

The shipped frames are a single flat RGB with the shape carried entirely in
the alpha channel:

| file | color | where it came from |
|---|---|---|
| `frame-amber.png` | `#fda400` | the original frame art; PiClock v1's kevin |
| `frame-blue.png` | `#11237e` | PiClock v1's jean |
| `frame-green.png` | `#1c5721` | PiClock v1's bedside and night configs |
| `frame-hairline.png` | `#ff8019` | the chris background's own sunset hue, at full strength |

The three color frames are the same alpha with a different RGB, which is the
whole point of building art that way: a new color costs nothing and loses
nothing.  Art with a baked-in gradient cannot be recolored like this.

To add a color, take any of the shipped sheets, keep its alpha channel and
replace the RGB - in GIMP, Colors > Map > Colorize, or a new layer of flat
color with the sheet's alpha as a mask.  Nothing else about the file changes.

Painting a frame that is not flat-plus-alpha is fine.  It just means color
variants have to be drawn rather than derived.

## Using it

Drop the PNG next to the others and point a theme at it:

```yaml
borders:
  default:
    art: '{folders.image}/my-frame.png'
    width: 0.012
    inset: 0.5
  radar:
    art: '{folders.image}/my-frame-heavy.png'
    width: 0.02
    inset: 0.75
```

A layout asks for `border: true` to get `default`, or `border: radar` for a
named one.  An unknown name falls back to `default`, so any theme still
works with any layout.

Themes in `PiClock3/themes/` are the shipped ones; a file of the same name in
`themes/` at the top level wins, so you can try a frame without editing
anything that ships.

A theme can be a file or a folder.  All of these are found:

    themes/mine.yaml            a file you dropped in
    themes/mine/theme.yaml      a folder, canonical name
    themes/mine/mine.yaml       a folder named after itself

The last two are what `git clone <repo> themes/mine` gives you, so a theme
someone else published works as a checkout with nothing to unpack.

**Inside a folder, ship your art with your theme.**  A plain relative path
is relative to the folder the theme was loaded from, so write `art:
'myframe.png'` and put the PNG beside the `.yaml`.  The theme never has to
know where it was installed.  A path containing a `{placeholder}` is left
alone - that is how the shipped themes reach the common image directory
with `'{folders.image}/frame-amber.png'`.

## Checking your work

Run the clock and look at it - there is no preview tool.  Worth checking
specifically:

- a **small** box and a **large** one on the same page: the frame should be
  the same weight on both
- the **rules between repeated cells**: the line running through them should
  not thin, brighten or break at the join
- the **corners**: the edge should meet the corner with no step
- **content against the frame**: adjust `inset` until it sits where you want
