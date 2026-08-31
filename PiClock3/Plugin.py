import logging
import os
import re
import sys

logger = logging.getLogger(__name__)

from PyQt5.QtCore import (QObject, QPointF)
from PyQt5.QtGui import QColor, QImage, QLinearGradient, QPainter
from PyQt5.QtWidgets import QGraphicsDropShadowEffect

DASH = re.compile(r'%-([a-zA-Z])')
WINDOWS = sys.platform == 'win32'


class Plugin(QObject):

    def __init__(self, piclock, name, config):
        super().__init__()
        self.name = name
        self.piclock = piclock
        self.config = config
        self.plugin = config['plugin'] if 'plugin' in config else None
        self.pluginData = piclock.pluginData[name]
        if 'region' in config:
            self.regionName = config['region']
            # always a list; a plugin that only understands one cell uses
            # self.region and ignores the rest
            self.regions = piclock.regionList(self.regionName)
            self.region = self.regions[0]

    def start(self):
        return

    def scaleFont(self, props, height):
        """sizes text the way core does, under the layout this widget sits in
        rather than whichever page happened to be built last"""
        return self.piclock.scaleFont(props, height,
                                      getattr(self, 'region', None))

    @staticmethod
    def strftimePortableFormat(fmt):
        """a strftime string this machine will accept.

        glibc drops a leading zero with %-d, the Windows CRT with %#d, and
        Windows raises on %-d rather than ignoring it.  A config travels
        between them, so it is written the glibc way and turned round here.

        Call it in start() and keep what it returns: the answer cannot
        change while the clock runs, and the widgets that draw a time
        redraw every second.
        """
        return DASH.sub(r'%#\1', fmt) if WINDOWS else fmt

    def themeDefault(self, name):
        """what the page says a Qt property should be, or None.

        A last resort.  self.config is asked first: it already holds what
        the theme's default: said, what kind-settings and plugin-settings
        said, and what this widget's own entry said, in that order.

        For what a stylesheet cannot deliver.  Qt inherits color into text
        by itself, so a widget that only draws text never needs this - a
        graphics effect is not a stylesheet property and inherits nothing.
        """
        theme = self.piclock.instanceTheme(self.config) or {}
        return (theme.get('default') or {}).get(name)

    def color(self, default='white'):
        """the color this widget draws in, whoever answered."""
        found = self.config.get('color') or self.themeDefault('color')
        return self.piclock.expand(found) if found else default

    # what this service must be credited as.  A service that needs no credit
    # says nothing and contributes nothing to the line.
    ATTRIBUTION = ''

    def attribution(self):
        return self.ATTRIBUTION

    def frameCaption(self, timeSlot):
        """what to write over the frame for this time slot.

        A frame provider that knows more than the time - that this one is a
        nowcast rather than an observation, say - overrides this.
        """
        return "{0:%H:%M}".format(self.piclock.localtime(timeSlot))

    def bottomBandMask(self, pixmap, rsize, px, feather=0.35):
        """an alpha mask over a full-width band across the bottom of pixmap.

        `px` is measured in the response's own pixels, before whatever
        gotMapPixmap scaled it by, so it is scaled the same way here.

        The band is fully opaque and the softening is added *above* it: a mark
        sitting at the top of the band would otherwise go partly transparent,
        which is the obscuring this exists to prevent.  The left, right and
        bottom edges stay hard because they lie on the pixmap's own boundary,
        where there is nothing to fade into.
        """
        w, h = pixmap.width(), pixmap.height()
        band = max(1, round(px * h / max(1, rsize.height())))
        fade = max(0, round(band * feather))
        top = h - band

        mask = QImage(pixmap.size(), QImage.Format_Alpha8)
        mask.fill(0)
        painter = QPainter()
        painter.begin(mask)
        painter.fillRect(0, top, w, band, QColor(255, 255, 255, 255))
        if fade:
            ramp = QLinearGradient(QPointF(0, top - fade), QPointF(0, top))
            ramp.setColorAt(0.0, QColor(255, 255, 255, 0))
            ramp.setColorAt(1.0, QColor(255, 255, 255, 255))
            painter.fillRect(0, top - fade, w, fade, ramp)
        painter.end()
        logger.debug("%s branding band %dpx, %dpx feather, in %dx%d",
                     self.name, band, fade, w, h)
        return mask

    def applyEffect(self, widget, height=None):
        """the effect: setting, on one widget.

            effect: glow 0.125      blur, as a fraction of height
            effect: glow 0.125 150  and how far to lighten the color
            effect: none            or 'glow 0', or absent

        Qt gives a widget one effect and renders its whole subtree, so this
        replaces whatever the widget had.  The blur is a fraction because
        50 hard pixels is a quarter of the relative size on a 4K panel that
        it is on the 800x600 one it was chosen on.

        The color defaults to this widget's own, lightened - which is what
        makes the face readable without draining the color out of the text
        itself.  100 means the color as written; a pale color clips to white
        somewhere near 150, while a dark one stays in hue and simply
        brightens, so a dark-on-light theme does not get a white halo.
        """
        spec = self.config.get('effect')
        kind, blur, color, offset, lighten = self._effect(spec)
        if not kind or blur <= 0:
            widget.setGraphicsEffect(None)
            return None
        height = widget.height() if height is None else height
        effect = QGraphicsDropShadowEffect()
        effect.setBlurRadius(blur * height)
        effect.setOffset(offset[0] * height, offset[1] * height)
        effect.setColor(QColor(color) if color
                        else QColor(self.color()).lighter(lighten))
        widget.setGraphicsEffect(effect)
        logger.info('%s: %s blur %.0fpx %s', self.name, kind,
                    effect.blurRadius(), effect.color().name())
        return effect

    # blur as a fraction of the widget's height, and how far to lighten the
    # widget's own color for the glow.  A pale color has clipped to white by
    # 150, so on most themes this is as bright as it goes.
    EFFECT = {'blur': 0.125, 'lighten': 150}

    # glow and shadow are one Qt effect; only the offset tells them apart.
    # Anything else is a typo, and a typo draws nothing.
    EFFECTS = ('glow', 'shadow')

    def _effect(self, spec):
        """(kind, blur, color, offset, lighten) from either way of writing it"""
        off = (None, 0, None, (0, 0), 100)
        if not spec or spec == 'none':
            return off
        if isinstance(spec, str):
            # 'glow 0.125 150'.  A color cannot ride here: yaml reads a
            # space then # as a comment, so it would vanish in silence.
            word = spec.split()
            try:
                blur = float(word[1]) if len(word) > 1 else self.EFFECT['blur']
                light = int(word[2]) if len(word) > 2 else self.EFFECT['lighten']
            except ValueError:
                logger.warning('%s: cannot read effect %r', self.name, spec)
                return off
            kind, color, o = word[0], None, (0, 0)
        else:
            kind = spec.get('type', 'glow')
            if kind == 'none':
                return off
            o = spec.get('offset', 0)
            o = (o, o) if isinstance(o, (int, float)) else tuple(o)
            blur = float(spec.get('blur', self.EFFECT['blur']))
            light = int(spec.get('lighten', self.EFFECT['lighten']))
            color = spec.get('color')
        if kind not in self.EFFECTS:
            logger.warning("%s: no effect called '%s' - try %s", self.name,
                           kind, ' or '.join(self.EFFECTS))
            return off
        return kind, blur, color, o, light

    def pageChange(self):
        return

    def setting(self, name, provider, default):
        """this instance, then the provider it is asking, then the default.

        The provider tier is what lets a service that knows its own coverage
        supply a sensible center or zoom for any widget that does not say.
        """
        if name in self.config:
            return self.config[name]
        if provider is not None and name in provider.config:
            return provider.config[name]
        return default

    def expand(self, s):
        return self.piclock.expand(s)

    def icon(self, name, folder=None):
        """the file for a weather icon, yours before the shipped one.

        The name already says day or night: whatever supplied it knew
        whether the sun was up, which is not something a widget can work
        out from a picture.
        """
        folder = folder or self.config.get('icons-folder') or 'icons-lightblue'
        # a bare name is a set that ships; anything with a path in it is a
        # set somebody supplied, so it is where it says it is
        where = [folder] if '/' in folder.replace(os.sep, '/') else []
        where += [os.path.join(base, folder)
                  for base in ('icons', os.path.join('PiClock3', 'icons'))]
        for base in where:
            path = os.path.join(base, name + '.png')
            if os.path.isfile(path):
                return path
        logger.warning('no icon %s in %s', name, folder)
        return ''

    def units(self, quantity, frm, value):
        """a value in `frm`, shown the way this instance asks for it.

        The set is this instance's units: if it has one, otherwise the
        clock's.  Precision is the table's unless a precision: block on
        the plugin or the instance says otherwise - a narrow column wants
        whole degrees where a big readout wants a tenth.
        """
        return self.piclock.units.format(
            quantity, frm, value,
            setName=self.unitSet(),
            precision=self.precision(quantity))

    def unitSet(self):
        chosen = self.config.get('units')
        if isinstance(chosen, str) and chosen:
            return chosen
        return self.piclock.units.setName()

    def precision(self, quantity):
        want = self.config.get('precision')
        if isinstance(want, dict) and quantity in want:
            return want[quantity]
        return None
