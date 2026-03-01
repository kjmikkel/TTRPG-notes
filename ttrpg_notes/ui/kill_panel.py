from __future__ import annotations

from collections import defaultdict

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QLineEdit,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ttrpg_notes.models.campaign import Campaign, Character, Kill, Player, Session
from ttrpg_notes.ui.kill_entry import KillEntry, ReadonlyKillEntry


def _character_total_kills(campaign: Campaign, character_id: str, up_to_idx: int) -> int:
    """Sum kills for a character across sessions 0..up_to_idx (inclusive)."""
    return sum(
        k.count
        for s in campaign.sessions[: up_to_idx + 1]
        for k in s.kills.get(character_id, [])
    )


def _player_total_kills(campaign: Campaign, player: Player, up_to_idx: int) -> int:
    return sum(_character_total_kills(campaign, c.id, up_to_idx) for c in player.characters)


class CharacterKillSection(QWidget):
    """
    UI block for a single character within the kill panel.
    Shows header with total kills, readonly rows from prior sessions,
    editable rows for the current session, and an "Add kill" input.
    """

    session_dirty = Signal()

    def __init__(
        self,
        character: Character,
        campaign: Campaign,
        current_session: Session,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._character = character
        self._current_session = current_session
        self._campaign = campaign
        self._current_idx = next(
            (i for i, s in enumerate(campaign.sessions) if s.id == current_session.id),
            len(campaign.sessions) - 1,
        )

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(4, 4, 4, 4)
        self._layout.setSpacing(2)

        # Header
        self._header_label = QLabel()
        self._header_label.setStyleSheet("font-weight: bold;")
        self._layout.addWidget(self._header_label)

        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        self._layout.addWidget(line)

        # Readonly rows (previous sessions aggregated)
        self._build_readonly_rows()

        # Editable rows (current session)
        self._editable_widgets: list[tuple[Kill, KillEntry]] = []
        self._build_editable_rows()

        # Add-kill input
        self._add_input = QLineEdit()
        self._add_input.setPlaceholderText("Type being name, press Enter…")
        self._add_input.returnPressed.connect(self._add_kill)
        self._layout.addWidget(self._add_input)

        self._update_header()

    # ------------------------------------------------------------------
    # Building rows
    # ------------------------------------------------------------------

    def _build_readonly_rows(self) -> None:
        """Aggregate kills from all sessions before the current one."""
        totals: dict[str, int] = defaultdict(int)
        for session in self._campaign.sessions[: self._current_idx]:
            for kill in session.kills.get(self._character.id, []):
                totals[kill.being] += kill.count

        for being, count in sorted(totals.items()):
            self._layout.addWidget(ReadonlyKillEntry(being, count))

    def _build_editable_rows(self) -> None:
        for kill in self._current_session.kills.get(self._character.id, []):
            self._add_editable_row(kill)

    def _add_editable_row(self, kill: Kill) -> None:
        entry = KillEntry(kill)
        entry.count_changed.connect(self._on_kill_changed)
        entry.name_changed.connect(self._on_kill_changed)
        entry.remove_requested.connect(self._remove_kill)
        # Insert before the add-input (last widget in layout)
        self._layout.insertWidget(self._layout.count() - 1, entry)
        self._editable_widgets.append((kill, entry))

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def _add_kill(self) -> None:
        being = self._add_input.text().strip()
        if not being:
            return
        self._add_input.clear()

        kill = Kill(being=being, count=1)
        self._current_session.kills.setdefault(self._character.id, []).append(kill)
        self._current_session.dirty = True

        self._add_editable_row(kill)
        self._update_header()
        self.session_dirty.emit()

    def _on_kill_changed(self, _kill: Kill) -> None:
        self._current_session.dirty = True
        self._update_header()
        self.session_dirty.emit()

    def _remove_kill(self, kill: Kill) -> None:
        char_kills = self._current_session.kills.get(self._character.id, [])
        if kill in char_kills:
            char_kills.remove(kill)
        self._current_session.dirty = True

        for stored_kill, widget in list(self._editable_widgets):
            if stored_kill is kill:
                widget.setParent(None)
                widget.deleteLater()
                self._editable_widgets.remove((stored_kill, widget))
                break

        self._update_header()
        self.session_dirty.emit()

    # ------------------------------------------------------------------
    # Header
    # ------------------------------------------------------------------

    def _update_header(self) -> None:
        total = _character_total_kills(self._campaign, self._character.id, self._current_idx)
        self._header_label.setText(f"  {self._character.name}  (Total: {total})")


class KillPanel(QScrollArea):
    """Right panel: scrollable area with per-character kill sections."""

    session_dirty = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self._container = QWidget()
        self._vbox = QVBoxLayout(self._container)
        self._vbox.setContentsMargins(4, 4, 4, 4)
        self._vbox.addStretch()
        self.setWidget(self._container)

        # All widgets we insert dynamically (player labels + sections)
        self._dynamic: list[QWidget] = []
        self._campaign: Campaign | None = None
        self._session: Session | None = None

    def load_session(self, campaign: Campaign, session: Session | None) -> None:
        self._campaign = campaign
        self._session = session
        self._rebuild()

    def _clear(self) -> None:
        for widget in self._dynamic:
            widget.setParent(None)
            widget.deleteLater()
        self._dynamic.clear()

    def _insert(self, widget: QWidget) -> None:
        """Insert widget before the trailing stretch."""
        self._vbox.insertWidget(self._vbox.count() - 1, widget)
        self._dynamic.append(widget)

    def _rebuild(self) -> None:
        self._clear()
        if self._campaign is None or self._session is None:
            return

        current_idx = next(
            (i for i, s in enumerate(self._campaign.sessions) if s.id == self._session.id),
            len(self._campaign.sessions) - 1,
        )

        for player in self._campaign.players:
            multi_char = len(player.characters) > 1
            if multi_char:
                total = _player_total_kills(self._campaign, player, current_idx)
                player_text = f"▸ {player.name} ({total})"
            else:
                player_text = f"▸ {player.name}"

            player_label = QLabel(player_text)
            player_label.setStyleSheet("font-weight: bold; margin-top: 6px;")
            self._insert(player_label)

            for character in player.characters:
                section = CharacterKillSection(
                    character, self._campaign, self._session
                )
                section.session_dirty.connect(self.session_dirty)
                self._insert(section)
