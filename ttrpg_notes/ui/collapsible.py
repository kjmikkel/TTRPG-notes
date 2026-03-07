from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QPushButton, QSizePolicy, QVBoxLayout, QWidget


class CollapsibleSection(QWidget):
    """
    Generic collapsible section with a titled toggle button.

    Pass any QWidget as *body*; it will be shown/hidden when the toggle
    button is clicked.  The section shrinks to toggle-button height when
    collapsed.

    Signals:
        toggled(bool) — emitted when the expanded state changes (True = open).
    """

    toggled = Signal(bool)

    def __init__(
        self,
        title: str,
        body: QWidget,
        *,
        expanded: bool = True,
        toggle_style: str = (
            "QPushButton { text-align: left; font-weight: bold; padding: 2px 4px; }"
        ),
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._title = title
        self._body = body

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._toggle = QPushButton()
        self._toggle.setFlat(True)
        self._toggle.setCheckable(True)
        self._toggle.setStyleSheet(toggle_style)
        layout.addWidget(self._toggle)
        layout.addWidget(body)

        # Apply initial state without emitting the toggled signal.
        self._toggle.blockSignals(True)
        self._toggle.setChecked(expanded)
        self._toggle.blockSignals(False)
        self._apply_state(expanded)

        self._toggle.toggled.connect(self._on_toggled)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def is_expanded(self) -> bool:
        return self._toggle.isChecked()

    def set_expanded(self, expanded: bool) -> None:
        if self._toggle.isChecked() != expanded:
            self._toggle.setChecked(expanded)
        else:
            # Signal won't fire if value is unchanged; apply state manually.
            self._apply_state(expanded)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _on_toggled(self, checked: bool) -> None:
        self._apply_state(checked)
        self.toggled.emit(checked)

    def _apply_state(self, expanded: bool) -> None:
        self._body.setVisible(expanded)
        arrow = "▼" if expanded else "▶"
        self._toggle.setText(f"{arrow}  {self._title}")
        v_policy = QSizePolicy.Policy.Expanding if expanded else QSizePolicy.Policy.Fixed
        self.setSizePolicy(QSizePolicy.Policy.Expanding, v_policy)
