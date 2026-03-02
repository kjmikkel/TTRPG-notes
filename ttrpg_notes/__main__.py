from __future__ import annotations

import logging
import logging.handlers
import sys
import types
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QSplashScreen

from ttrpg_notes.ui.app import run_startup
from ttrpg_notes.ui.main_window import MainWindow


def _configure_logging() -> None:
    log_dir = Path.home() / ".ttrpg_notes"
    log_dir.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Rotating file handler — keep up to 3 × 1 MB of history
    fh = logging.handlers.RotatingFileHandler(
        log_dir / "ttrpg_notes.log",
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    root.addHandler(fh)

    # Console handler — only warnings and above (useful when running from a terminal)
    sh = logging.StreamHandler()
    sh.setLevel(logging.WARNING)
    sh.setFormatter(logging.Formatter("[%(levelname)s] %(name)s: %(message)s"))
    root.addHandler(sh)


def _install_excepthook() -> None:
    _log = logging.getLogger(__name__)

    def _hook(
        exc_type: type[BaseException],
        exc_value: BaseException,
        exc_tb: types.TracebackType | None,
    ) -> None:
        if not issubclass(exc_type, (KeyboardInterrupt, SystemExit)):
            _log.critical("Unhandled exception", exc_info=(exc_type, exc_value, exc_tb))
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = _hook

# Must match the resize() call in MainWindow.__init__
_WIN_W = 1100
_WIN_H = 700


def _make_splash() -> QSplashScreen:
    pix = QPixmap(420, 180)
    pix.fill(QColor("#1e1e2e"))

    painter = QPainter(pix)

    title_font = QFont()
    title_font.setPointSize(26)
    title_font.setBold(True)
    painter.setFont(title_font)
    painter.setPen(QColor("#cdd6f4"))
    painter.drawText(pix.rect().adjusted(0, -30, 0, 0), Qt.AlignmentFlag.AlignCenter, "TTRPG Notes")

    sub_font = QFont()
    sub_font.setPointSize(10)
    painter.setFont(sub_font)
    painter.setPen(QColor("#6c7086"))
    painter.drawText(pix.rect().adjusted(0, 60, 0, 0), Qt.AlignmentFlag.AlignCenter, "Loading…")

    painter.end()
    return QSplashScreen(pix)


def main() -> None:
    _configure_logging()
    _install_excepthook()

    app = QApplication(sys.argv)
    app.setApplicationName("ttrpg-notes")
    app.setOrganizationName("ttrpg-notes")

    # Build the window (invisible) so we can position both it and the splash
    # at the same centred location before either is revealed.
    window = MainWindow()

    screen_geo = app.primaryScreen().availableGeometry()
    win_x = screen_geo.x() + (screen_geo.width() - _WIN_W) // 2
    win_y = screen_geo.y() + (screen_geo.height() - _WIN_H) // 2
    window.move(win_x, win_y)

    splash = _make_splash()
    splash.move(
        win_x + (_WIN_W - splash.width()) // 2,
        win_y + (_WIN_H - splash.height()) // 2,
    )
    splash.show()
    app.processEvents()

    run_startup(window)

    window.show()
    splash.finish(window)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
