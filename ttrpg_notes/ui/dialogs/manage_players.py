from __future__ import annotations

import uuid

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QInputDialog,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from ttrpg_notes.models.campaign import Campaign, Character, Player

# UserRole tags stored on each tree item
_ROLE = Qt.UserRole


class ManagePlayersDialog(QDialog):
    """
    View/add/rename/delete players and characters.
    Modifies campaign.players in-place.
    After exec(), check .changed to know if a save is needed.
    """

    def __init__(self, campaign: Campaign, parent=None) -> None:
        super().__init__(parent)
        self._campaign = campaign
        self.changed = False

        self.setWindowTitle("Manage Players & Characters")
        self.setMinimumSize(380, 380)

        layout = QVBoxLayout(self)

        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setSelectionMode(QTreeWidget.SingleSelection)
        self._tree.currentItemChanged.connect(self._update_buttons)
        layout.addWidget(self._tree)

        # Action buttons
        btn_row = QHBoxLayout()
        self._add_player_btn = QPushButton("Add Player")
        self._add_char_btn = QPushButton("Add Character")
        self._rename_btn = QPushButton("Rename")
        self._delete_btn = QPushButton("Delete")
        for b in (self._add_player_btn, self._add_char_btn, self._rename_btn, self._delete_btn):
            btn_row.addWidget(b)
        layout.addLayout(btn_row)

        self._add_player_btn.clicked.connect(self._add_player)
        self._add_char_btn.clicked.connect(self._add_character)
        self._rename_btn.clicked.connect(self._rename)
        self._delete_btn.clicked.connect(self._delete)

        close_buttons = QDialogButtonBox(QDialogButtonBox.Close)
        close_buttons.rejected.connect(self.accept)
        layout.addWidget(close_buttons)

        self._populate()
        self._update_buttons()

    # ------------------------------------------------------------------
    # Tree population
    # ------------------------------------------------------------------

    def _populate(self) -> None:
        selected_tag = self._selected_tag()
        self._tree.clear()

        for player in self._campaign.players:
            pi = QTreeWidgetItem([player.name])
            pi.setData(0, _ROLE, ("player", player.id))
            font = pi.font(0)
            font.setBold(True)
            pi.setFont(0, font)
            for char in player.characters:
                ci = QTreeWidgetItem([char.name])
                ci.setData(0, _ROLE, ("character", player.id, char.id))
                pi.addChild(ci)
            self._tree.addTopLevelItem(pi)

        self._tree.expandAll()

        # Restore selection
        if selected_tag:
            self._select_by_tag(selected_tag)

    def _selected_tag(self):
        item = self._tree.currentItem()
        return item.data(0, _ROLE) if item else None

    def _select_by_tag(self, tag) -> None:
        it = QTreeWidgetItem()  # dummy — just to iterate
        for i in range(self._tree.topLevelItemCount()):
            top = self._tree.topLevelItem(i)
            if top.data(0, _ROLE) == tag:
                self._tree.setCurrentItem(top)
                return
            for j in range(top.childCount()):
                child = top.child(j)
                if child.data(0, _ROLE) == tag:
                    self._tree.setCurrentItem(child)
                    return

    def _update_buttons(self) -> None:
        item = self._tree.currentItem()
        is_player = item is not None and item.parent() is None
        has_sel = item is not None
        self._add_char_btn.setEnabled(is_player)
        self._rename_btn.setEnabled(has_sel)
        self._delete_btn.setEnabled(has_sel)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _add_player(self) -> None:
        name, ok = QInputDialog.getText(self, "Add Player", "Player name:")
        name = name.strip()
        if not ok or not name:
            return
        self._campaign.players.append(Player(id=str(uuid.uuid4()), name=name))
        self.changed = True
        self._populate()

    def _add_character(self) -> None:
        item = self._tree.currentItem()
        if item is None or item.parent() is not None:
            return
        player = self._find_player(item.data(0, _ROLE)[1])
        if player is None:
            return
        name, ok = QInputDialog.getText(self, "Add Character", "Character name:")
        name = name.strip()
        if not ok or not name:
            return
        player.characters.append(Character(id=str(uuid.uuid4()), name=name))
        self.changed = True
        self._populate()

    def _rename(self) -> None:
        item = self._tree.currentItem()
        if item is None:
            return
        tag = item.data(0, _ROLE)
        if tag[0] == "player":
            player = self._find_player(tag[1])
            if player is None:
                return
            name, ok = QInputDialog.getText(self, "Rename Player", "New name:", text=player.name)
            name = name.strip()
            if not ok or not name:
                return
            player.name = name
        else:
            player = self._find_player(tag[1])
            char = self._find_character(player, tag[2]) if player else None
            if char is None:
                return
            name, ok = QInputDialog.getText(
                self, "Rename Character", "New name:", text=char.name
            )
            name = name.strip()
            if not ok or not name:
                return
            char.name = name
        self.changed = True
        self._populate()

    def _delete(self) -> None:
        item = self._tree.currentItem()
        if item is None:
            return
        tag = item.data(0, _ROLE)
        if tag[0] == "player":
            player = self._find_player(tag[1])
            if player is None:
                return
            resp = QMessageBox.question(
                self,
                "Delete Player",
                f"Delete player '{player.name}' and all their characters?\n"
                "Kill data recorded against their characters will be orphaned.",
                QMessageBox.Yes | QMessageBox.No,
            )
            if resp != QMessageBox.Yes:
                return
            self._campaign.players.remove(player)
        else:
            player = self._find_player(tag[1])
            char = self._find_character(player, tag[2]) if player else None
            if char is None:
                return
            resp = QMessageBox.question(
                self,
                "Delete Character",
                f"Delete character '{char.name}'?\n"
                "Kill data recorded for this character will be orphaned.",
                QMessageBox.Yes | QMessageBox.No,
            )
            if resp != QMessageBox.Yes:
                return
            player.characters.remove(char)  # type: ignore[union-attr]

        self.changed = True
        self._populate()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _find_player(self, player_id: str) -> Player | None:
        return next((p for p in self._campaign.players if p.id == player_id), None)

    def _find_character(self, player: Player | None, char_id: str) -> Character | None:
        if player is None:
            return None
        return next((c for c in player.characters if c.id == char_id), None)
