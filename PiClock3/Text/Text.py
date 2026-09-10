"""Words in a region.

Static text is the ordinary case: a city name over a clock face, a note
under a map.  It goes through expand(), so anything the clock knows can be
written into it.

A text-provider: is the other case - a plugin that supplies words and says
when they change.  Nothing ships with one; the role it implements is
TextSource.  With both given, the config's text: is what stands there until
the source first speaks.

Three things to do with a line too wide for its region, because none of
them is right for every region: shrink it, scroll it past, or let the edge
cut it.
"""
import logging

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QLabel

from ..FitLabel import FitLabel
from ..Widget import Widget

logger = logging.getLogger(__name__)

# how often a marquee moves.  Fast enough not to step visibly, and the
# only cost when nothing has to travel is a comparison.
TICK = 40


class Text(Widget):

    def __init__(self, piclock, name, config):
        super().__init__(piclock, name, config)
        self.label = None
        self.provider = None
        self.timer = None
        self.overflow = 'clip'
        self.span = 0
        self.offset = 0.0
        self.step = 0.0

    def start(self):
        self.overflow = str(self.config['overflow'] or 'clip')
        rect = self.region.frameRect()
        # a marquee moves its label, so the label is as wide as its words
        # and Qt clips it to the region; the other two fill the region and
        # are centered in it
        self.label = (QLabel(self.region) if self.overflow == 'marquee'
                      else FitLabel(self.region))
        self.label.setObjectName('text')
        self.label.setGeometry(rect)
        # only the size.  color, font-family and font-weight arrive on the
        # region and Qt inherits them, so the words draw in the color the
        # theme wrote
        props = self.scaleFont({'font-size': self.config['font-size']},
                               rect.height())
        # kept, because FitLabel appends a smaller font-size to it rather
        # than building a sheet of its own
        rule = self.styleRule('text', props,
                              self.config['extra-font-attributes'])
        self.label.setStyleSheet(rule)

        if self.overflow == 'marquee':
            self.label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.timer = QTimer()
            self.timer.timeout.connect(self.scroll)
            self.timer.start(TICK)
        else:
            self.label.setAlignment(Qt.AlignCenter)
            self.label.baseStyle = rule
            if self.overflow == 'fit':
                # FitLabel comes down from a ceiling and never goes up, so
                # the size asked for is the largest it will ever draw
                self.label.fitCeiling = self.fontPixels(
                    props.get('font-size'), rect.height())

        self.setText(self.piclock.expand(self.config['text'] or ''))
        name = self.config['text-provider']
        if name:
            self.provider = self.piclock.plugins[name]
            self.provider.subscribe(self.fromProvider)

    def pageChange(self):
        return

    def fontPixels(self, size, height):
        """the ceiling to fit down from, as a number.

        scaleFont answers in css - '48px' - because that is what a
        stylesheet wants, and drops the size altogether at font-size: 0,
        which asks for nothing but the box to constrain it.
        """
        if size is None:
            return int(height * 0.8)
        try:
            return int(float(str(size).replace('px', '').strip()))
        except ValueError:
            logger.warning('%s: cannot size text by %r', self.name, size)
            return int(height * 0.8)

    def fromProvider(self):
        """the source has something to say, so say it.

        As it stands: a source has already decided on its words, and a
        widget rewriting them would be guessing.
        """
        self.setText(self.provider.text())

    def setText(self, text):
        text = text or ''
        self.label.setText(text)
        # measured again when it is drawn, because the words have changed
        # and the label is only as wide as the ones it had
        self.span = 0

    def scroll(self):
        """one step of a marquee, or nothing where the words already fit"""
        rect = self.region.frameRect()
        if not self.span:
            self.label.adjustSize()
            self.span = self.label.width()
            self.step = (self.config['marquee-speed']
                         * rect.width() * TICK / 1000.0)
            self.offset = float(rect.width())
            self.label.setGeometry(rect.width(), 0, self.span, rect.height())
        if self.span <= rect.width():
            # a sign with room for its words should not be moving them
            self.label.move(0, 0)
            return
        self.offset -= self.step
        if self.offset < -self.span:
            self.offset = float(rect.width())
        self.label.move(int(self.offset), 0)
