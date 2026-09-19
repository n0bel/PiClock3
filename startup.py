"""A countdown before the clock starts, with Now and Cancel.

    python3 startup.py [seconds]

What startup.sh runs first, so a clock starting on its own at boot can be
stopped by someone at the Pi, and gives the network and the time a moment
to arrive.  Exits 0 to start the clock and 1 to leave it.

A Pi has no clock of its own, so if the countdown ends before the time is
set from the network, it waits for that too.
"""
import shutil
import subprocess
import sys

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (QApplication, QDialog, QHBoxLayout, QLabel,
                             QPushButton, QVBoxLayout)

# seconds to count down when no number is given
DEFAULT = 45

# how long past the countdown to wait for the time to be set
TIMEWAIT = 60


def timeIsSet():
    """whether the system clock has been set from the network.

    True where timedatectl cannot be asked.
    """
    if not shutil.which('timedatectl'):
        return True
    try:
        out = subprocess.run(
            ['timedatectl', 'show', '-p', 'NTPSynchronized', '--value'],
            capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return True
    return out.strip() != 'no'


class Countdown(QDialog):

    def __init__(self, seconds):
        super().__init__()
        self.left = seconds
        self.waited = 0
        self.setWindowTitle('PiClock3')
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.label = QLabel()
        self.label.setAlignment(Qt.AlignCenter)
        now = QPushButton('Now')
        cancel = QPushButton('Cancel')
        now.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        buttons = QHBoxLayout()
        buttons.addWidget(now)
        buttons.addWidget(cancel)
        layout = QVBoxLayout(self)
        layout.addWidget(self.label)
        layout.addLayout(buttons)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(1000)
        self.tick(counting=False)

    def tick(self, counting=True):
        if counting and self.left > 0:
            self.left -= 1
        if self.left > 0:
            self.label.setText('Starting PiClock3 in %d seconds' % self.left)
            return
        if timeIsSet() or self.waited >= TIMEWAIT:
            self.accept()
            return
        self.waited += 1
        self.label.setText('Waiting for the time to be set')


def main():
    seconds = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT
    app = QApplication(sys.argv[:1])
    dialog = Countdown(seconds)
    dialog.show()
    started = dialog.exec_() == QDialog.Accepted
    app.quit()
    return 0 if started else 1


if __name__ == '__main__':
    sys.exit(main())
