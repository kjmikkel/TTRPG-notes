from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)


_DATE_FORMATS = [
    ("yyyy-MM-dd", "2024-01-15"),
    ("MM/dd/yyyy", "01/15/2024"),
    ("dd/MM/yyyy", "15/01/2024"),
    ("MMMM d, yyyy", "January 15, 2024"),
    ("d MMMM yyyy", "15 January 2024"),
]


class NewCampaignDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Campaign")
        self.setMinimumWidth(350)

        outer = QVBoxLayout(self)
        form = QFormLayout()
        outer.addLayout(form)

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("My Campaign")
        form.addRow("Campaign name:", self._name_edit)

        self._fmt_combo = QComboBox()
        for fmt, example in _DATE_FORMATS:
            self._fmt_combo.addItem(f"{example}  ({fmt})", userData=fmt)
        form.addRow("Date format:", self._fmt_combo)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

    def _accept(self) -> None:
        if self._name_edit.text().strip():
            self.accept()

    @property
    def campaign_name(self) -> str:
        return self._name_edit.text().strip()

    @property
    def date_format(self) -> str:
        return str(self._fmt_combo.currentData())
