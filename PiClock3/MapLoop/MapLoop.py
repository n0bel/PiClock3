import logging
import os
import time

from ..Plugin import Plugin

from PyQt5 import (QtGui, QtNetwork)
from PyQt5.QtCore import (QObject, QThread, pyqtSlot, pyqtSignal, Qt,
                          QSize, QTimer)
from PyQt5.QtGui import (QPixmap, QImage, QPainter, QColor, QFont,
                         QFontMetrics, QPainterPath, QPen, QBrush)
from PyQt5.QtWidgets import (QWidget, QLabel, QMessageBox, QListWidget,
                             QPushButton, QApplication, QTableWidget,
                             QGridLayout, QListWidgetItem, QTableWidgetItem,
                             QLineEdit, QFrame)

from ..DottedDict import Missing
from ..Projection import (getCorners, getPoint, getTileXY, LatLng,
                          MapView)

logger = logging.getLogger(__name__)

# no data source has an opinion about where you live
DEFAULT_CENTER = {'latitude': '{location.latitude}',
                  'longitude': '{location.longitude}'}
DEFAULT_ZOOM = 7

# the line every map carries when nothing else is asked for.  Only the frame
# provider is named: radar tiles carry nothing of their own, while a base map
# arrives with its own mark already on it and that mark is put back on top.
# {plugin-data.base-attribution} is there for a config that wants it anyway.
DEFAULT_CAPTION = '{plugin-data.frame-caption}'

# how far off the edge the built-in captions sit, as a fraction of the map
MARGIN = 0.02

# how long to wait before asking again for a base map or overlay that did not
# arrive.  Neither is on a timer of its own the way radar frames are, so this
# is the only thing that fetches them again.
#
# Quick at first, because most failures are a hiccup and clear on the next
# try, then backing off hard: a service that is down for the afternoon should
# be asked once an hour, not three times a minute.  Four tries at each step.
RETRY_STEPS = (5, 30, 300, 3600)
RETRY_TRIES = 4

# what to draw the radar on when there is no base map to be had.  Dark enough
# that the light end of a radar palette still reads, plain enough that nobody
# mistakes it for terrain.
NO_MAP = '#3a3a3a'


