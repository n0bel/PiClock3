#!/bin/sh
# Run by a desktop's autostart: a countdown with Now and Cancel, then the
# clock.  The countdown is 45 seconds, or the number of seconds given as
# the first argument.
cd "$(dirname "$0")" || exit 1
python3 startup.py "${1:-45}" || exit 0
exec python3 PyQtPiClock3.py
