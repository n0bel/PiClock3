import datetime
import importlib
import inspect
import locale
import logging
import logging.handlers
import os
import re
import zoneinfo

import tzlocal
import yaml

from PyQt5 import (QtNetwork)
from PyQt5.QtCore import (Qt, QRect,
                          QSize)
from PyQt5.QtGui import (QImage, QFontMetrics)
from PyQt5.QtWidgets import (QWidget, QLabel, QApplication, QFrame)

from .Config import thisFolder
from .DottedDict import DottedDict
from .Languages import Languages
from .Plugin import Plugin
from .Slideshow import Slideshow
from .Units import Units

logger = logging.getLogger(__name__)


class FitLabel(QLabel):
    """text as large as fits across, asked for by font-size: 0.

    The size only ever comes down.  A clock started on a short date would
    otherwise clip on a long one.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.fitCeiling = None
        self.fitSize = None
        self.baseStyle = ''

    def setText(self, text):
        super().setText(text)
        if self.fitCeiling and text:
            self.fitText(text)

    def fitText(self, text):
        # a label renders markup, so the tags are not part of the width
        shown = re.sub(r'<[^>]*>', '', text)
        size = self.fitSize or self.fitCeiling
        room = self.width() - 4
        font = self.font()
        font.setPixelSize(int(size))
        while size > 6 and QFontMetrics(font).horizontalAdvance(shown) > room:
            size -= 1
            font.setPixelSize(int(size))
        if self.fitSize is not None and size >= self.fitSize:
            return
        self.fitSize = size
        # a stylesheet beats setFont, and the page carries one
        self.setStyleSheet("%s #%s { font-size: %dpx; }"
                           % (self.baseStyle, self.objectName(), size))
        logger.info("fit %s: %dpx for %r in %dpx",
                    self.objectName(), size, shown, room)


class Words():
    """the language table, as something a format string can reach into.

    {language.sunrise} asks the same question as piclock.language('sunrise')
    and gets the same answer - including the same fallback for a word no
    table has - so the two ways of asking cannot drift apart.
    """

    def __init__(self, piclock):
        self.piclock = piclock

    def __getattr__(self, name):
        return self.piclock.language(name)


class PiClock3(QWidget):
    config = DottedDict()
    pages = DottedDict()
    # a plain dict: region names contain dots (maps.1) and DottedDict would
    # read those as a path
    regions = {}
    # intrinsic size of each frame image, so the inset can be derived
    artSizes = {}
    # which theme each region was built with, so a widget in it can be told
    regionTheme = {}
    styles = DottedDict()
    plugins = DottedDict()
    pluginData = DottedDict()
    slideshows = []

    regionName = 'PiClock3'
    net = QtNetwork.QNetworkAccessManager()

    offset = datetime.timedelta()

    def __init__(self, config):
        self.config = config
        super().__init__()
        # before anything asks the time
        self.offset = self.startAt()
        self.screen = self.screenGeometry()
        logging.info("%s" % self.screen)
        # fontScale is per region; a region keeps the one it was built under
        self.pageRatio = 1.0
        self.designAspect = None
        self.fontScale = 1.0
        self.units = Units(self)
        self.units.load()
        self.languages = Languages(self)
        self.languages.load()
        self.setLocale()
        self.words = self.languages.strings()
        self.config['language'] = Words(self)
        self.initData()
        self.initWidgets()
        if self.config.get('geometry'):
            self.setGeometry(self.screen)
            self.show()
        else:
            self.showFullScreen()
        self.nextPage(0)
        logging.info("Startup Finished.")

    def screenGeometry(self):
        """the rectangle the clock lays itself out in.

        geometry: is how a clock drawn for a screen you do not have in front
        of you can be looked at on the one you do - every size in a layout or
        a theme is a fraction of this, so what comes out is what that screen
        would show rather than a scaled picture of it.
        """
        want = self.config.get('geometry')
        if not want:
            return QApplication.desktop().screenGeometry()
        size = re.match(r'^\s*(\d+)\s*[xX,]\s*(\d+)'
                        r'(?:\s*\+\s*(\d+)\s*\+\s*(\d+))?\s*$', str(want))
        if not size:
            raise SystemExit(
                "geometry wants WIDTHxHEIGHT, or WIDTHxHEIGHT+X+Y: %r" % want)
        w, h, x, y = size.groups()
        return QRect(int(x or 0), int(y or 0), int(w), int(h))

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_F4:
            logging.info("F4 Quit")
            self.close()
        if event.key() == Qt.Key_Space:
            self.nextPage(1)
        # F6, F7 and F8 are the keys PiClock v1 used for these
        show = self.showing()
        if show is None:
            return
        if event.key() == Qt.Key_F6:
            show.step(-1)
        if event.key() == Qt.Key_F7:
            show.step(1)
        if event.key() == Qt.Key_F8:
            logging.info('slideshow %s', 'held' if show.hold() else 'running')

    def showing(self):
        """the slideshow on the page being looked at, if there is one"""
        for show in self.slideshows:
            if show.isVisible():
                return show
        return None

    def mousePressEvent(self, event):
        return

    def initData(self):
        styles = self.config.styles if 'styles' in self.config else {}
        for style in styles:
            styleString = self._buildStyleString(styles[style])
            logging.debug('styleString: ' + style + '>' + styleString)
            self.styles[style] = styleString

    def initWidgets(self):
        self._requireLayoutConfig()
        unsortedPages = []
        for pageName in self.config.pages:
            page = self.config.pages[pageName]
            layout = self._loadPart('layouts', page['layout'])
            self.config._merge(self.config.get('layout') or {}, layout)
            theme = self._loadPart('themes', page['theme'])
            # theme: and layout: blocks in the config have the last word
            # over the files they name, which is what makes either testable
            # from the command line without editing it.  Named for what they
            # change rather than -settings: they are not keyed by a target
            # the way kind-settings and plugin-settings are.
            self.config._merge(self.config.get('theme') or {}, theme)
            theme['styles'] = self.regionStyles(layout, theme)
            self.pageRatio = self.aspectScale(layout)
            logging.debug("Building Page %s: layout %s, theme %s",
                          pageName, page['layout'], page['theme'])
            logging.info("page %s: layout %s designed for %s, screen %.3f,"
                         " ratio %.3f", pageName, page['layout'],
                         layout.get('designed-for', 'any shape'),
                         self.screen.width() / self.screen.height(),
                         self.pageRatio)

            pageFrame = QFrame(self)
            pageFrame.setVisible(False)
            pageFrame.setObjectName(pageName)
            pageFrame.setGeometry(
                0, 0, self.screen.width(), self.screen.height())
            if 'default' in theme:
                pageFrame.setStyleSheet(self._buildStyleString(
                    self.scaleFont(theme['default'], self.screen.height())))
            pageFrame.order = page['order'] if 'order' in page else 0
            pageFrame.regionName = pageName
            self.pages[pageName] = pageFrame
            unsortedPages.append(pageFrame)

            if 'background' in theme:
                self._buildBackground(pageFrame, pageName, theme['background'])

            for name in layout.get('regions', {}):
                self._buildRegion(pageFrame, name,
                                  layout['regions'][name], theme)

        sortedPages = sorted(unsortedPages, key=lambda x: x.order)
        for i in range(len(sortedPages)):
            pageFrame = sortedPages[i]
            if i == 0:
                pageFrame.setVisible(True)
            pageFrame.pageNumber = i

        # providers first: a widget names the providers it draws with, and
        # they have to exist by the time it does
        for section in ('providers', 'widgets'):
            if section not in self.config:
                continue
            for name in self.config[section]:
                self.loadModule(name, self.config[section][name])

    def _buildBackground(self, pageFrame, pageName, spec):
        """one picture behind a page, or a folder of them"""
        name = self.qtName(pageName) + '-background'
        if isinstance(spec, dict):
            resolved = dict(spec)
            if 'folder' in resolved:
                resolved['folder'] = self.expand(str(resolved['folder']))
            elif 'files' in resolved:
                resolved['files'] = [self.expand(str(f))
                                     for f in resolved['files']]
            else:
                raise SystemExit(
                    "\nthe background of page '%s' names neither a folder:"
                    " nor files:.\n" % pageName)
            self.slideshows.append(Slideshow(pageFrame, resolved, name))
            return
        bg = QLabel(pageFrame)
        bg.setObjectName(name)
        bg.setGeometry(0, 0, self.screen.width(), self.screen.height())
        bg.setStyleSheet(
            "#%s { border-image: url(%s) 0 0 0 0 stretch stretch; }"
            % (name, self.expand(spec)))

    def regionStyles(self, layout, theme):
        """the named styles a region can ask for, layout first then theme.

        A layout knows how big its text has to be to fit; a theme knows what
        it should look like.  So a layout carries the sizing as a default and
        a theme overrides whatever it cares to, which is what lets a layout
        nobody has themed still look right.
        """
        styles = {}
        self.config._merge(layout.get('layout-style-settings') or {}, styles)
        self.config._merge(theme.get('styles') or {}, styles)
        wanted = {r['style'] for r in (layout.get('regions') or {}).values()
                  if isinstance(r, dict) and 'style' in r}
        for name in sorted(wanted - set(styles)):
            logger.warning('layout asks for style %r and nothing defines it',
                           name)
        return styles

    def _requireLayoutConfig(self):
        if 'plugins' in self.config:
            raise SystemExit(
                "\nConfig.yaml still has a plugins: section.\n\n"
                "Instances are now split into providers: and widgets:, and\n"
                "each one names its plugin rather than including its file:\n\n"
                "  widgets:\n"
                "    radar1: {plugin: PiClock3.MapLoop, region: maps.1}\n\n"
                "Start again from examples/default.yaml rather than converting\n"
                "this one.  See\n"
                "BREAKING-CONFIGURATION-CHANGE-2026-08-23.md.\n")
        for pageName in self.config.pages:
            page = self.config.pages[pageName]
            if 'blocks' in page or 'layout' not in page:
                raise SystemExit(
                    "\n%s is in the old configuration format.\n\n"
                    "Pages used to include a tree of blocks mixing geometry\n"
                    "and styling.  They now name a layout and a theme:\n\n"
                    "  pages:\n"
                    "    clock-page: {order: 0, layout: classic, theme: circuit}\n\n"
                    "Start again from examples/default.yaml rather than\n"
                    "converting this one.  See\n"
                    "BREAKING-CONFIGURATION-CHANGE-2026-08-23.md.\n"
                    % pageName)

    def _loadPart(self, kind, name):
        """a layout or a theme - the user's own first, then the shipped one

        either a file or a folder will do.  a folder is what a git checkout
        of somebody else's theme looks like, so themes/mine.yaml and
        themes/mine/theme.yaml both work, and so does the repository naming
        its file after itself.
        """
        stem = 'theme' if kind == 'themes' else 'layout'
        for base in (kind, os.path.join('PiClock3', kind)):
            folder = os.path.join(base, name)
            for path, home in ((os.path.join(base, name + '.yaml'), None),
                               (os.path.join(folder, stem + '.yaml'), folder),
                               (os.path.join(folder, name + '.yaml'), folder)):
                if not os.path.isfile(path):
                    continue
                with open(path, encoding='utf-8') as fh:
                    part = yaml.safe_load(fh)
                logging.debug('%s %s from %s', stem, name, path)
                # localArt leaves a {placeholder} alone, so it has to run
                # before the placeholder becomes a path
                part = self.localArt(part, home) if home else part
                return thisFolder(part, os.path.dirname(path))
        raise SystemExit(
            "no %s named '%s'.  looked for %s.yaml, %s/%s.yaml and "
            "%s/%s.yaml, in %s/ and in PiClock3/%s/\n"
            % (stem, name, name, name, stem, name, name, kind, kind))

    @staticmethod
    def localArt(part, home):
        """point a folder's own art at that folder.

        a theme that ships its own images should not have to know where it
        was installed, so inside a folder a plain relative path is relative
        to the folder.  a path with a {placeholder} is left alone: that is
        how the shipped themes reach the common image directory.
        """
        keys = ('art', 'background', 'folder', 'files', 'image')
        if isinstance(part, list):
            for v in part:
                PiClock3.localArt(v, home)
        elif isinstance(part, dict):
            for k, v in part.items():
                if k in keys and isinstance(v, list):
                    part[k] = [PiClock3.localPath(x, home) for x in v]
                elif isinstance(v, (dict, list)):
                    PiClock3.localArt(v, home)
                elif k in keys:
                    part[k] = PiClock3.localPath(v, home)
        return part

    @staticmethod
    def localPath(value, home):
        """one relative path, made relative to the folder it came in"""
        if (isinstance(value, str) and '{' not in value
                and not os.path.isabs(value)):
            return (home + '/' + value).replace(os.sep, '/')
        return value

    def _regionRect(self, pw, ph, r, widen=False):
        # both edges and no size: whatever lies between them
        edges = 'width' not in r and 'left' in r and 'right' in r
        leftf, rightf = r.get('left', 0.0), r.get('right', 0.0)
        if edges:
            if widen:
                leftf = leftf / self.pageRatio
                rightf = rightf / self.pageRatio
            width = pw * max(0.0, 1.0 - leftf - rightf)
        else:
            width = pw * r['width'] if 'width' in r else pw
        height = ph * r['height'] if 'height' in r else ph
        # width only: a region grown downward would cover the one under it.
        # Not a plugin's parts - their region was corrected already.
        if (widen and not edges and 'width' in r and 'height' in r
                and 'aspect' not in r):
            # all of it or none: half is the wrong shape and costs a margin
            want = width / self.pageRatio
            room = pw
            if 'left' in r:
                room = pw - pw * r['left']
            elif 'right' in r:
                room = pw - pw * r['right']
            if want <= room:
                width = want
        if 'aspect' in r:
            if 'width' in r:
                height = width * r['aspect']
            else:
                width = height * r['aspect']
        left = top = 0
        if 'horizontal-center' in r:
            left = pw / 2.0 + pw * r['horizontal-center'] - width / 2.0
        if 'vertical-center' in r:
            top = ph / 2.0 + ph * r['vertical-center'] - height / 2.0
        if 'left' in r:
            left = pw * leftf
        if 'top' in r:
            top = ph * r['top']
        if 'right' in r:
            left = pw - pw * rightf - width
        if 'bottom' in r:
            top = ph - ph * r['bottom'] - height
        # a side past an edge is held at it
        if left < 0:
            width += left
            left = 0
        if left + width > pw:
            width = pw - left
        if top < 0:
            height += top
            top = 0
        if top + height > ph:
            height = ph - top
        return QRect(int(left), int(top), int(width), int(height))

    @staticmethod
    def qtName(name):
        """object names reach Qt stylesheets as #selectors, and a dot there
        means a class - so maps.1 has to become maps_1"""
        return name.replace('.', '_')

    def scaleFont(self, props, height, region=None):
        """a bare number font-size is a fraction of the height it sits in.

        The region says which layout it came from: a plugin sizes its text
        long after the page holding it was built.
        """
        scale = (self.fontScale if region is None
                 else getattr(region, 'fontScale', self.fontScale))
        props = dict(props)
        fs = props.get('font-size')
        if fs is not None:
            t = str(fs)
            if t.replace('.', '', 1).isdigit():
                if float(t) == 0.0:
                    del props['font-size']          # fit, once it has text
                else:
                    props['font-size'] = "%dpx" % (float(t) * height * scale)
        return props

    @staticmethod
    def readAspect(spec):
        """a screen shape, as '16:9' or as the number that means"""
        t = str(spec)
        if ':' in t:
            w, h = t.split(':', 1)
            return float(w) / float(h)
        value = float(t)
        # yaml reads a bare 16:9 as sexagesimal - 969.  No screen is that
        # shape, so take it back apart.
        if value > 60 and value == int(value) and int(value) % 60:
            logger.warning("designed-for: %s is being read as a number - quote"
                           " it as '%d:%d'", t, int(value) // 60,
                           int(value) % 60)
            return (int(value) // 60) / float(int(value) % 60)
        return value

    def aspectScale(self, layout):
        """the screen's shape over the one the layout was designed for.

        A layout that says nothing is left alone: guessing would reshape one
        designed for 4:3 on the screen it was designed for.
        """
        spec = layout.get('designed-for')
        self.designAspect = None if spec is None else self.readAspect(spec)
        if self.designAspect is None:
            return 1.0
        actual = self.screen.width() / self.screen.height()
        return actual / self.designAspect

    def regionFontScale(self, r, rect):
        """text is a fraction of a region's height but has to fit across its
        width, so a region that came out a different shape needs it smaller.
        One that kept its shape does not."""
        if not self.designAspect or 'width' not in r or 'height' not in r:
            return 1.0
        designed = (r['width'] / r['height']) * self.designAspect
        return min(1.0, (rect.width() / rect.height()) / designed)

    def _regionStyle(self, name, region, theme, rect):
        """styling that belongs on the region itself - not the frame"""
        if 'style' not in region:
            return ''
        props = self.scaleFont(
            theme.get('styles', {}).get(region['style'], {}), rect.height())
        props.pop('fit', None)          # ours to act on, not a Qt property
        style = self._buildStyleString(props)
        return "#%s { %s }" % (self.qtName(name), style) if style else ''

    def _borderFor(self, region, theme):
        """the theme's border entry for a region, or None"""
        if not region.get('border'):
            return None
        borders = theme.get('borders', {})
        which = region['border']
        return borders.get('default' if which is True else which,
                           borders.get('default'))

    def artSize(self, path):
        if path not in self.artSizes:
            img = QImage(path)
            self.artSizes[path] = None if img.isNull() else img.size()
            if img.isNull():
                logging.warning('frame art %s will not load', path)
        return self.artSizes[path]

    def borderWidth(self, border, screenHeight):
        """frame weight in pixels.

        a fraction of screen height, so a frame is the same weight on a
        small box as on a big one, and the same at 800x600 as at 1920x1080.
        """
        return max(1, int(round(float(border.get('width', 0.012))
                                * screenHeight)))

    def borderPull(self, border, bw):
        """how far content reaches back into the frame.

        the shipped art is a glowing tube - its alpha fades symmetrically
        either side of the line, so unlike a drop-off edge it names no
        boundary for content to sit against.  inset says where to put one,
        as a fraction of the frame's width: 1.0 leaves the whole glow clear
        of the content, 0.5 brings content up to the middle of the line so
        the inner half of the glow falls across it.

        content is never pulled past the middle, or two cells sharing a
        rule would overlap each other.
        """
        f = float(border.get('inset', 0.5))
        return min(bw // 2, max(0, int(round(bw * (1.0 - f)))))

    def borderStyle(self, qt, border, screenHeight, edges=None):
        """a nine-slice frame painted in the widget's own border.

        the art is a 3x3 sheet, so the slice is a third of it - the art
        describes its own geometry and a theme cannot disagree with it.
        qt insets contentsRect by the border, so content cannot cover the
        frame and nothing here has to work that out.

        edges limits which sides are drawn.  one edge on its own draws no
        corner art, which is what a divider between cells needs: a corner
        is where a line ends, and an internal join is where it must not.
        """
        art = self.expand(border['art'])
        size = self.artSize(art)
        if size is None or size.isEmpty():
            return ''
        # a third of the sheet each way, so the cells need not be square
        cw, ch = size.width() // 3, size.height() // 3
        bw = self.borderWidth(border, screenHeight)
        style = ("border-image: url(%s) %d %d %d %d stretch stretch;"
                 % (art, ch, cw, ch, cw))
        if edges is None:
            style += " border-width: %dpx;" % bw
        else:
            style += " border-width: 0px;"
            for e in edges:
                style += " border-%s-width: %dpx;" % (e, bw)
        return "#%s { %s }" % (qt, style)

    def _buildRegion(self, parent, name, region, theme):
        rect = self._regionRect(parent.width(), parent.height(), region,
                                widen=True)
        self.fontScale = self.regionFontScale(region, rect)
        rep = region.get('repeat')
        border = self._borderFor(region, theme)

        if not border:
            if not rep:
                self._makeRegion(parent, name, rect, region, theme)
                return
            for i, cell in enumerate(self._cellRects(rect, rep, 0)):
                self._makeRegion(parent, '%s.%d' % (name, i + 1), cell,
                                 region, theme)
            return

        # cells held apart are separate boxes, each framed on its own;
        # only cells that butt together share a frame with a rule between
        if rep and self._repeatPad(rect, rep):
            for i, cell in enumerate(self._cellRects(rect, rep, 0)):
                self._framedBox(parent, '%s.%d' % (name, i + 1), cell,
                                region, theme, border)
            return

        # the frame goes on top of the content, so the glow falls across it
        # the way a light does.  content under the frame would cut the tube
        # in half and make a fading edge look like a drop-off one.
        container = QWidget(parent)
        container.setObjectName(self.qtName(name) + '-group')
        container.setGeometry(rect)

        bw = self.borderWidth(border, parent.height())
        pull = self.borderPull(border, bw)
        area = QRect(bw, bw, rect.width() - bw * 2, rect.height() - bw * 2)

        cells = ([area] if not rep
                 else self._cellRects(area, rep, bw))
        for i, cell in enumerate(cells):
            cname = name if not rep else '%s.%d' % (name, i + 1)
            self._makeRegion(container, cname,
                             cell.adjusted(-pull, -pull, pull, pull),
                             region, theme)

        # added after the cells, so they paint over them
        qt = self.qtName(name) + '-frame'
        frame = QLabel(container)
        frame.setObjectName(qt)
        frame.setGeometry(0, 0, rect.width(), rect.height())
        frame.setStyleSheet(self.borderStyle(qt, border, parent.height()))

        if rep:
            across = rep.get('direction') == 'across'
            pad = self._repeatPad(area, rep)
            for i, cell in enumerate(cells):
                if i:
                    self._makeDivider(container, '%s.%d-rule' % (name, i + 1),
                                      border, cell, across, bw, pad,
                                      parent.height())

    def _framedBox(self, parent, name, rect, region, theme, border):
        """one region inside a frame of its own"""
        container = QWidget(parent)
        container.setObjectName(self.qtName(name) + '-group')
        container.setGeometry(rect)

        bw = self.borderWidth(border, parent.height())
        pull = self.borderPull(border, bw)
        area = QRect(bw, bw, rect.width() - bw * 2, rect.height() - bw * 2)
        self._makeRegion(container, name,
                         area.adjusted(-pull, -pull, pull, pull), region, theme)

        qt = self.qtName(name) + '-frame'
        frame = QLabel(container)
        frame.setObjectName(qt)
        frame.setGeometry(0, 0, rect.width(), rect.height())
        frame.setStyleSheet(self.borderStyle(qt, border, parent.height()))

    def _repeatPad(self, area, rep):
        across = rep.get('direction') == 'across'
        span = area.width() if across else area.height()
        return int(span * rep.get('gap', 0))

    def _cellRects(self, area, rep, bw):
        """the content boxes of a repeat, with room between them for a rule"""
        count = rep.get('count', 1)
        across = rep.get('direction') == 'across'
        span = area.width() if across else area.height()
        pad = int(span * rep.get('gap', 0))
        splits = count - 1
        cellspan = (span - (bw + pad) * splits) / float(count)
        out = []
        for i in range(count):
            a = int(round(i * (cellspan + bw + pad)))
            b = int(round(a + cellspan))
            if across:
                out.append(QRect(area.x() + a, area.y(), b - a, area.height()))
            else:
                out.append(QRect(area.x(), area.y() + a, area.width(), b - a))
        return out

    def _makeDivider(self, host, name, border, cell, across, bw, pad,
                     screenHeight):
        """the straight rule between two cells of a repeat"""
        qt = self.qtName(name)
        d = QLabel(host)
        d.setObjectName(qt)
        # the rule runs to the middle of the side it meets - far enough to
        # cross the side's glow so the T does not break, not so far that it
        # reaches the outer edge and juts out past the box.
        half = bw // 2
        if across:
            d.setGeometry(cell.x() - bw - pad + pad // 2, half,
                          bw, host.height() - half * 2)
            edge = 'left'
        else:
            d.setGeometry(half, cell.y() - bw - pad + pad // 2,
                          host.width() - half * 2, bw)
            edge = 'top'
        d.setStyleSheet(
            self.borderStyle(qt, border, screenHeight, (edge,)))

    def _makeRegion(self, parent, name, rect, region, theme):
        qt = self.qtName(name)
        w = FitLabel(parent)
        w.setObjectName(qt)
        w.setGeometry(rect)
        spec = theme.get('styles', {}).get(region.get('style'), {}) or {}
        size = str(spec.get('font-size', '')).strip()
        if size == '0':
            # nothing but the box constrains it
            w.fitCeiling = int(rect.height() * 0.8)
        elif spec.get('fit') and size.replace('.', '', 1).isdigit():
            # the size the layout asked for, and never larger
            w.fitCeiling = int(float(size) * rect.height() * self.fontScale)

        style = self._regionStyle(name, region, theme, rect)
        w.baseStyle = style or ''
        if style:
            w.setStyleSheet(style)

        w.regionName = name
        w.fontScale = self.fontScale
        if name in self.regions:
            logging.warning('region %s is defined by more than one layout in '
                            'use - the later page wins', name)
        self.regions[name] = w
        self.regionTheme[name] = theme
        logging.debug("Region %s %s", name, rect)

    def pluginConfig(self, mod, entry):
        """the plugin's own defaults with this instance merged over them.

        the defaults live beside the plugin's code, so they are found from
        the imported module rather than from a path anybody has to write
        down - which is what makes a third-party plugin work the moment it
        is cloned into plugins/.
        """
        config = DottedDict()
        defaults = {}
        path = os.path.join(os.path.dirname(os.path.abspath(mod.__file__)),
                            'config.yaml')
        if os.path.isfile(path):
            with open(path, encoding='utf-8') as fh:
                defaults = yaml.safe_load(fh) or {}
            defaults = thisFolder(defaults, os.path.dirname(path))
            self.config._merge(defaults, config)

        # the theme of the page this instance draws on, if it draws at all.
        # a provider occupies no region, so no theme reaches it - which is
        # why anything a theme should be able to say belongs on a widget.
        theme = self.instanceTheme(entry)
        if theme:
            self.cascade(theme, defaults, config)
            self.settingsFor(theme, defaults, entry, config)

        # the config has the same two blocks and the last word over the theme
        self.settingsFor(self.config, defaults, entry, config)
        self.config._merge(entry, config)
        return config

    # Qt's own property names, which mean here what they mean in Qt.  A
    # widget declaring one is asking for the page's answer to it.
    CASCADE = ('color', 'background-color', 'font-family', 'font-style',
               'font-weight')

    def cascade(self, theme, defaults, config):
        """the theme's default: reaching every widget that takes the name.

        font-size is deliberately not among them.  It is a fraction of
        whatever it sits in, and a page and a region are not the same
        height - the page's 0.02 would draw a clock face at four pixels.
        """
        page = theme.get('default') or {}
        for name in self.CASCADE:
            if name in page and name in defaults:
                config[name] = page[name]

    def settingsFor(self, source, defaults, entry, config):
        """kind-settings: then plugin-settings:, from a theme or the config.

        A kind is what a plugin is interchangeable with, so a kind-setting
        means the same thing to every plugin wearing it.  plugin-settings:
        names one exactly, for the times that is too broad.
        """
        for block, key in (('kind-settings', defaults.get('kind')),
                           ('plugin-settings', entry.get('plugin'))):
            settings = source.get(block)
            if isinstance(settings, dict) and isinstance(settings.get(key), dict):
                self.config._merge(settings[key], config)

    def instanceTheme(self, entry):
        """the theme of the page an instance draws on"""
        name = entry.get('region')
        if isinstance(name, list):
            name = name[0] if name else None
        if not name:
            return None
        if name in self.regionTheme:
            return self.regionTheme[name]
        head = name + '.'                      # a repeat: its cells share a page
        for key in self.regionTheme:
            if key.startswith(head):
                return self.regionTheme[key]
        return None

    def regionList(self, name):
        """every region a widget's region: refers to, in order.

        a plain name is one region.  the name of a repeat gathers its cells,
        which is unambiguous because a repeat registers only name.1 .. name.N
        and never the bare name.  a list names them explicitly.
        """
        if isinstance(name, list):
            missing = [n for n in name if n not in self.regions]
            if missing:
                raise SystemExit("no region named %s\n" % ", ".join(missing))
            return [self.regions[n] for n in name]

        if name in self.regions:
            return [self.regions[name]]

        head = name + '.'
        cells = [k for k in self.regions
                 if k.startswith(head) and k[len(head):].isdigit()]
        if cells:
            return [self.regions[k]
                    for k in sorted(cells, key=lambda k: int(k.split('.')[-1]))]

        raise SystemExit(
            "no region or repeat named '%s'.  the layout defines: %s\n"
            % (name, ', '.join(sorted(self.regions)) or 'nothing'))

    # The Qt names that genuinely inherit, and so can be handed to a region
    # for whatever a plugin draws inside it.
    #
    # background-color is deliberately not among them.  CSS does not inherit
    # it, and broadcasting it would paint a box behind every child - the
    # analog face among them, which is a border-image that expects to see
    # through.  A widget that wants a background sets its own.
    #
    # font-size is not among them either, for the reason it is not in
    # CASCADE: it is a fraction of whatever it sits in, and a region and a
    # label inside that region are not the same height.
    INHERITED = ('color', 'font-family', 'font-style', 'font-weight')

    def broadcast(self, entry, config):
        """a widget's resolved settings, onto its region, for its children.

        A theme's default: reaches everything because core hands it to the
        page frame and Qt carries it down.  A kind-setting had no such road:
        it was merged into the plugin's config and then did nothing unless
        that plugin happened to have written a line reading that key - which
        is why kind-settings font-weight moved nothing for most widgets.

        This is the page's trick one level in.  Whatever resolved for this
        instance is put on its region, and Qt carries it to whatever the
        plugin draws there.  A widget that names a value itself still wins,
        because an id selector outranks a type selector - so this reaches
        only what nobody else answered.

        QWidget { } rather than a bare list of properties: a stylesheet
        holding both bare properties and a rule loses the bare half, and
        loses it silently.
        """
        if not entry.get('region'):
            return                      # a provider draws nothing
        props = {n: self.expand(config[n]) for n in self.INHERITED
                 if config.get(n) is not None}
        if not props:
            return
        rule = 'QWidget {%s }' % self._buildStyleString(props)
        for region in self.regionList(entry['region']):
            region.setStyleSheet(rule + ' ' + region.styleSheet())
        logger.debug('region style for %s: %s', entry.get('region'), rule)

    def loadModule(self, name, entry):
        if 'plugin' not in entry:
            raise SystemExit("%s does not say which plugin it is.  Add"
                             " plugin: <module>\n" % name)
        mod = importlib.import_module(entry['plugin'])
        moduleConfig = self.pluginConfig(mod, entry)
        self.broadcast(entry, moduleConfig)
        logging.info('loading %s %s', mod, name)
        self.pluginData[name] = DottedDict()
        cls = None
        clsName = ''
        for cname, obj in inspect.getmembers(mod, inspect.isclass):
            # defined here, not imported.  A plugin that imports a base class
            # to subclass it puts a second Plugin subclass in this namespace,
            # and picking by "most derived" cannot tell the two apart when
            # neither descends from the other.  `plugin:` names the package,
            # so the class arrives from a module inside it rather than from
            # the package itself
            if not (obj.__module__ == mod.__name__
                    or obj.__module__.startswith(mod.__name__ + '.')):
                continue
            if not issubclass(obj, Plugin) or obj is Plugin:
                continue
            if cls is not None and issubclass(cls, obj):
                continue
            cls = obj
            clsName = cname
        if cls is None:
            raise TypeError('%s defines no Plugin subclass' % entry['plugin'])
        logger.debug('found %s %s', cls, clsName)
        instance = cls(self, name, moduleConfig)
        self.plugins[name] = instance
        # effect: on the region, before start() draws anything into it.  An
        # effect covers a widget's whole subtree and picks up children added
        # later, so this reaches whatever the plugin goes on to make without
        # the plugin knowing an effect exists.
        for region in getattr(instance, 'regions', None) or []:
            instance.applyEffect(region, region.height())
        instance.start()

    def nextPage(self, n):
        current = -1
        count = 0
        for pageName in self.pages:
            page = self.pages[pageName]
            count += 1
            if page.isVisible():
                current = page.pageNumber
                logging.debug("Setting page %s (%s) to invisible"
                              % (page.pageNumber, pageName))
                page.setVisible(False)
        logging.debug("Current %s Max %s" % (current, count))
        current = (current + n) % count
        logging.debug("new Current %s" % current)
        for pageName in self.pages:
            page = self.pages[pageName]
            if page.pageNumber == current:
                logging.debug("Setting page %s (%s) to visible"
                             % (current, pageName))
                page.setVisible(True)
        for show in self.slideshows:
            show.pageChange()
        for pluginName in self.plugins:
            plugin = self.plugins[pluginName]
            plugin.pageChange()
            logger.debug("call pageChange %s", pluginName)
            region = getattr(plugin, 'region', None)
            if region is not None:
                logger.debug(' plugin region visible: %s', region.isVisible())

    def _buildStyleString(self, style):
        styleString = ''
        for element in style:
            styleString += ' ' + element + ': ' + str(style[element]) + ';'
        return styleString

    def timezone(self):
        """the zone of the location: this clock is pointed at.

        Blank means the machine's own, which is right for a clock standing
        where it is pointed.
        """
        raw = None
        if 'location' in self.config and 'timezone' in self.config.location:
            raw = self.config.location.timezone
        name = raw.strip() if isinstance(raw, str) else ''
        if name:
            try:
                return zoneinfo.ZoneInfo(name)
            except Exception as e:
                logger.warning("timezone %r unknown, using this machine's: %s",
                               name, e)
        return zoneinfo.ZoneInfo(tzlocal.get_localzone_name())

    def now(self):
        """the current time where the clock is pointed.

        start-at: in the config shifts this, and only this.  The radar asks
        the wall clock directly, because a frame server has what it has
        whatever the clock believes - so a clock set to midwinter shows
        midwinter's sun and this afternoon's rain.
        """
        return datetime.datetime.now(self.timezone()) + self.offset

    def startAt(self):
        """how far off the real time the config asked to be.

        An offset rather than a fixed moment, so the clock still ticks: set
        it to a polar night and the seconds still run.
        """
        wanted = self.config.get('start-at')
        if not wanted:
            return datetime.timedelta()
        try:
            when = datetime.datetime.fromisoformat(str(wanted))
        except ValueError:
            raise SystemExit(
                "\nstart-at: %r is not a date and time.  Write it as"
                " 2026-06-21 or 2026-06-21 13:45.\n" % wanted)
        if when.tzinfo is None:
            when = when.replace(tzinfo=self.timezone())
        off = when - datetime.datetime.now(self.timezone())
        logger.warning('start-at %s: the clock is running %s from now',
                       when, off)
        return off

    def localtime(self, stamp):
        """a unix timestamp as a time where the clock is pointed"""
        return datetime.datetime.fromtimestamp(stamp, self.timezone())

    def language(self, s):
        """a word in the language this clock is set to.

        An unknown key becomes itself, spaced and capitalized, so a plugin
        that says something no table has yet still reads as words.
        """
        s = s.replace(' ', '_').lower()
        if s in self.words:
            return self.words[s]
        return s.replace('_', ' ').title()

    def setLocale(self):
        """LC_TIME, so strftime names the days and months in this language.

        Set here, before any widget starts, because the widgets that draw
        dates do so on network callbacks and cannot be ordered.

        A locale is spelled differently on each platform, and on glibc it
        also has to have been generated, so the language file offers several
        and the first that takes is the one used.  A config's own locale:
        overrides all of them.
        """
        wanted = self.config.get('locale')
        names = [wanted] if wanted else self.languages.locales()
        for name in names:
            try:
                locale.setlocale(locale.LC_TIME, name)
                logger.info('locale %s', name)
                return name
            except locale.Error:
                continue
        if names:
            logger.warning(
                'none of these locales is installed: %s - day and month names'
                ' will be the system default', ', '.join(str(n) for n in names))
        return None

    def condition(self, notation):
        """words for a WMO 4678 weather notation, or a METAR sky cover.

        Providers hand out notation rather than sentences so that what the
        sky is doing and what to call it stay separate concerns.
        """
        return self.languages.condition(notation)

    def expand(self, s):
        self.config['plugin-folder'] = os.path.dirname(
            os.path.relpath(inspect.stack()[1][1])).replace('\\', '/')
        inst = inspect.stack()[1][0].f_locals['self']
        if hasattr(inst, 'name'):
            if inst.name in self.pluginData:
                self.config['plugin-data'] = self.pluginData[inst.name]
            else:
                self.config['plugin-data'] = DottedDict()
        return self.config.expand(s)


class LogHandler(logging.handlers.RotatingFileHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.doRollover()
