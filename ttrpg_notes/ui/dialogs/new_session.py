from __future__ import annotations

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)


class NewSessionDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Session")
        self.setMinimumWidth(300)

        outer = QVBoxLayout(self)
        form = QFormLayout()
        outer.addLayout(form)

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("Optional session name")
        form.addRow("Session name:", self._name_edit)

        self._date_edit = QDateEdit(QDate.currentDate())
        self._date_edit.setCalendarPopup(True)
        self._date_edit.setDisplayFormat("yyyy-MM-dd")
        form.addRow("Date:", self._date_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

    @property
    def session_name(self) -> str | None:
        text = self._name_edit.text().strip()
        return text if text else None

    @property
    def session_date(self) -> str:
        return self._date_edit.date().toString("yyyy-MM-dd")
