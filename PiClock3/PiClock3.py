import datetime
import importlib
import inspect
import logging
import logging.handlers
import os
import zoneinfo

import tzlocal
import yaml

from PyQt5 import (QtNetwork)
from PyQt5.QtCore import (Qt, QRect,
                          QSize)
from PyQt5.QtGui import (QImage)
from PyQt5.QtWidgets import (QWidget, QLabel, QApplication, QFrame)

from .DottedDict import DottedDict
from .Plugin import Plugin

logger = logging.getLogger(__name__)


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

    regionName = 'PiClock3'
    net = QtNetwork.QNetworkAccessManager()

    def __init__(self, config):
        self.config = config
        super().__init__()
        self.screen = QApplication.desktop().screenGeometry()
        logging.info("%s" % self.screen)
        self.initData()
        self.initWidgets()
        self.showFullScreen()
        self.nextPage(0)
        logging.info("Startup Finished.")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_F4:
            logging.info("F4 Quit")
            self.close()
        if event.key() == Qt.Key_Space:
            self.nextPage(1)

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
            theme = self._loadPart('themes', page['theme'])
            logging.debug("Building Page %s: layout %s, theme %s",
                          pageName, page['layout'], page['theme'])

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
                bg = QLabel(pageFrame)
                bg.setObjectName(self.qtName(pageName) + '-background')
                bg.setGeometry(0, 0, self.screen.width(), self.screen.height())
                bg.setStyleSheet(
                    "#%s-background { border-image: url(%s) 0 0 0 0 "
                    "stretch stretch; }"
                    % (self.qtName(pageName), self.expand(theme['background'])))

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

    def _requireLayoutConfig(self):
        if 'plugins' in self.config:
            raise SystemExit(
                "\nConfig.yaml still has a plugins: section.\n\n"
                "Instances are now split into providers: and widgets:, and\n"
                "each one names its plugin rather than including its file:\n\n"
                "  widgets:\n"
                "    radar1: {plugin: PiClock3.MapLoop, region: maps.1}\n\n"
                "Start again from Config-Example.yaml rather than converting\n"
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
                    "Start again from Config-Example.yaml rather than\n"
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
                return self.localArt(part, home) if home else part
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
        keys = ('art', 'background', 'image')
        if isinstance(part, list):
            for v in part:
                PiClock3.localArt(v, home)
        elif isinstance(part, dict):
            for k, v in part.items():
                if isinstance(v, (dict, list)):
                    PiClock3.localArt(v, home)
                elif (k in keys and isinstance(v, str) and '{' not in v
                      and not os.path.isabs(v)):
                    part[k] = (home + '/' + v).replace(os.sep, '/')
        return part

    def _regionRect(self, pw, ph, r):
        width = pw * r['width'] if 'width' in r else pw
        height = ph * r['height'] if 'height' in r else ph
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
            left = pw * r['left']
        if 'top' in r:
            top = ph * r['top']
        if 'right' in r:
            left = pw - pw * r['right'] - width
        if 'bottom' in r:
            top = ph - ph * r['bottom'] - height
        return QRect(int(left), int(top), int(width), int(height))

    @staticmethod
    def qtName(name):
        """object names reach Qt stylesheets as #selectors, and a dot there
        means a class - so maps.1 has to become maps_1"""
        return name.replace('.', '_')

    @staticmethod
    def scaleFont(props, height):
        """a bare number font-size is a fraction of the height it sits in, so
        that nothing in a layout or theme is tied to a pixel count"""
        props = dict(props)
        fs = props.get('font-size')
        if fs is not None:
            t = str(fs)
            if t.replace('.', '', 1).isdigit():
                props['font-size'] = "%dpx" % (float(t) * height)
        return props

    def _regionStyle(self, name, region, theme, rect):
        """styling that belongs on the region itself - not the frame"""
        if 'style' not in region:
            return ''
        props = self.scaleFont(
            theme.get('styles', {}).get(region['style'], {}), rect.height())
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
        rect = self._regionRect(parent.width(), parent.height(), region)
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
        w = QLabel(parent)
        w.setObjectName(qt)
        w.setGeometry(rect)

        style = self._regionStyle(name, region, theme, rect)
        if style:
            w.setStyleSheet(style)

        w.regionName = name
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
            self.config._merge(defaults, config)

        # the theme of the page this instance draws on, if it draws at all.
        # a provider occupies no region, so no theme reaches it - which is
        # why anything a theme should be able to say belongs on a widget.
        theme = self.instanceTheme(entry)
        if theme:
            self.config._merge(self.themeAsks(defaults, theme), config)
            kind = defaults.get('kind')
            if isinstance(theme.get(kind), dict):
                self.config._merge(theme[kind], config)

        self.config._merge(entry, config)
        return config

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

    @staticmethod
    def themeAsks(defaults, theme):
        """the theme values a plugin said it wanted, under its own key names.

        A plugin declares the mapping itself, so the loader knows nothing
        about any particular plugin and a third-party one can ask for the
        same things:

            from-theme:
              clock-images-folder: clock-art
        """
        out = {}
        for mine, theirs in (defaults.get('from-theme') or {}).items():
            value = theme
            for part in str(theirs).split('.'):
                if not isinstance(value, dict) or part not in value:
                    value = None
                    break
                value = value[part]
            if value is not None:
                out[mine] = value
        return out

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

    def loadModule(self, name, entry):
        if 'plugin' not in entry:
            raise SystemExit("%s does not say which plugin it is.  Add"
                             " plugin: <module>\n" % name)
        mod = importlib.import_module(entry['plugin'])
        moduleConfig = self.pluginConfig(mod, entry)
        logging.info('loading %s %s', mod, name)
        self.pluginData[name] = DottedDict()
        cls = None
        clsName = ''
        for cname, obj in inspect.getmembers(mod, inspect.isclass):
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
        """the current time where the clock is pointed"""
        return datetime.datetime.now(self.timezone())

    def localtime(self, stamp):
        """a unix timestamp as a time where the clock is pointed"""
        return datetime.datetime.fromtimestamp(stamp, self.timezone())

    def language(self, s):
        s = s.replace(' ', '_').lower()
        if s in self.config.language:
            return self.config.language[s]
        else:
            return s.replace('_', ' ').title()

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
