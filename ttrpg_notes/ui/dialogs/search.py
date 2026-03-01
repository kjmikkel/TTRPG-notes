from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
)

from ttrpg_notes.models.campaign import Campaign, Session


class SearchDialog(QDialog):
    """Non-modal search dialog; emits session_selected when user clicks a result."""

    session_selected = Signal(object)  # Session

    def __init__(self, campaign: Campaign, parent=None) -> None:
        super().__init__(parent)
        self._campaign = campaign
        self.setWindowTitle("Search Sessions")
        self.setWindowFlag(Qt.WindowStaysOnTopHint, False)
        self.setMinimumWidth(400)
        self.setMinimumHeight(300)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Search sessions (name or summary):"))

        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Type to filter…")
        self._search_edit.textChanged.connect(self._update_results)
        layout.addWidget(self._search_edit)

        self._results = QListWidget()
        self._results.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self._results)

        self._update_results("")

    def _update_results(self, query: str) -> None:
        self._results.clear()
        q = query.lower()
        for session in self._campaign.sessions:
            name = session.name or ""
            if q in name.lower() or q in session.summary.lower():
                label = session.name or session.date or f"Session {session.number}"
                item = QListWidgetItem(label)
                item.setData(256, session.id)
                self._results.addItem(item)

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        sid = item.data(256)
        for session in self._campaign.sessions:
            if session.id == sid:
                self.session_selected.emit(session)
                break
