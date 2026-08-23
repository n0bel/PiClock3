import importlib
import inspect
import logging
import logging.handlers
import os

import yaml

from PyQt5 import (QtNetwork)
from PyQt5.QtCore import (Qt, QRect,
                          QSize)
from PyQt5.QtWidgets import (QWidget, QLabel, QApplication, QFrame)

from .DottedDict import DottedDict
from .Plugin import Plugin

logger = logging.getLogger(__name__)


class PiClock3(QWidget):
    config = DottedDict()
    pages = DottedDict()
    # a plain dict: region names contain dots (maps.1) and DottedDict would
    # read those as a path
    blocks = {}
    styles = DottedDict()
    plugins = DottedDict()
    pluginData = DottedDict()

    blockName = 'PiClock3'
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
                pageFrame.setStyleSheet(self._buildStyleString(theme['default']))
            pageFrame.order = page['order'] if 'order' in page else 0
            pageFrame.blockName = pageName
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
            self.pages[pageFrame.blockName] = pageFrame

        for module in self.config.plugins:
            self.loadModule(module, self.config.plugins[module])

    def _requireLayoutConfig(self):
        for pageName in self.config.pages:
            page = self.config.pages[pageName]
            if 'blocks' in page or 'layout' not in page:
                raise SystemExit(
                    "\n%s is in the old configuration format.\n\n"
                    "Pages used to include a tree of blocks mixing geometry\n"
                    "and styling.  They now name a layout and a theme:\n\n"
                    "  pages:\n"
                    "    clock-page: {order: 0, layout: classic, theme: kevin}\n\n"
                    "Block names changed with it, so every plugin's block:\n"
                    "needs updating too.  See MIGRATION.md.\n" % pageName)

    def _loadPart(self, kind, name):
        """a layout or a theme - the user's own first, then the shipped one"""
        for base in (kind, os.path.join('PiClock3', kind)):
            path = os.path.join(base, name + '.yaml')
            if os.path.isfile(path):
                with open(path, encoding='utf-8') as fh:
                    return yaml.safe_load(fh)
        raise SystemExit("no %s named '%s' in %s/ or PiClock3/%s/"
                         % (kind[:-1], name, kind, kind))

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

    def _regionStyle(self, name, region, theme, rect):
        """styling that belongs on the region itself - not the frame"""
        if 'style' not in region:
            return ''
        props = dict(theme.get('styles', {}).get(region['style'], {}))
        # a bare number font-size is a fraction of the region height
        fs = props.get('font-size')
        if fs is not None:
            t = str(fs)
            if t.replace('.', '', 1).isdigit():
                props['font-size'] = "%dpx" % (float(t) * rect.height())
        style = self._buildStyleString(props)
        return "#%s { %s }" % (self.qtName(name), style) if style else ''

    def _borderFor(self, region, theme, position):
        if not region.get('border'):
            return None, None
        borders = theme.get('borders', {})
        which = region['border']
        b = borders.get('default' if which is True else which,
                        borders.get('default'))
        if not b:
            return None, None
        cut = b.get('slice', [0, 0, 0, 0])
        if position in b:
            cut = b[position]
        return b, [int(v) for v in cut]

    def _buildRegion(self, parent, name, region, theme):
        rect = self._regionRect(parent.width(), parent.height(), region)
        rep = region.get('repeat')
        if not rep:
            self._makeRegion(parent, name, rect, region, theme, None)
            return
        count = rep.get('count', 1)
        gap = rep.get('gap', 0)
        across = rep.get('direction') == 'across'
        span = rect.width() if across else rect.height()
        # the gap goes between cells, not after every one
        pad = int(span * gap)
        cellspan = (span - pad * (count - 1)) / float(count)
        for i in range(count):
            a = int(round(i * (cellspan + pad)))
            b = int(round(a + cellspan))
            if across:
                cell = QRect(rect.x() + a, rect.y(),
                             b - a, rect.height())
            else:
                cell = QRect(rect.x(), rect.y() + a,
                             rect.width(), b - a)
            pos = 'first' if i == 0 else ('last' if i == count - 1 else None)
            self._makeRegion(parent, '%s.%d' % (name, i + 1), cell,
                             region, theme, pos)

    def _makeRegion(self, parent, name, rect, region, theme, position):
        qt = self.qtName(name)
        outer = QLabel(parent)
        outer.setObjectName(qt)
        outer.setGeometry(rect)

        border, cut = self._borderFor(region, theme, position)
        target = outer
        if border:
            # the frame art is a picture stretched over the whole region, so it
            # has to sit on top of the content, not behind it.  the content
            # goes in an inner widget inset by the slice, and plugins bind to
            # that - which is what the old config spelled out by hand for every
            # bordered block.
            top, right, bottom, left = cut
            inner = QLabel(outer)
            inner.setObjectName(qt + '-content')
            inner.setGeometry(left, top,
                              rect.width() - left - right,
                              rect.height() - top - bottom)
            overlay = QLabel(outer)
            overlay.setObjectName(qt + '-border')
            overlay.setGeometry(0, 0, rect.width(), rect.height())
            overlay.setStyleSheet(
                "#%s-border { border-image: url(%s) %s; }"
                % (qt, self.expand(border['image']),
                   ' '.join(str(v) for v in cut)))
            target = inner

        style = self._regionStyle(name, region, theme, rect)
        if style:
            outer.setStyleSheet(style)
        target.blockName = name
        target.blockType = 'label'
        if name in self.blocks:
            logging.warning('region %s is defined by more than one layout in '
                            'use - the later page wins', name)
        self.blocks[name] = target
        logging.debug("Region %s %s%s", name, rect, ' framed' if border else '')

    def loadModule(self, name, moduleConfig):
        mod = importlib.import_module(moduleConfig.module)
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
            raise TypeError('%s defines no Plugin subclass' % moduleConfig.module)
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
            if hasattr(plugin, 'block'):
                block = getattr(plugin, 'block')
                if block != None:
                    logger.debug(" plugin block visible: %s", block.isVisible())            

    def _buildStyleString(self, style):
        styleString = ''
        for element in style:
            styleString += ' ' + element + ': ' + str(style[element]) + ';'
        return styleString

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
