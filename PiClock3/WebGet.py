import logging
import re
import time
from PyQt5 import (QtNetwork)
from PyQt5.QtCore import (QObject, QThread, pyqtSlot, pyqtSignal, Qt, QRect,
                          QSize, QUrl)
from PyQt5.QtNetwork import (QNetworkReply, QNetworkRequest, QNetworkAccessManager)

logger = logging.getLogger(__name__)

def safeurl(url):
    """a key in a query parameter becomes <key>; one in a path would not"""
    return re.sub(r'((?:apikey|appid|key|access_token)=)[^&]*',
                  r'\1<key>', url)

class WebGet(QObject):
    webGets = []
    # one manager for the whole application - a manager per request is a
    # connection pool per request
    sharedManager = None
    
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
        self.started = time.monotonic()
        self.request = QNetworkRequest(QUrl(self.url))
        self.reply = self.manager.get(self.request)
        self.reply.finished.connect(self.finished)

    #def __del__(self):
    #    logger.debug("delete of WebGet Object %s", self.url)

    def finished(self):
        error = self.reply.error()
        took = time.monotonic() - self.started
        waiting = len(WebGet.webGets)
        if error != QNetworkReply.NoError:
            logger.warning("WebGet FAILED %s in %.3fs (%d in flight): %s",
                           error, took, waiting, safeurl(self.url))
            self.callback(error, None, self.params)
        else:
            logger.debug("WebGet ok in %.3fs (%d in flight): %s",
                         took, waiting, safeurl(self.url))
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