class MapLoop(Plugin):

    def __init__(self, piclock, name, config):
        super().__init__(piclock, name, config)
        self.baseProvider = self.piclock.plugins[self.config['base-provider']]
        self.overlayProvider = self.piclock.plugins[
            self.config.get('overlay-provider') or self.config['base-provider']]
        self.frameProvider = self.piclock.plugins[self.config['frame-provider']]
        self.view = None
        self.mapPixmap = None
        self.overlayPixmap = None
        self.markerPixmap = None
        # the base map's own logo and credit, cut out of the pixmap it
        # arrived in, to go back on top of the radar that would cover it
        self.brandMark = None
        self.overlayFailed = False
        self.baseFailed = False
        self.tries = {}
        self.framePixmaps = dict()
        self.finished = dict()
        self.frame = 0

    def mapView(self):
        """the one view every layer of this map uses"""
        c = self.setting('center', self.frameProvider, DEFAULT_CENTER)
        zoom = self.setting('zoom', self.frameProvider, DEFAULT_ZOOM)
        return MapView(
            LatLng(float(self.piclock.expand(str(c['latitude']))),
                   float(self.piclock.expand(str(c['longitude'])))),
            int(self.piclock.expand(str(zoom))),
            self.region.contentsRect())

    def start(self):
        # every layer is composited into one pixmap per frame, so there is one
        # widget rather than a stack of transparent ones.  It is what lets the
        # captions and the vendors' own marks sit above the radar at all.
        rr = self.region.contentsRect()
        self.mapLabel = QLabel(self.region)
        self.mapLabel.setObjectName("mapLabel")
        self.mapLabel.setGeometry(rr)
        self.mapLabel.setStyleSheet("#mapLabel { background-color: transparent; }")
        self.mapLabel.setAlignment(Qt.AlignCenter)
        logger.debug("maploop geom %s", rr)

        self.captions = self.captionList()

        logger.debug("maploop get map pixmap")
        self.view = self.mapView()
        logger.debug('maploop view %s', self.view)
        self.getBasePixmap()
        self.getOverlayPixmap()
        self.interval = 60 * self.config.interval
        self.frameCount = self.config.frames
        self.intervalTimer = QTimer()
        self.intervalTimer.timeout.connect(self.intervalTick)
        self.intervalTimer.start(1000  * self.interval)
        self.intervalTick()
        self.dwell = max(20, int(self.config.dwell)
                         if 'dwell' in self.config else 200)
        self.hold = max(0, int(self.config.hold)
                        if 'hold' in self.config else 1200)
        self.animationTimer = QTimer()
        self.animationTimer.timeout.connect(self.animationTick)
        self.animationTimer.start(self.dwell)
        return


    def getBasePixmap(self):
        self.baseProvider.getMapPixmap(self.view, self.config,
                                       self.gotMapPixmap)

    def getOverlayPixmap(self):
        if not self.config.get('overlay-style'):
            return
        overlay = dict(self.config)
        overlay['style'] = self.config['overlay-style']
        self.overlayProvider.getMapPixmap(self.view, overlay,
                                          self.gotOverlayPixmap)

    def pageChange(self):
        self.intervalTick()
        return

    def intervalTick(self):
        logger.debug("tick %s %s", self.name, self.region.isVisible())
        if not self.region.isVisible():
            return
        wanted = self.frameProvider.frameTimes(self.frameCount)
        for t in list(self.framePixmaps):
            if t not in wanted:
                self.framePixmaps.pop(t)
        for t in list(self.finished):
            if t not in wanted:
                self.finished.pop(t)
        self.getNextNeededFrame()

    def animationTick(self):
        if not self.region.isVisible():
            return;
        frameTimes = sorted(self.finished)
        if len(frameTimes) < 1: return
        if self.frame >= len(frameTimes):
            self.frame = -int(self.hold / self.dwell)
        f = self.frame
        if f < 0:
            f = len(frameTimes) - 1
        self.mapLabel.setPixmap(self.finished[frameTimes[f]])
        self.frame += 1

    def gotMapPixmap(self, pixmap, mask=None):
        logger.info("maploop got map pixmap");
        if pixmap is None or pixmap.isNull():
            # a plain field rather than nothing: the weather is the part that
            # cannot wait, and there is no next base map coming on its own -
            # unlike a radar frame, it is asked for once
            self.baseFailed = True
            self.mapPixmap = self.blankMap()
            self.brandMark = None
            self.askAgain('base map', self.getBasePixmap)
        else:
            self.tries['base map'] = 0
            if self.baseFailed:
                logger.info("%s: base map arrived late, redoing %d frames",
                            self.name, len(self.finished))
                self.baseFailed = False
                self.finished.clear()
            self.mapPixmap = pixmap
            logger.debug("radar %s", pixmap.size())
            self.keepBrandMark(pixmap, mask)
        self.makeMarkerPixmap()
        # whatever the base is, it is what shows until a frame has been
        # composited onto it
        if not self.finished:
            self.mapLabel.setPixmap(self.mapPixmap)
        self.compositeWaiting()

    def askAgain(self, what, again):
        """schedule another try for a map that did not arrive, backing off.

        The step depends on how many times this particular one has failed, so
        a working base map and a broken overlay back off independently.
        """
        tries = self.tries.get(what, 0)
        self.tries[what] = tries + 1
        wait = RETRY_STEPS[min(tries // RETRY_TRIES,
                               len(RETRY_STEPS) - 1)] * 1000
        logger.warning("%s: no %s (try %d), asking again in %ds",
                       self.name, what, tries + 1, wait // 1000)
        QTimer.singleShot(wait, again)

    def blankMap(self):
        """a plain field to draw radar on when there is no map to be had.

        Nothing is attributed to anybody here - it is not anyone's imagery,
        so there is no mark to restore and none is claimed.
        """
        blank = QPixmap(self.region.contentsRect().size())
        blank.fill(QColor(NO_MAP))
        return blank

    def gotOverlayPixmap(self, pixmap, mask=None):
        logger.info("maploop got overlay pixmap")
        if pixmap is None or pixmap.isNull():
            # the map draws without it from here rather than waiting: labels
            # over the radar are worth having, but not worth a blank map
            self.overlayFailed = True
            self.askAgain('overlay', self.getOverlayPixmap)
            self.compositeWaiting()
            return
        self.overlayPixmap = pixmap
        self.tries['overlay'] = 0
        if self.overlayFailed:
            # frames were composited without it, so they are wrong now
            logger.info("%s: overlay arrived late, redoing %d frames",
                        self.name, len(self.finished))
            self.overlayFailed = False
            self.finished.clear()
        self.compositeWaiting()

    def keepBrandMark(self, pixmap, mask):
        """the base map's own logo and credit, cut out of the pixmap it drew
        them into, ready to go back over the radar.

        Only the base map's.  It is the layer everything else is drawn on top
        of, so it is the only one whose mark gets buried; an overlay is drawn
        above the radar and keeps its own.

        Masked here rather than in composite() so it happens once per map
        instead of once per frame.
        """
        if mask is None or pixmap.isNull():
            return
        if self.config.get('ignore-attribution-mask'):
            logger.info("%s: ignore-attribution-mask - the radar will cover "
                        "whatever mark the map arrived with", self.name)
            return
        # DestinationIn can only take alpha away, so the target has to have
        # some: a pixmap filled with an opaque color has no alpha channel and
        # the mask would do nothing at all
        cut = QPixmap(pixmap.size())
        cut.fill(Qt.transparent)
        painter = QPainter()
        painter.begin(cut)
        painter.drawPixmap(0, 0, pixmap)
        painter.setCompositionMode(QPainter.CompositionMode_DestinationIn)
        painter.drawImage(0, 0, mask)
        painter.end()
        self.brandMark = cut
        logger.debug("maploop keeping brand mark")

    def makeMarkerPixmap(self):
        self.markerPixmap = QPixmap(self.mapPixmap.size())
        self.markerPixmap.fill(Qt.transparent)
        #br = QBrush(QColor(Config.dimcolor))
        painter = QPainter()
        painter.begin(self.markerPixmap)
        #painter.fillRect(0, 0, self.mkpixmap.width(),
        #                 self.mkpixmap.height(), br)
        markers = self.config.markers if 'markers' in self.config else []
        for marker in markers:
            if 'visible' not in marker or marker['visible'] == 1:
                loc = LatLng(float(self.piclock.expand(marker["location"]["latitude"])),
                             float(self.piclock.expand(marker["location"]["longitude"])))
                pt = getPoint(
                    loc, self.view.center, self.view.zoom,
                    self.mapPixmap.width(), self.mapPixmap.height())
                mk2 = QImage()
                mkfile = 'teardrop'
                if 'image' in marker:
                    mkfile = self.piclock.expand(marker['image'])
                if os.path.dirname(mkfile) == '':
                    mkfile = os.path.join(self.piclock.expand('{folders.marker}'), mkfile)
                if os.path.splitext(mkfile)[1] == '':
                    mkfile += '.png'
                mk2.load(mkfile)
                if mk2.format != QImage.Format_ARGB32:
                    mk2 = mk2.convertToFormat(QImage.Format_ARGB32)
                logger.debug("yy size %s", mk2.size())
                mkh = 80  # self.rect.height() / 5
                if 'size' in marker:
                    if marker['size'] == 'small':
                        mkh = 64
                    if marker['size'] == 'mid':
                        mkh = 70
                    if marker['size'] == 'tiny':
                        mkh = 40
                if 'color' in marker:
                    c = QColor(marker['color'])
                    (cr, cg, cb, ca) = c.getRgbF()
                    for x in range(0, mk2.width()):
                        for y in range(0, mk2.height()):
                            (r, g, b, a) = QColor.fromRgba(
                                           mk2.pixel(x, y)).getRgbF()
                            r = r * cr
                            g = g * cg
                            b = b * cb
                            mk2.setPixel(x, y, QColor.fromRgbF(r, g, b, a)
                                         .rgba())
                mk2 = mk2.scaledToHeight(mkh, 1)
                x = int(pt.x - mkh / 2)
                y = int(pt.y - mkh / 2)
                logger.debug("drawImage %d %d", x, y)
                painter.drawImage(x, y, mk2)
        painter.end()

    def getNextNeededFrame(self):
        if not self.region.isVisible():
            return
        times = self.frameProvider.frameTimes(self.frameCount)
        if not times:
            QTimer.singleShot(2000, self.getNextNeededFrame)
            return
        # newest first, so the picture on screen is current within one
        # request.  The animation sorts what it has, so order here is free.
        for t in reversed(times):
            if t not in self.framePixmaps:
                logger.debug("maploop next needed frame %s",
                             time.asctime(time.localtime(t)))
                self.frameProvider.getFramePixmap(
                    t, self.view, self.config, self.gotFramePixmap)
                return

    def gotFramePixmap(self, pixmap, timeSlot):
        logger.debug("got radar pixmap %s %s %s", pixmap, timeSlot, time.asctime(time.localtime(timeSlot)))
        self.framePixmaps[timeSlot] = pixmap
        if self.ready():
            self.finished[timeSlot] = self.composite(timeSlot)
        self.getNextNeededFrame()

    def ready(self):
        """whether everything a finished frame needs has arrived.

        The requests all go out at once and the base map is one large image
        against many small tiles, so it is a real race and radar frames often
        win it.
        """
        if self.mapPixmap is None or self.mapPixmap.isNull():
            return False
        # an overlay is worth waiting for, but not forever: a map that draws
        # without its labels beats one that never draws
        if (self.config.get('overlay-style') and self.overlayPixmap is None
                and not self.overlayFailed):
            return False
        return True

    def compositeWaiting(self):
        """finish whatever frames were waiting on the map arriving"""
        if not self.ready():
            return
        for timeSlot in self.framePixmaps:
            if timeSlot not in self.finished:
                self.finished[timeSlot] = self.composite(timeSlot)
        if not self.finished:
            # no radar yet, and maybe none coming.  The markers, the overlay
            # and the base map's own credit belong on the map whether or not
            # there is weather to draw over it.
            self.mapLabel.setPixmap(self.composite(None))

    def composite(self, timeSlot):
        """one flat pixmap: map, radar, overlay, markers, marks, captions.

        Compositing here rather than stacking transparent widgets is what puts
        the captions and the vendors' marks above the radar, and it happens
        once per frame fetched rather than on every repaint of the loop.
        """
        out = QPixmap(self.mapPixmap.size())
        painter = QPainter()
        painter.begin(out)
        painter.drawPixmap(0, 0, self.mapPixmap)

        frame = self.framePixmaps.get(timeSlot)
        if frame is not None and not frame.isNull():
            painter.setOpacity(self.opacity('frame-opacity'))
            painter.drawPixmap(0, 0, frame)
            painter.setOpacity(1.0)

        if self.overlayPixmap is not None and not self.overlayPixmap.isNull():
            painter.setOpacity(self.opacity('overlay-opacity'))
            painter.drawPixmap(0, 0, self.overlayPixmap)
            painter.setOpacity(1.0)

        if self.markerPixmap is not None:
            painter.drawPixmap(0, 0, self.markerPixmap)

        if self.brandMark is not None:
            painter.drawPixmap(0, 0, self.brandMark)

        self.drawCaptions(painter, timeSlot, out.width(), out.height())
        painter.end()
        return out

    def opacity(self, name):
        value = self.config.get(name)
        try:
            return min(1.0, max(0.0, float(value)))
        except (TypeError, ValueError):
            logger.warning("%s: %s is not a number: %r", self.name, name, value)
            return 1.0

    def captionList(self):
        """the captions to draw, from captions: or from the older keys.

        A supplied list replaces rather than adds to: Config._merge assigns
        anything that is not a dict outright, so a narrower tier restates the
        whole list rather than adjusting one entry of it.
        """
        given = self.config.get('captions')
        if given:
            if self.config.get('label'):
                logger.info("%s: captions: given, so label: is not drawn",
                            self.name)
            entries = [{'text': c} if isinstance(c, str) else dict(c)
                       for c in given]
            # a caption carries a time format inside its braces, so it needs
            # the same rewrite every other format gets - glibc drops a leading
            # zero with %-I and the Windows CRT with %#I, and Windows raises
            # on %-I rather than ignoring it.  Once, here, not on every draw.
            for entry in entries:
                entry['text'] = self.strftimePortableFormat(
                    str(entry.get('text', '')))
            # an entry that says nothing about where it goes lands in the top
            # left, off the edge by the same margin the built-in captions use
            # rather than flush against it
            for entry in entries:
                if not any(k in entry for k in
                           ('left', 'right', 'horizontal-center')):
                    entry['left'] = MARGIN
                if not any(k in entry for k in
                           ('top', 'bottom', 'vertical-center')):
                    entry['top'] = MARGIN
            # a base map's own mark is put back on top whatever the list says,
            # but nothing else credits the frame provider
            named = ('frame-caption', 'frame-attribution')
            if not any(n in str(c.get('text', ''))
                       for c in entries for n in named):
                logger.warning(
                    "%s: no caption names the frame provider - %s asks to be "
                    "credited and nothing else on the map does it",
                    self.name, self.frameProvider.attribution() or 'it')
            return entries

        entries = [{'text': DEFAULT_CAPTION,
                    'left': MARGIN, 'top': MARGIN, 'outline': True}]
        if self.config.get('label'):
            # label-size is a fraction of the map, which is what it has always
            # meant, and a caption's size is a fraction of the screen - so it
            # is converted rather than passed on, and a config written before
            # captions existed draws its name at the size it always did
            mapHeight = self.region.contentsRect().height()
            screenHeight = max(1, self.piclock.screen.height())
            try:
                size = float(self.config['label-size']) * mapHeight / screenHeight
            except (TypeError, ValueError):
                size = None
            entry = {'text': str(self.config['label']),
                     'right': MARGIN, 'top': MARGIN,
                     'color': self.config['label-color']}
            if size:
                entry['size'] = size
            entries.append(entry)
        return entries

    def captionFont(self, entry):
        """a bare size is a fraction of the screen's height, one with units is
        used as written.

        The screen rather than the map, because one clock's radars are not one
        size - classic at 800x600 gives a 200px cell and bigmaps at 1080p an
        850px one, and no single fraction of the map reads on both.  What a
        caption should be is a size on the screen you are looking at, which is
        the same reasoning behind a theme's font-size being a fraction of the
        page.
        """
        size = entry.get('size', self.config.get('caption-size'))
        px = None
        if isinstance(size, str) and not size.replace('.', '', 1).isdigit():
            digits = ''.join(c for c in size if c.isdigit() or c == '.')
            try:
                px = float(digits)
            except ValueError:
                logger.warning("%s: cannot read caption size %r",
                               self.name, size)
        if px is None:
            try:
                px = float(size) * self.piclock.screen.height()
            except (TypeError, ValueError):
                px = 0.018 * self.piclock.screen.height()
        font = QFont()
        family = (entry.get('font-family') or self.config.get('font-family')
                  or self.themeDefault('font-family'))
        if family:
            font.setFamily(str(family))
        font.setPixelSize(max(6, int(round(px))))
        return font

    def drawCaptions(self, painter, timeSlot, width, height):
        """every caption, placed the way a layout places a region.

        A caption is a box inside the map, so left, right, top, bottom and the
        two centers mean here what they mean in a layout - fractions of what
        they sit in.  Its size is the text's own rather than a fraction, so
        that is what is handed to the same geometry, which then holds a side
        that would run past an edge at the edge.
        """
        # with no frame there is nothing to stamp a time on.  Missing rather
        # than an empty string: a caption asking for {...frame-time:%H:%M}
        # would be applying a time format to whatever is put here, and only
        # Missing answers a format specifier with nothing.  The attributions
        # are names rather than frame data and still stand.
        self.pluginData['frame-time'] = (
            self.piclock.localtime(timeSlot) if timeSlot is not None
            else Missing())
        self.pluginData['frame-caption'] = (
            self.frameProvider.frameCaption(timeSlot)
            if timeSlot is not None else Missing())
        self.pluginData['frame-attribution'] = self.frameProvider.attribution()
        self.pluginData['base-attribution'] = self.baseProvider.attribution()
        self.pluginData['overlay-attribution'] = \
            self.overlayProvider.attribution()

        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)

        for entry in self.captions:
            text = self.piclock.expand(str(entry.get('text', ''))).strip()
            if not text:
                continue
            font = self.captionFont(entry)
            metrics = QFontMetrics(font)
            box = dict(entry)
            box['width'] = metrics.horizontalAdvance(text) / float(width)
            box['height'] = metrics.height() / float(height)
            rect = self.piclock._regionRect(width, height, box)
            self.drawCaption(painter, entry, font, text,
                             rect.left(), rect.top() + metrics.ascent())

    def drawCaption(self, painter, entry, font, text, x, y):
        """one caption, outlined only if it asked to be.

        A stroked path rather than text drawn several times at an offset: the
        stroke is centred on the glyph outline, so it has to go down before
        the fill or it eats half its width out of the letter.
        """
        color = QColor(self.piclock.expand(str(
            entry.get('color', self.config.get('caption-color', '#fff')))))
        outline = entry.get('outline')
        painter.setFont(font)

        if not outline:
            painter.setPen(color)
            painter.drawText(int(x), int(y), text)
            return

        if outline is True:
            outline = '#000' if color.lightness() > 127 else '#fff'
        path = QPainterPath()
        path.addText(float(x), float(y), font, text)
        width = max(1.0, font.pixelSize() / 8.0)
        painter.strokePath(path, QPen(QColor(self.piclock.expand(str(outline))),
                                      width, Qt.SolidLine, Qt.RoundCap,
                                      Qt.RoundJoin))
        painter.fillPath(path, QBrush(color))
