"""What a page's background: draws - a color, or a picture.

    python3 tests/backgroundtest.py

`background:` took a picture and only a picture, so a theme that wanted a
plain page shipped a rectangle of one color as a .png.  It takes a color
now, and the two are told apart by asking Qt whether the value names one -
with a file that exists winning the tie, since no filename is a color and
somebody may have one called red.

Needs PyQt5 for QColor, which is a value and wants no window.
"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

from PiClock3.PiClock3 import backgroundRule            # noqa: E402

COLOR = 'background-color'
PICTURE = 'border-image'

# (name, the value background: holds, which rule it must build)
CASES = [
    ('a picture, as themes have always said it',
     'PiClock3/themes/circuit/background.png', PICTURE),
    ('a picture that is not there is still a picture',
     'nosuch.png', PICTURE),
    ('a path with no extension at all', 'art/backdrop', PICTURE),

    ('three digit hex', '#000', COLOR),
    ('six digit hex', '#103125', COLOR),
    ('eight digit hex, alpha first', '#c0103125', COLOR),
    ('a name Qt knows', 'black', COLOR),
    ('another one', 'darkslategray', COLOR),

    # what is neither: it draws nothing either way, and a picture rule is
    # the older behavior, so that is what it keeps
    ('a word that is no color and no file', 'chartreusey', PICTURE),
    ('empty', '', PICTURE),
]


def main():
    failed = 0
    for name, value, wanted in CASES:
        rule = backgroundRule('clock-page-background', value)
        if wanted not in rule:
            print('  FAIL  %s: %r built %s' % (name, value, rule))
            failed += 1
            continue
        if wanted is COLOR and value not in rule:
            print('  FAIL  %s: the color is not in %s' % (name, rule))
            failed += 1
            continue
        print('  ok    %s' % name)

    # a file called red is a file, not a color.  Written rather than
    # assumed, because it is the one case the order of the two tests
    # decides.
    holder = tempfile.mkdtemp()
    red = os.path.join(holder, 'red')
    with open(red, 'w', encoding='utf-8') as fh:
        fh.write('not a color\n')
    rule = backgroundRule('clock-page-background', red)
    if PICTURE in rule:
        print('  ok    a file named red is a picture')
    else:
        print('  FAIL  a file named red became a color: %s' % rule)
        failed += 1
    os.unlink(red)
    os.rmdir(holder)

    print('%d cases, %d failed' % (len(CASES) + 1, failed))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
