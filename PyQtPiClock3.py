import logging.handlers
import sys

from PyQt5.QtWidgets import QMessageBox, QApplication

from PiClock3.Config import Config
from PiClock3.PiClock3 import PiClock3


class LogHandler(logging.handlers.RotatingFileHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.doRollover()


if __name__ == '__main__':

    fmt = logging.Formatter('%(asctime)s %(message)s')
    logger = logging.getLogger()
    fileh = LogHandler(filename='PyQtPiClock3.log', backupCount=7)
    fileh.setFormatter(fmt)
    logger.addHandler(fileh)
    errh = logging.StreamHandler(sys.stderr)
    fileh.setFormatter(fmt)
    logger.addHandler(errh)
    logger.setLevel(logging.WARNING)

    try:
        app = QApplication(sys.argv)
        try:
            configName = 'Config.yaml'
            if len(sys.argv) > 1:
                configName = sys.argv[1]
            config = Config()
            config.load(configName)
            if 'logging-level' in config:
                if config['logging-level'] == 'debug':
                    logger.setLevel(logging.DEBUG)
                if config['logging-level'] == 'warning':
                    logger.setLevel(logging.WARNING)
                if config['logging-level'] == 'info':
                    logger.setLevel(logging.INFO)
            logging.info("Startup....")
            logging.debug('config = %s', config.dump())
        except Exception as e:
            logging.exception('PyQtPiClock3 Config Error:')
            QMessageBox.critical(
                None, "PyQtPiClock3 Config Error",
                type(e).__name__ + ': ' + str(e), QMessageBox.Ok)
            sys.exit(1)
        ex = PiClock3(config)
        sys.exit(app.exec_())
    except SystemExit:
        pass
    except Exception as e:
        logging.exception('Unhandled Error Caught at outermost level:')
        QMessageBox.critical(None, "Unhandled Error",
                             type(e).__name__ + ': ' + str(e), QMessageBox.Ok)
