import os
import sys
import time
import yaml
from yamlinclude import YamlIncludeConstructor
import logging
import logging.handlers
import queue
import datetime
import re
import importlib
import inspect
from .DottedDict import DottedDict
from .Config import Config
from .Plugin import Plugin

from PyQt5 import (QtGui, QtNetwork)
from PyQt5.QtCore import (QObject, QThread, pyqtSlot, pyqtSignal, Qt, QRect,
                          QSize)
from PyQt5.QtWidgets import (QWidget, QLabel, QMessageBox, QListWidget,
                             QPushButton, QApplication, QTableWidget,
                             QGridLayout, QListWidgetItem, QTableWidgetItem,
                             QLineEdit, QFrame)
from PyQt5.QtGui import (QIcon, QIntValidator)

logger = logging.getLogger(__name__)


class PiClock3(QWidget):
    config = DottedDict()
    pages = DottedDict()
    blocks = DottedDict()
    styles = DottedDict()
    plugins = DottedDict()
    pluginData = DottedDict()

    blockName = 'PiClock3'
    net = QtNetwork.QNetworkAccessManager()

    def __init__(self, config):
        self.config = config
        super().__init__()
        self.screen = QApplication.desktop().screenGeometry()
        logging.info("%s" % (self.screen))
        self.initData()
        self.initWidgets()
        self.showFullScreen()

        logging.info("Startup Finished.")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_F4:
            logging.info("F4 Quit")
            self.close()
        if event.key() == Qt.Key_Space:
            self.nextFrame(1)

    def mousePressEvent(self, event):
        return

    def initData(self):
        styles = self.config.styles
        for style in styles:
            styleString = self._buildStyleString(styles[style])
            logging.debug('styleString: ' + style + '>' + styleString)
            self.styles[style] = styleString

    def initWidgets(self):
        self.setStyleSheet(self.styles.default)
        unsortedPages = []
        for pageName in self.config.pages:
            page = self.config.pages[pageName]
            logging.debug("Building Page: " + pageName)
            order = 0
            if 'order' in page:
                order = page.order
            pageFrame = QFrame(self)
            pageFrame.setVisible(False)
            pageFrame.setObjectName(pageName)
            pageFrame.setGeometry(
                0, 0, self.screen.width(), self.screen.height())
            styleString = self._buildFullStyleString(pageName, page)
            logging.debug("Page Style " + styleString)
            pageFrame.setStyleSheet(styleString)
            pageFrame.order = order
            pageFrame.blockName = pageName
            self.pages[pageName] = pageFrame
            unsortedPages.append(pageFrame)

            if 'blocks' in page:
                logging.debug("call loadblocks, passing %s %s"
                              % (self.blockName, self))
                self.loadBlocks(pageFrame, page.blocks)

        sortedPages = sorted(unsortedPages, key=lambda x: x.order)

        for i in range(len(sortedPages)):
            pageFrame = sortedPages[i]
            if i == 0:
                pageFrame.setVisible(True)
            pageFrame.pageNumber = i
            self.pages[pageFrame.blockName] = pageFrame

        for module in self.config.plugins:
            self.loadModule(module, self.config.plugins[module])

    def loadModule(self, name, moduleConfig):
        mod = importlib.import_module(moduleConfig.module)
        logging.info('loading %s %s', mod, name)
        self.pluginData[name] = DottedDict()
        cls = None
        clsName = ''
        for cname, obj in inspect.getmembers(mod):
            try:
                if hasattr(obj, "__bases__") and Plugin in obj.__bases__:
                    cls = obj
                    clsName = cname
            except BaseException:
                pass
        logger.debug('found %s %s', cls, clsName)
        instance = cls(self, name, moduleConfig)
        self.plugins[name] = instance
        instance.start()

    def nextFrame(self, n):
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
        logging.debug("new Current %s" % (current))
        for pageName in self.pages:
            page = self.pages[pageName]
            if page.pageNumber == current:
                logging.info("Setting page %s (%s) to visible"
                             % (current, pageName))
                page.setVisible(True)

    def _buildStyleString(self, style):
        styleString = ''
        for element in style:
            styleString += ' ' + element + ': ' + str(style[element]) + ';'
        return styleString

    def _buildFullStyleString(self, name, page, size=None):
        styleString = ""

        if 'style-cascade' in page:
            if not page['style-cascade']:
                styleString += "#" + name + " {"

        # pick up style keywords and expand
        if 'style' in page:
            if page['style'] in self.styles:
                styleString += self.styles[page['style']]

        if 'background-image' in page:
            styleString += " border-image: url(" + \
                self.expand(page['background-image']) + \
                ") 0 0 0 0 stretch stretch;"

        if 'styles' in page:
            for sty in page.styles:
                styleString += " " + sty + ": " + \
                    self.expand(str(page.styles[sty])) + ';'
        # redo font size if it is a bare number and size of parent was passed
            if 'font-size' in page.styles and isinstance(size, QSize):
                fs = str(page.styles['font-size'])
                if fs.replace('.', '', 1).replace('-', '', 1).isnumeric():
                    fs = "%dpx" % (float(fs) * size.height())
                    styleString += " font-size: " + fs + ';'

        if '{' in styleString:
            styleString += "}"
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

    def loadBlocks(self, parent, blocks):
        unsortedBlocks = []
        for blockName in blocks:
            block = blocks[blockName]
            order = 0
            if 'order' in block:
                order = block.order
            b = {}
            b['order'] = order
            b['block'] = block
            b['name'] = blockName
            unsortedBlocks.append(b)
        sortedBlocks = sorted(unsortedBlocks, key=lambda x: x['order'])
        for blockRef in sortedBlocks:
            self.loadBlock(parent, blockRef['name'], blockRef['block'])

    def loadBlock(self, parent, blockName, block):
        logging.debug("Processing Block %s in %s"
                      % (blockName, parent.blockName))
        type = block.type
        if type == 'frame':
            blockWidget = QFrame(parent)
        elif type == 'label':
            blockWidget = QLabel(parent)
        else:
            raise Exception("%s.type = % invalid block type"
                            % (blockName, type))
        blockWidget.setObjectName(blockName)
        geometry = self._calcGeometry(parent, block)
        logging.debug("Block Geometry: %s" % (geometry))
        blockWidget.setGeometry(geometry)
        styleString = self._buildFullStyleString(
            blockName, block, blockWidget.size()
        )
        logging.debug("Block Style " + styleString)
        blockWidget.setStyleSheet(styleString)
        if 'text' in block:
            logger.debug("Block Text: %s" % (block.text))
            blockWidget.setText(block.text)
        blockWidget.blockName = blockName
        blockWidget.blockType = type
        self.blocks[blockName] = blockWidget
        if 'blocks' in block:
            self.loadBlocks(blockWidget, block.blocks)

    def _calcGeometry(self, parent, block):
        if parent == self:
            parentWidth = self.screen.width()
            parentHeight = self.screen.height()
        else:
            parentWidth = parent.width()
            parentHeight = parent.height()
        top = 0
        left = 0
        width = parentWidth
        height = parentHeight

        if 'width' in block:
            width = parentWidth * block.width
        if 'height' in block:
            height = parentHeight * block.height
        if 'aspect' in block:
            if 'width' in block:
                width = parentWidth * block.width
                height = width * block.aspect
            else:
                height = parentHeight * block.height
                width = height * block.aspect
        else:
            width = parentWidth * block.width
            height = parentHeight * block.height
        if 'horizontal-center' in block:
            c = parentWidth * block['horizontal-center']
            left = parentWidth / 2 + c - width / 2
        if 'vertical-center' in block:
            c = parentHeight * block['vertical-center']
            top = parentHeight / 2 + c - height / 2
        if 'left' in block:
            left = parentWidth * block.left
        if 'top' in block:
            top = parentHeight * block.top
        if 'right' in block:
            left = parentWidth - parentWidth * block.right - width
        if 'bottom' in block:
            top = parentHeight - parentHeight * block.bottom - height

        return QRect(left, top, width, height)


class LogHandler(logging.handlers.RotatingFileHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.doRollover()
