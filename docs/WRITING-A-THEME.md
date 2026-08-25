# Writing a theme

A theme is what a page looks like: the picture behind it, the frames round
its boxes, the colors and the fonts, and which art the widgets use.  A page
names one and a layout says where things sit - the two are separate on
purpose, so any theme works with any layout.

    PiClock3/themes/meadow/theme.yaml
    PiClock3/themes/meadow/background.png
    PiClock3/themes/meadow/frame.png

Themes are found the way layouts, units and languages are found: a `themes`
folder of your own first, then `PiClock3/themes`.  Either a file or a folder
will do, so `themes/mine.yaml` and `themes/mine/theme.yaml` both work - a
folder being what a checkout of somebody else's theme looks like.

Drawing the frames themselves is [FRAME-ART.md](FRAME-ART.md).

## The file

A theme is a folder with a `theme.yaml` and whatever art it uses:

```yaml
name: Meadow
description: The meadow background

background: 'background.png'

default:                     # cascades to everything on the page
  font-size: 0.02            # a fraction of the screen height
  font-family: Arial
  background-color: transparent
  color: '#042299'

borders:
  default:
    art: 'frame.png'
    width: 0.012             # frame weight, a fraction of screen height
    inset: 0.5               # where content lands, a fraction of width
  radar:
    art: 'frame.png'
    width: 0.012
    inset: 0.5

kind-settings:               # what the plugins should use
  analog-clock:       {clock-images-folder: darkblue}
  current-conditions: {icons-folder: icons-darkblue}
  forecast:           {icons-folder: icons-darkblue}
```

`default:` sets the page-wide cascade, so pick `color:` against your
background - a pale blue reads well on the dark ones and is close to
invisible on a bright one.

Five of its names reach the widgets by themselves: **`color`,
`background-color`, `font-family`, `font-style` and `font-weight`**.  A
widget that takes a setting by one of those names is handed the page's answer
to it without asking, so setting `color:` once colors the digital clock, the
conditions and the forecast.  They are Qt's names and mean what Qt means by
them, which is why a plugin must not use one of them for anything else.

`font-size` is deliberately not among them.  It is a fraction of whatever it
sits in, and a page is not the same height as a region - the page's `0.02`
would draw a clock face four pixels tall.

`kind-settings:` is how a theme reaches anything else a plugin takes.  The
key is the plugin's **kind** - `analog-clock`, `forecast`, `radar` - and what
follows is merged into the settings of every plugin wearing it.  A kind means
"interchangeable with", so a setting under one means the same thing to all of
them.  `plugin-settings:` does the same for one plugin named exactly, as
`PiClock3.AnalogClock`, for when a kind is too broad.

An instance keeps the last word: a widget that names a value in the config
holds it, whatever the theme says.

`borders:` are named frames.  A layout asks for `border: true` to get
`default`, or `border: radar` for a named one, and an unknown name falls back
to `default` so any theme works with any layout.

`styles:` are named sets of raw Qt stylesheet properties, which a layout
region asks for by name with `style: date`.  Both files have a say in them,
and the theme has the last one:

- a layout carries its own under `layout-style-settings:`, because how big
  the text has to be to fit a region is the layout's business.  That is what
  lets a layout look right under a theme that has never heard of it.
- a theme's `styles:` are merged over those, one property at a time.  Setting
  `date: {font-size: 0.4}` changes the size and leaves the alignment the
  layout asked for.

So a theme need only say what it wants to differ.  None of the shipped themes
defines a style at present, because the sizes the layouts carry suit them all
- but redefining one is a first-class thing to do, not a leftover.

A name nothing defines is simply not applied, and says so in the log.

## A background that changes

`background:` takes a folder instead of a picture, and works through it:

```yaml
background:
  folder: 'slides'           # inside the theme, or any path you like
  interval: 305              # seconds on each picture
  fit: contain               # or cover
  color: '#000'              # behind contain, where the picture does not reach
  order: shuffle             # or sorted
```

Only `folder:` is needed; the rest are the defaults above.

`files:` takes its place when the pictures are named one by one rather than
gathered in a folder:

```yaml
background:
  files:
    - '../stag/background.png'
    - '../meadow/background.png'
  interval: 20
  fit: cover
```

A folder is listed again whenever something is put in it; a named set is
fixed.  `examples/gallery.yaml` uses the second form to work through every
background the shipped themes have, which cannot be a folder because each one
lives in its own theme and they all answer to `background.png`.

A relative path, in either form, is inside the theme, the same as any other
art - so a theme can ship its pictures, and `../` reaches a neighboring
theme's.  An absolute path is left alone, which is what your own photographs
want: they are not theme art and do not belong in the theme folder.

`contain` fits the whole picture in and fills what is left with `color:`.
`cover` fills the screen and crops what overhangs, taking the middle rather
than a corner.  Photographs of mixed shapes look better under `cover` on a
small screen, where letterbox bars cost real space.

`shuffle` is a running order dealt once, not a fresh pick each turn, so
stepping back goes to the picture you actually just saw.

Which pages run one follows from which theme they name: give the clock page a
theme with a folder and the maps page one with a picture, and only the clock
changes.  A page nobody is looking at stops until it is showing again.

**F6** steps back, **F7** forward, and **F8** holds on the picture showing.
Pictures are read when they are shown rather than all at once, and the folder
is listed again only when something in it changes - so a photograph dropped in
appears without restarting the clock.
