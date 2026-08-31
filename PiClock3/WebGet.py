import collections
import logging
import re
import time
from PyQt5 import (QtNetwork)
from PyQt5.QtCore import (QObject, QThread, pyqtSlot, pyqtSignal, Qt, QRect,
                          QSize, QTimer, QUrl)
from PyQt5.QtNetwork import (QNetworkReply, QNetworkRequest, QNetworkAccessManager)

logger = logging.getLogger(__name__)

# Nothing gives up on its own: QNetworkAccessManager applies no timeout, so a
# request the far end never answers waits for the process to end - and a
# tiler waits on every tile before it hands a frame over, so one stalled tile
# is a radar frame that never arrives at all.  Long enough for a slow tile to
# still land: a radar tile measured 9.9s on a service having a bad afternoon.
TIMEOUT = 15000

# A clock asks for everything at once - four maps, seven frames each, twenty
# tiles a frame - and QNetworkAccessManager opens only a handful of
# connections per host, so the rest sit in its queue.  Holding them here
# instead means the timeout above measures the request rather than the wait
# in front of it, which is the difference between a slow tile and a tile that
# never got sent.  Per host, so a radar server cannot delay the metar.
INFLIGHT = 6

def safeurl(url):
    """a key in a query parameter becomes <key>; one in a path would not"""
    return re.sub(r'((?:apikey|appid|key|access_token)=)[^&]*',
                  r'\1<key>', url)

class WebGet(QObject):
    webGets = []
    # one manager for the whole application - a manager per request is a
    # connection pool per request
    sharedManager = None
    # host -> those waiting to be sent, and how many are out
    waiting = {}
    inflight = {}

    def __init__(self, url, callback, params=None, manager=None):
        super().__init__()
        WebGet.webGets.append(self)
        self.manager = manager
        self.url = url
        self.callback = callback
        self.params = params if params is not None else {}
        if self.manager == None:
            if WebGet.sharedManager is None:
                WebGet.sharedManager = QtNetwork.QNetworkAccessManager()
            self.manager = WebGet.sharedManager
        self.queued = time.monotonic()
        self.started = None
        self.reply = None
        self.request = QNetworkRequest(QUrl(self.url))
        self.host = QUrl(self.url).host()
        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.timedOut)
        WebGet.waiting.setdefault(self.host, collections.deque()).append(self)
        WebGet.send(self.host)

    @classmethod
    def send(cls, host):
        """start as many as this host is allowed to have out at once"""
        while (cls.inflight.get(host, 0) < INFLIGHT
               and cls.waiting.get(host)):
            cls.inflight[host] = cls.inflight.get(host, 0) + 1
            cls.waiting[host].popleft().dispatch()

    def dispatch(self):
        # the clock starts here, not when this was asked for: what is being
        # timed is the request, not the queue in front of it
        self.started = time.monotonic()
        self.reply = self.manager.get(self.request)
        self.reply.finished.connect(self.finished)
        self.timer.start(TIMEOUT)

    def timedOut(self):
        """abort, so the caller hears a failure rather than nothing.

        aborting emits finished with OperationCanceledError, so the normal
        path reports it and the callback runs exactly once.
        """
        if self.reply is not None and self.reply.isRunning():
            logger.warning("WebGet TIMEOUT after %.0fs (queued %.1fs): %s",
                           TIMEOUT / 1000.0,
                           self.started - self.queued, safeurl(self.url))
            self.reply.abort()

    #def __del__(self):
    #    logger.debug("delete of WebGet Object %s", self.url)

    def finished(self):
        self.timer.stop()
        error = self.reply.error()
        took = time.monotonic() - self.started
        queued = len(WebGet.waiting.get(self.host, ()))
        # let the next one for this host go before the callback runs, which
        # may well ask for another
        WebGet.inflight[self.host] = max(0, WebGet.inflight.get(self.host, 1) - 1)
        WebGet.send(self.host)
        if error != QNetworkReply.NoError:
            logger.warning("WebGet FAILED %s in %.3fs (%d queued): %s",
                           error, took, queued, safeurl(self.url))
            self.callback(error, None, self.params)
        else:
            logger.debug("WebGet ok in %.3fs (%d queued): %s",
                         took, queued, safeurl(self.url))
            self.callback(error, self.reply.readAll(), self.params)
        WebGet.webGets.remove(self)

if __name__ == '__main__':
    import sys
    from PyQt5.QtWidgets import (QMessageBox, QApplication, QWidget, QPushButton)

    def callback(error, data):
        print(error, data)

    app = QApplication(sys.argv)
    w = QWidget()
    l = QPushButton(w)
    l.setText("Exit")
    l.clicked.connect(lambda x: w.close())
    w.screen = QApplication.desktop().screenGeometry()
    w.show()
    WebGet("https://google.com", callback)
    sys.exit(app.exec_())

