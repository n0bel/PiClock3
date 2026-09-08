"""What the log is opened as, read from the text before the config is.

    python3 tests/logtest.py

The settings about the log have to be read before the log exists, from
the config text rather than from a loaded config.  So this reads text the
way yaml would have: quoted and unquoted have to come out the same, since
both are what somebody may have written.

Needs PyQt5, because it loads PyQtPiClock3.py to reach the functions it is
about.  It opens no window.
"""
import importlib.util
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

spec = importlib.util.spec_from_file_location('clock', 'PyQtPiClock3.py')
clock = importlib.util.module_from_spec(spec)
spec.loader.exec_module(clock)


def written(text):
    handle, path = tempfile.mkstemp(suffix='.yaml', text=True)
    with os.fdopen(handle, 'w', encoding='utf-8') as fh:
        fh.write(text)
    return path


# (name, config text, --set list, key, what early should answer)
READS = [
    ('bare', 'logging-rotate: daily\n', [], 'logging-rotate', 'daily'),
    ('single quoted', "logging-rotate: 'daily'\n", [], 'logging-rotate',
     'daily'),
    ('double quoted', 'logging-rotate: "daily"\n', [], 'logging-rotate',
     'daily'),
    ('spaced', 'logging-rotate:    daily   \n', [], 'logging-rotate',
     'daily'),
    ('trailing comment', 'logging-rotate: daily  # why\n', [],
     'logging-rotate', 'daily'),
    ('quoted with comment', "logging-rotate: 'daily'  # why\n", [],
     'logging-rotate', 'daily'),
    ('commented out', '# logging-rotate: daily\n', [], 'logging-rotate',
     None),
    ('indented under a widget',
     'widgets:\n  a:\n    logging-rotate: daily\n', [], 'logging-rotate',
     None),
    ('absent', 'pages: {}\n', [], 'logging-rotate', None),
    ('blank', 'logging-rotate:\n', [], 'logging-rotate', None),
    ('empty quotes', "logging-rotate: ''\n", [], 'logging-rotate', None),
    # the command line, both ways, and it beats the file
    ('--set bare', 'logging-rotate: per-run\n', ['logging-rotate=daily'],
     'logging-rotate', 'daily'),
    ('--set quoted', 'logging-rotate: per-run\n',
     ["logging-rotate='daily'"], 'logging-rotate', 'daily'),
    ('--set last wins', 'logging-rotate: per-run\n',
     ['logging-rotate=daily', 'logging-rotate=per-run'], 'logging-rotate',
     'per-run'),
    # numbers read the same either way, though --check refuses a quoted one
    ('number bare', 'logging-keep: 3\n', [], 'logging-keep', '3'),
    ('number quoted', "logging-keep: '3'\n", [], 'logging-keep', '3'),
]

# (name, config text, --set, expected handler, maxBytes, backupCount)
BUILDS = [
    ('nothing said', 'pages: {}\n', [], 'LogHandler', 10 * 1024 * 1024, 7),
    ('daily bare', 'logging-rotate: daily\n', [],
     'TimedRotatingFileHandler', None, 7),
    ('daily quoted', "logging-rotate: 'daily'\n", [],
     'TimedRotatingFileHandler', None, 7),
    ('keep bare', 'logging-keep: 3\n', [], 'LogHandler',
     10 * 1024 * 1024, 3),
    ('keep quoted', "logging-keep: '3'\n", [], 'LogHandler',
     10 * 1024 * 1024, 3),
    ('size 0 is no limit', 'logging-max-size: 0\n', [], 'LogHandler', 0, 7),
    ('size a fraction', 'logging-max-size: 0.5\n', [], 'LogHandler',
     524288, 7),
    # nothing here may raise: there is no log yet to raise into
    ('size not a number', 'logging-max-size: wide\n', [], 'LogHandler',
     10 * 1024 * 1024, 7),
    ('keep a fraction', 'logging-keep: 3.7\n', [], 'LogHandler',
     10 * 1024 * 1024, 3),
    ('keep negative', 'logging-keep: -2\n', [], 'LogHandler',
     10 * 1024 * 1024, 7),
]


# (name, config text, --set, the level the root logger should end up at).
# The one that matters is the first: a config saying nothing used to get
# python's own WARNING and write an empty file, on a clock whose bug report
# asks for the log.
LEVELS = [
    ('nothing said', 'pages: {}\n', [], 'INFO'),
    ('the file says debug', 'logging-level: debug\n', [], 'DEBUG'),
    ('the file says warning', 'logging-level: warning\n', [], 'WARNING'),
    ('a word that is not a level', 'logging-level: chatty\n', [], 'INFO'),
    ('--set with nothing in the file', 'pages: {}\n',
     ['logging-level=debug'], 'DEBUG'),
    ('--set over a file that says warning', 'logging-level: warning\n',
     ['logging-level=debug'], 'DEBUG'),
]


def levels():
    """what the root logger is set to before the config is even read.

    clock.early() is what decides it, so this asks the same question the
    program asks and not a second version of it.
    """
    import logging  # noqa: E402 - only this function needs it
    out = []
    for name, text, sets, want in LEVELS:
        path = written(text)
        try:
            got = clock.LEVELS.get(clock.early(path, sets, 'logging-level'),
                                   clock.DEFAULT_LEVEL)
        finally:
            os.unlink(path)
        out.append((name, want, logging.getLevelName(got)))
    return out


def main():
    failed = 0
    for name, want, got in levels():
        if got == want:
            print('  ok    level %-26s %s' % (name, got))
        else:
            failed += 1
            print('  FAIL  level %-26s wanted %s, got %s'
                  % (name, want, got))

    for name, text, sets, key, want in READS:
        path = written(text)
        try:
            got = clock.early(path, sets, key)
        finally:
            os.unlink(path)
        if got == want:
            print('  ok    read  %-26s %r' % (name, got))
        else:
            failed += 1
            print('  FAIL  read  %-26s wanted %r, got %r'
                  % (name, want, got))

    for name, text, sets, kind, maxBytes, keep in BUILDS:
        path = written(text)
        try:
            h = clock.logHandler(path, sets)
        except Exception as e:                                # noqa: BLE001
            failed += 1
            print('  FAIL  build %-26s raised %s: %s'
                  % (name, type(e).__name__, e))
            os.unlink(path)
            continue
        bad = []
        if type(h).__name__ != kind:
            bad.append('wanted %s, got %s' % (kind, type(h).__name__))
        if maxBytes is not None and getattr(h, 'maxBytes', None) != maxBytes:
            bad.append('maxBytes %s, wanted %s'
                       % (getattr(h, 'maxBytes', None), maxBytes))
        if h.backupCount != keep:
            bad.append('backupCount %s, wanted %s' % (h.backupCount, keep))
        h.close()
        os.unlink(path)
        for leftover in ('PyQtPiClock3.log', 'PyQtPiClock3.log.1'):
            if os.path.isfile(leftover):
                os.unlink(leftover)
        if bad:
            failed += 1
            print('  FAIL  build %-26s %s' % (name, '; '.join(bad)))
        else:
            print('  ok    build %-26s %s' % (name, kind))

    print('\n  %d cases, %d failed'
          % (len(LEVELS) + len(READS) + len(BUILDS), failed))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
