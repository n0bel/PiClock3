import logging
import re

from PyQt5.QtGui import QFontMetrics
from PyQt5.QtWidgets import QLabel

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
