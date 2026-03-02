from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QWidget,
)

from ttrpg_notes.models.campaign import Kill


class KillEntry(QWidget):
    """
    A single kill row for the current session (editable).
    Emits count_changed(kill), name_changed(kill), and remove_requested(kill).
    """

    count_changed = Signal(object)    # Kill
    name_changed = Signal(object)     # Kill
    remove_requested = Signal(object) # Kill

    def __init__(self, kill: Kill, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.kill = kill

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._name_edit = QLineEdit(kill.being)
        self._name_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._name_edit.editingFinished.connect(self._on_name_changed)

        self._count_btn = QPushButton(str(kill.count))
        self._count_btn.setFixedWidth(40)
        self._count_btn.setToolTip("Click to add 1 kill")
        self._count_btn.clicked.connect(self._increment)

        self._remove_btn = QPushButton("X")
        self._remove_btn.setFixedWidth(28)
        self._remove_btn.setToolTip("Remove 1 kill (removes row at 0)")
        self._remove_btn.clicked.connect(self._decrement)

        layout.addWidget(self._name_edit)
        layout.addWidget(self._count_btn)
        layout.addWidget(self._remove_btn)

    def _on_name_changed(self) -> None:
        new_name = self._name_edit.text().strip()
        if not new_name:
            self._name_edit.setText(self.kill.being)
            return
        if new_name != self.kill.being:
            self.kill.being = new_name
            self.name_changed.emit(self.kill)

    def _increment(self) -> None:
        self.kill.count += 1
        self._count_btn.setText(str(self.kill.count))
        self.count_changed.emit(self.kill)

    def _decrement(self) -> None:
        self.kill.count -= 1
        if self.kill.count <= 0:
            self.remove_requested.emit(self.kill)
        else:
            self._count_btn.setText(str(self.kill.count))
            self.count_changed.emit(self.kill)


class ReadonlyKillEntry(QWidget):
    """A single kill row for previous sessions (read-only label)."""

    def __init__(self, being: str, count: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        name_label = QLabel(being)
        name_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        name_label.setEnabled(False)

        count_label = QLabel(str(count))
        count_label.setFixedWidth(40)
        count_label.setEnabled(False)

        layout.addWidget(name_label)
        layout.addWidget(count_label)
