from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QMessageBox

from ttrpg_notes.config import settings
from ttrpg_notes.ui.main_window import MainWindow


def run_startup(window: MainWindow) -> None:
    """
    Check QSettings for a last campaign path.
    If the file exists → load it.
    Otherwise → ask the user whether to create a new campaign or open one.
    """
    last = settings.get_last_campaign_path()
    if last and Path(last).exists():
        window.load_campaign(last)
        return

    msg = QMessageBox(window)
    msg.setWindowTitle("Welcome to TTRPG Notes")
    msg.setText("No campaign is loaded. What would you like to do?")
    new_btn = msg.addButton("New Campaign…", QMessageBox.AcceptRole)
    open_btn = msg.addButton("Open Campaign…", QMessageBox.AcceptRole)
    msg.addButton("Start Empty", QMessageBox.RejectRole)
    msg.exec()

    clicked = msg.clickedButton()
    if clicked is new_btn:
        window._action_new_campaign()
    elif clicked is open_btn:
        window._action_open()
