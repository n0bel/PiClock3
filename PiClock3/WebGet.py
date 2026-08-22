import logging
from PyQt5 import (QtNetwork)
from PyQt5.QtCore import (QObject, QThread, pyqtSlot, pyqtSignal, Qt, QRect,
                          QSize, QUrl)
from PyQt5.QtNetwork import (QNetworkReply, QNetworkRequest, QNetworkAccessManager)

logger = logging.getLogger(__name__)

class WebGet(QObject):
    webGets = []
    
    def __init__(self, url, callback, params = dict(), manager=None):
        super().__init__()
        WebGet.webGets.append(self)
        self.manager = manager
        self.url = url
        self.callback = callback
        self.params = params
        if self.manager == None:
            self.manager = QtNetwork.QNetworkAccessManager(self)
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

