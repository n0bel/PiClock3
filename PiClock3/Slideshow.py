"""A page background that changes.

A theme names either one picture or a folder of them:

    background: 'background.png'

    background:
      folder: 'slides'
      interval: 305
      fit: contain
      color: '#000'
      order: shuffle

`files:` takes their place when the pictures are named one by one rather than
gathered in a folder.  A folder is listed again when something is put in it;
a named set is fixed.

Which pages run one falls out of which theme they name, so a clock page can
work through photographs while the maps page keeps a fixed picture.

F6 and F7 step back and forward, F8 holds on the picture showing.
"""
import logging
import os
import random

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QLabel

logger = logging.getLogger(__name__)

SUFFIXES = ('.png', '.jpg', '.jpeg', '.bmp', '.gif')


class Slideshow(QLabel):

    def __init__(self, parent, spec, name):
        super().__init__(parent)
        self.folder = spec.get('folder')
        self.files = spec.get('files')
        self.interval = int(float(spec.get('interval', 300)) * 1000)
        self.fit = spec.get('fit', 'contain')
        self.order = spec.get('order', 'shuffle')
        self.held = False
        self.pictures = []
        self.at = -1
        self.listed = None

        self.setObjectName(name)
        self.setGeometry(0, 0, parent.width(), parent.height())
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet('#%s { background-color: %s; }'
                           % (name, spec.get('color', '#000')))

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.advance)
        self.timer.start(self.interval)
        self.advance()

    # ------------------------------------------------------------- the list

    def scan(self):
        """the running order, when there is a new one to have"""
        found = self.listing()
        if found is None:
            return
        if self.order == 'shuffle':
            # a shuffled running order rather than a fresh draw each turn, so
            # that the picture before this one is something that exists
            random.shuffle(found)
        self.pictures = found
        self.at = -1
        logger.info('slideshow: %d pictures', len(found))

    def listing(self):
        """the pictures to show, or None when nothing has changed.

        A folder is listed again only when its own timestamp moves, so a
        picture dropped in appears without a restart and nothing lists a
        directory every turn.  A named set does not change.
        """
        if self.files is not None:
            return None if self.pictures else [str(f) for f in self.files]
        try:
            stamp = os.stat(self.folder).st_mtime
        except OSError:
            logger.warning('slideshow: no folder %s', self.folder)
            return None
        if stamp == self.listed and self.pictures:
            return None
        self.listed = stamp
        found = [os.path.join(self.folder, n)
                 for n in sorted(os.listdir(self.folder))
                 if n.lower().endswith(SUFFIXES)]
        if not found:
            logger.warning('slideshow: nothing to show in %s', self.folder)
        return found

    def advance(self, step=1):
        self.scan()
        if not self.pictures:
            return
        self.at = (self.at + step) % len(self.pictures)
        self.display(self.pictures[self.at])

    def display(self, path):
        picture = QPixmap(path)
        if picture.isNull():
            logger.warning('slideshow: cannot read %s', path)
            return
        if self.fit == 'cover':
            scaled = picture.scaled(self.size(), Qt.KeepAspectRatioByExpanding,
                                    Qt.SmoothTransformation)
            # expanding overshoots on one side; keep the middle of it
            x = max(0, (scaled.width() - self.width()) // 2)
            y = max(0, (scaled.height() - self.height()) // 2)
            scaled = scaled.copy(x, y, self.width(), self.height())
        else:
            scaled = picture.scaled(self.size(), Qt.KeepAspectRatio,
                                    Qt.SmoothTransformation)
        self.setPixmap(scaled)

    # --------------------------------------------------------- the controls

    def step(self, direction):
        """the next picture or the one before, and a full turn on it"""
        self.timer.stop()
        self.advance(direction)
        if not self.held:
            self.timer.start(self.interval)

    def hold(self):
        """stay on this picture, or start moving again"""
        self.held = not self.held
        if self.held:
            self.timer.stop()
        else:
            self.timer.start(self.interval)
        return self.held

    def pageChange(self):
        """a hidden page is not worth decoding pictures for"""
        running = self.isVisible() and not self.held
        if running and not self.timer.isActive():
            self.timer.start(self.interval)
        elif not running and self.timer.isActive():
            self.timer.stop()
