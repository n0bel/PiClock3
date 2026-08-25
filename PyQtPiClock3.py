import logging.handlers
import traceback
import os
import sys

from PyQt5.QtWidgets import QMessageBox, QApplication

from PiClock3.Config import Config
from PiClock3.PiClock3 import PiClock3

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 'plugins'))


USAGE = """
    python3 PyQtPiClock3.py [config.yaml] [--set key=value ...] [--at when]

      --set  a config key, dotted for anything nested, taking the last word
             over the file:   --set units=metric
                              --set location.timezone=Europe/Oslo
                              --set widgets.clock.plugin=PiClock3.DigitalClock

             theme: and layout: are blocks of their own, laid over whichever
             theme or layout a page names, so either can be tried without
             editing it:      --set theme.default.color=#ff8800
                              --set theme.borders.default.width=0.03
                              --set layout.regions.clock.width=0.5

             A plugin is reached through kind-settings or plugin-settings,
             the same way a theme reaches one:
                              --set kind-settings.radar.palette=4

      --at   start the clock at another time and let it run from there,
             which is how to see a polar night in August:
                              --at 2026-06-21
                              --at "2026-06-21 13:45"
             Only the clock moves.  The radar still shows what the frame
             server has, because that is all it has.

    Values are read as yaml, so 4 is a number and true is a boolean.  A word
    starting with # is a color rather than a comment.
"""


def readArgs(args):
    """the config to load, and the settings to lay over it"""
    configName, settings, i = 'Config.yaml', [], 0
    while i < len(args):
        a = args[i]
        if a in ('-h', '--help'):
            # asking is not an error: it goes to stdout and exits happy
            print(USAGE)
            sys.exit(0)
        elif a == '--set':
            i += 1
            if i >= len(args):
                raise SystemExit("\n--set wants key=value\n" + USAGE)
            settings.append(args[i])
        elif a == '--at':
            i += 1
            if i >= len(args):
                raise SystemExit("\n--at wants a date and time\n" + USAGE)
            settings.append('start-at=' + args[i])
        elif a.startswith('-'):
            raise SystemExit("\nno such option %r\n" % a + USAGE)
        else:
            configName = a
        i += 1
    return configName, settings


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

    def excepthook(etype, value, tb):
        logging.error("unhandled exception:\n%s",
                      ''.join(traceback.format_exception(etype, value, tb)))

    sys.excepthook = excepthook

    try:
        app = QApplication(sys.argv)
        try:
            configName, settings = readArgs(sys.argv[1:])
            config = Config()
            config.load(configName)
            # after the file, so the command line has the last word
            for setting in settings:
                config.override(setting)
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
    except SystemExit as e:
        # sys.exit(app.exec_()) arrives here with an int, and that is a
        # normal quit.  a SystemExit carrying a message is a config problem
        # somebody needs to read, so say it and fail.
        if isinstance(e.code, str):
            # the logger writes to stderr as well as to the file, so saying
            # it here too would say it twice
            logging.error('%s', e.code)
            sys.exit(1)
    except Exception as e:
        logging.exception('Unhandled Error Caught at outermost level:')
        QMessageBox.critical(None, "Unhandled Error",
                             type(e).__name__ + ': ' + str(e), QMessageBox.Ok)
