import logging
import re
from PyQt5 import (QtNetwork)
from PyQt5.QtCore import (QObject, QThread, pyqtSlot, pyqtSignal, Qt, QRect,
                          QSize, QUrl)
from PyQt5.QtNetwork import (QNetworkReply, QNetworkRequest, QNetworkAccessManager)

logger = logging.getLogger(__name__)

def safeurl(url):
    return re.sub(r'((?:apikey|appid|key|access_token)=)[^&]*',
                  r'\1<key>', url)

class WebGet(QObject):
    webGets = []
    # one manager for the whole application.  A manager per request means a
    # fresh connection pool per request, and a page of large radars asks for
    # dozens at once - enough of them to stall the gui thread for twenty
    # seconds before anything is painted.  Shared, Qt keeps its own pool and
    # queues the rest.
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
        self.request = QNetworkRequest(QUrl(self.url))
        self.reply = self.manager.get(self.request)
        self.reply.finished.connect(self.finished)

    #def __del__(self):
    #    logger.debug("delete of WebGet Object %s", self.url)

    def finished(self):
        logger.debug("WebGet Finished")
        request = self.reply.request()
        if self.reply.error() != QNetworkReply.NoError:
            self.callback(self.reply.error(), None, self.params)
        else:
            data = self.reply.readAll()
            self.callback(self.reply.error(), data, self.params)
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

