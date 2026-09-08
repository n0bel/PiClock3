import logging.handlers
import re
import traceback
import os
import sys

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFontDatabase
from PyQt5.QtWidgets import QMessageBox, QApplication

from PiClock3.Check import Check
from PiClock3.Config import Config, ConfigError
from PiClock3.PiClock3 import PiClock3
from PiClock3.ResolvedConfig import ResolvedConfig

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 'plugins'))


USAGE = """
    python3 PyQtPiClock3.py [config.yaml] [--set key=value ...] [--at when]

      --check  read the config against the schemas and say what is wrong
             with it, rather than running.  Opens no window and needs no
             screen, so it is what a pi with no display, or something
             building this, can run.  A problem means it cannot work and
             exits 1; a warning means it runs but not as written.

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
                              --set kind-settings.radar-frames.palette=4

      --at   start the clock at another time and let it run from there,
             which is how to see a polar night in August:
                              --at 2026-06-21
                              --at "2026-06-21 13:45"
             Only the clock moves.  The radar still shows what the frame
             server has, because that is all it has.

      --geometry  run in a window of this size instead of filling the
             screen, which is how to see what a clock looks like on a
             screen you do not have:
                              --geometry 800x600
                              --geometry 1920x1080+100+100
             Every size in a layout or a theme is a fraction of this, so
             what comes out is what that screen would show.

    Values are read as yaml, so 4 is a number and true is a boolean.  A word
    starting with # is a color rather than a comment.
"""


def readArgs(args):
    """the config to load, the settings to lay over it, and whether to
    read it rather than run it"""
    configName, settings, checking, i = 'Config.yaml', [], False, 0
    while i < len(args):
        a = args[i]
        if a in ('-h', '--help'):
            # asking is not an error: it goes to stdout and exits happy
            print(USAGE)
            sys.exit(0)
        elif a == '--check':
            checking = True
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
        elif a == '--geometry':
            i += 1
            if i >= len(args):
                raise SystemExit("\n--geometry wants WIDTHxHEIGHT\n" + USAGE)
            settings.append('geometry=' + args[i])
        elif a.startswith('-'):
            raise SystemExit("\nno such option %r\n" % a + USAGE)
        else:
            configName = a
        i += 1
    return configName, settings, checking


def loadConfig(configName, settings):
    """the file, with each --set laid over it, and which paths those were"""
    config = Config()
    config.load(configName)
    overridden = []

    def setLevel():
        if config.get('logging-level') in LEVELS:
            logging.getLogger().setLevel(LEVELS[config['logging-level']])

    # the file's level first, so that each --set can say what it did as it
    # does it - which is the only way to catch a mistyped path, since one
    # that matches nothing is otherwise silent
    setLevel()
    # after the file, so the command line has the last word
    for setting in settings:
        overridden.append(config.override(setting))
    # again, in case one of them was logging-level itself
    setLevel()
    return config, overridden


def resolveAndCheck(configName, settings):
    """the config, worked out once, and read against the schemas.

    The same two steps whether this is going to draw a clock or only say
    what is wrong with one, so the answers a check gives are the answers
    the clock will then be built from.
    """
    config, overridden = loadConfig(configName, settings)
    resolved = ResolvedConfig(config).build()
    check = Check(config, resolved, configName, overridden)
    check.run()
    return config, resolved, check


def runCheck(configName, settings):
    """--check: say what is wrong with a config, and how badly.

    Written to stdout rather than logged, because this is somebody asking a
    question at a prompt or something building the project, and the answer
    is the output.  Nothing here touches Qt, so it runs with no screen.
    """
    try:
        check = resolveAndCheck(configName, settings)[2]
    except ConfigError as e:
        # the config itself will not read, so there is nothing to check and
        # nothing to draw.  One finding, in the shape of the rest of them
        print('%-8s %s: %s' % ('problem', e.where, e.message))
        print('%s: 1 problem, 0 warnings' % configName)
        return 1
    for line in check.report():
        print(line)
    problems, warnings = len(check.problems()), len(check.warnings())
    print('%s: %d problem%s, %d warning%s'
          % (configName, problems, '' if problems == 1 else 's',
             warnings, '' if warnings == 1 else 's'))
    return 1 if problems else 0


# long enough to read a screenful and write one down, short enough that a
# clock on a wall is not left holding a dialog
COUNTDOWN = 30


def fixedWidth(box):
    """a findings box in a font whose columns line up.

    A yaml fault quotes the line it went wrong on and puts a caret under
    the character, and a caret under proportional text points at nothing.
    """
    box.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))


def refuse(check, seconds=COUNTDOWN):
    """what is wrong with this config, on the screen the clock would use.

    All of them rather than the first, because the person reading is
    standing at a wall rather than a prompt and will not want to come back
    once per fault.  It closes itself and gives up: a clock drawing the
    wrong thing quietly is what the checking is for.
    """
    problems = check.problems()
    for severity, where, message in problems:
        logging.error('%s: %s', where, message)

    box = QMessageBox(QMessageBox.Critical, 'PiClock3 will not start', '')
    # one label, because setTextFormat reaches this one and not an
    # informative half.  A finding quotes the config, and Qt reading a
    # quoted tag as html swallows it and the newlines with it.
    box.setTextFormat(Qt.PlainText)
    fixedWidth(box)
    box.setText('%d problem%s with this configuration:\n\n%s'
                % (len(problems), '' if len(problems) == 1 else 's',
                   '\n'.join('%s: %s' % (where, message)
                             for _, where, message in problems)))
    button = box.addButton(QMessageBox.Ok)

    left = [seconds]

    def tick():
        left[0] -= 1
        if left[0] <= 0:
            box.close()
        else:
            button.setText('Quit (%d)' % left[0])

    timer = QTimer(box)
    timer.timeout.connect(tick)
    timer.start(1000)
    button.setText('Quit (%d)' % seconds)
    box.exec_()


