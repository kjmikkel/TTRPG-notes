from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)


class NewPlayerDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Player")
        self.setMinimumWidth(300)

        outer = QVBoxLayout(self)
        form = QFormLayout()
        outer.addLayout(form)

        self._player_edit = QLineEdit()
        self._player_edit.setPlaceholderText("Alice")
        form.addRow("Player name:", self._player_edit)

        self._char_edit = QLineEdit()
        self._char_edit.setPlaceholderText("Ragna")
        form.addRow("Initial character:", self._char_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

    def _accept(self) -> None:
        if self._player_edit.text().strip():
            self.accept()

    @property
    def player_name(self) -> str:
        return self._player_edit.text().strip()

    @property
    def character_name(self) -> str:
        return self._char_edit.text().strip() or "Character 1"
