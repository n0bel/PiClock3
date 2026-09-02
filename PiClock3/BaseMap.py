import logging

from PyQt5.QtCore import QPointF
from PyQt5.QtGui import QColor, QImage, QLinearGradient, QPainter

from .Provider import Provider

logger = logging.getLogger(__name__)


class BaseMap(Provider):
    """the map drawn under the frames.

    It arrives as one image with the service's own logo and credit already
    on it, which the terms say must stay visible.  Whatever draws frames
    over it lifts that mark back on top, guided by a mask this provider
    sends along with the pixmap.
    """

    def getMapPixmap(self, view, layerConfig, callback):
        """fetch the map for `view` and answer callback(pixmap, mask).

        `mask` is where this service's own logo and credit sit, in the
        pixmap's own coordinates, or None where there is nothing to
        protect.  Whatever draws frames over the map lifts that much of it
        back on top, so a mark a provider does not describe is a mark that
        gets covered.  bottomBandMask builds the usual one.

        The mask travels with the pixmap rather than sitting on the
        provider, because one instance serves every map on the clock and
        the next response would overwrite it.
        """
        raise NotImplementedError(
            '%s: %s is a base map and has no getMapPixmap'
            % (self.name, type(self).__name__))

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