class LogHandler(logging.handlers.RotatingFileHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.doRollover()


LOGFILE = 'PyQtPiClock3.log'

LEVELS = {'debug': logging.DEBUG, 'info': logging.INFO,
          'warning': logging.WARNING}


def early(configName, settings, key):
    """one top-level setting, read from the text before the config is.

    The log is opened first, so the settings about the log have to come
    from somewhere earlier.  --set wins, then a key at column 0.  Only
    the handler leans on this; the loaded config is what everything else
    reads, and it has the last word.

    Quotes come off, because this reads text where yaml would have read a
    value - and 'daily' with its quotes still on matches nothing.
    """
    for one in reversed(settings):
        name, _, value = one.partition('=')
        if name.strip() == key:
            return unquoted(value)
    try:
        with open(configName, encoding='utf-8') as fh:
            found = re.search(
                r'(?m)^%s:[ \t]*(.*?)[ \t]*(?:#.*)?$' % re.escape(key),
                fh.read())
    except OSError:
        return None
    return unquoted(found.group(1)) if found else None


def unquoted(value):
    value = value.strip()
    if len(value) > 1 and value[0] == value[-1] and value[0] in '\'"':
        value = value[1:-1].strip()
    return value or None


def number(value, default):
    """a number out of the config text, or the default.

    Never raises: this runs before there is a log to complain into, and
    --check is where a value out of range gets named.
    """
    try:
        found = type(default)(float(value))
    except (TypeError, ValueError):
        return default
    return found if found >= 0 else default


def logHandler(configName, settings):
    """the log, rolled the way the config asks.

    per-run at every start and again at logging-max-size, so the run
    before this one is still there and no one run fills a card.  daily
    at midnight instead, and not on a restart.
    """
    keep = number(early(configName, settings, 'logging-keep'), 7)
    if early(configName, settings, 'logging-rotate') == 'daily':
        return logging.handlers.TimedRotatingFileHandler(
            LOGFILE, when='midnight', backupCount=keep)
    mb = number(early(configName, settings, 'logging-max-size'), 10.0)
    return LogHandler(LOGFILE, maxBytes=int(mb * 1024 * 1024),
                      backupCount=keep)


if __name__ == '__main__':

    # padded, so the messages still line up under each other - the level
    # is four characters or eight depending on which one it is
    fmt = logging.Formatter('%(asctime)s %(levelname)-8s %(message)s')
    # a period rather than logging's own comma, which is the decimal point
    # everywhere else in this project and the only one RFC 3339 allows
    fmt.default_msec_format = '%s.%03d'
    logger = logging.getLogger()
    # the arguments first: they need no log, and the log is built from them
    configName, settings, checking = readArgs(sys.argv[1:])
    errh = logging.StreamHandler(sys.stderr)
    errh.setFormatter(fmt)
    logger.addHandler(errh)
    # from the text, since the config is not read yet.  setLevel() sets it
    # again from the loaded config, which is the one that counts
    logger.setLevel(LEVELS.get(early(configName, settings, 'logging-level'),
                               logging.WARNING))

    def excepthook(etype, value, tb):
        logging.error("unhandled exception:\n%s",
                      ''.join(traceback.format_exception(etype, value, tb)))

    sys.excepthook = excepthook

    # before any of Qt, so --check runs where there is no screen to open a
    # window on, and before the log file, because opening it rolls it -
    # checking a config in a loop should not push the last real run out
    if checking:
        sys.exit(runCheck(configName, settings))

    fileh = logHandler(configName, settings)
    fileh.setFormatter(fmt)
    logger.addHandler(fileh)

    try:
        app = QApplication(sys.argv)
        try:
            config, resolved, check = resolveAndCheck(configName, settings)
            logging.info("Startup....")
        except ConfigError as e:
            # a file that will not read, said the way a finding is said -
            # the refusal window is for a config that was read and is
            # wrong, and this one was never read at all
            logging.error('%s: %s', e.where, e.message)
            box = QMessageBox(QMessageBox.Critical,
                              'PiClock3 will not start', '')
            box.setTextFormat(Qt.PlainText)
            fixedWidth(box)
            box.setText('%s\n\n%s' % (e.where, e.message))
            box.exec_()
            sys.exit(1)
        except Exception as e:
            logging.exception('PyQtPiClock3 Config Error:')
            QMessageBox.critical(
                None, "PyQtPiClock3 Config Error",
                type(e).__name__ + ': ' + str(e), QMessageBox.Ok)
            sys.exit(1)
        for _, where, message in check.warnings():
            logging.warning('%s: %s', where, message)
        if check.problems():
            refuse(check)
            sys.exit(1)
        # built from what was just checked rather than worked out again
        ex = PiClock3(config, resolved)
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
        # a number already says what to exit with, and swallowing it here
        # would answer 0 to everything that asked
        raise
    except Exception as e:
        logging.exception('Unhandled Error Caught at outermost level:')
        QMessageBox.critical(None, "Unhandled Error",
                             type(e).__name__ + ': ' + str(e), QMessageBox.Ok)
