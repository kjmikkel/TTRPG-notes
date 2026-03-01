from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics
from PySide6.QtWidgets import (
    QApplication,
    QInputDialog,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
)

from ttrpg_notes.models.campaign import Campaign, Session

_ROLE_SESSION_ID = 256
_ROLE_DIRTY = 257


class _DirtyDelegate(QStyledItemDelegate):
    """Draws a red superscript '*' after the label of dirty sessions."""

    def paint(self, painter, option, index) -> None:
        super().paint(painter, option, index)
        if not index.data(_ROLE_DIRTY):
            return

        painter.save()

        text = index.data(Qt.DisplayRole) or ""
        fm = QFontMetrics(option.font)

        # Resolve the precise rect that the default delegate used for text.
        style_opt = QStyleOptionViewItem(option)
        self.initStyleOption(style_opt, index)
        w = option.widget
        style = w.style() if w else QApplication.style()
        text_rect = style.subElementRect(QStyle.SE_ItemViewItemText, style_opt, w)

        # Superscript: ~65 % of normal size, red, drawn near the top of the row.
        sup_font = QFont(option.font)
        sup_font.setPointSizeF(max(6.0, option.font.pointSizeF() * 0.65))
        sup_fm = QFontMetrics(sup_font)

        x = text_rect.x() + fm.horizontalAdvance(text) + 2
        y = text_rect.y() + sup_fm.ascent() + 1

        painter.setFont(sup_font)
        painter.setPen(QColor("red"))
        painter.drawText(x, y, "*")

        painter.restore()


def _session_label(session: Session, date_format: str) -> str:
    """Return display label: '[name] - [date]' | '[date]' | 'Session N'."""
    from PySide6.QtCore import QDate

    date_str = ""
    if session.date:
        d = QDate.fromString(session.date, "yyyy-MM-dd")
        if d.isValid():
            date_str = d.toString(date_format)

    if session.name and date_str:
        return f"{session.name} - {date_str}"
    if session.name:
        return session.name
    if date_str:
        return date_str
    return f"Session {session.number}"


class SessionList(QListWidget):
    """Left-panel list of sessions."""

    session_selected = Signal(object)  # Session | None
    session_renamed = Signal(object)   # Session
    session_deleted = Signal(object)   # Session

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._campaign: Campaign | None = None
        self.currentItemChanged.connect(self._on_item_changed)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self.setItemDelegate(_DirtyDelegate(self))

    def load_campaign(self, campaign: Campaign) -> None:
        self._campaign = campaign
        self.refresh()

    def refresh(self) -> None:
        if self._campaign is None:
            self.clear()
            return
        current_id = self._current_session_id()
        self.blockSignals(True)
        self.clear()
        for session in self._campaign.sessions:
            label = _session_label(session, self._campaign.date_format)
            item = QListWidgetItem(label)
            item.setData(_ROLE_SESSION_ID, session.id)
            item.setData(_ROLE_DIRTY, session.dirty)
            self.addItem(item)
        self.blockSignals(False)
        if current_id:
            self._select_by_id(current_id)
        elif self.count() > 0:
            self.setCurrentRow(self.count() - 1)

    def select_session(self, session: Session) -> None:
        self._select_by_id(session.id)

    def _select_by_id(self, session_id: str) -> None:
        for i in range(self.count()):
            if self.item(i).data(256) == session_id:
                self.setCurrentRow(i)
                return

    def _current_session_id(self) -> str | None:
        item = self.currentItem()
        return item.data(_ROLE_SESSION_ID) if item else None

    def _on_item_changed(self, current: QListWidgetItem | None, _prev) -> None:
        if self._campaign is None or current is None:
            self.session_selected.emit(None)
            return
        sid = current.data(256)
        for session in self._campaign.sessions:
            if session.id == sid:
                self.session_selected.emit(session)
                return
        self.session_selected.emit(None)

    def refresh_dirty(self) -> None:
        """Update only the dirty indicators without rebuilding the list."""
        if self._campaign is None:
            return
        by_id = {s.id: s for s in self._campaign.sessions}
        for i in range(self.count()):
            item = self.item(i)
            if item:
                session = by_id.get(item.data(_ROLE_SESSION_ID))
                if session is not None:
                    item.setData(_ROLE_DIRTY, session.dirty)
        self.viewport().update()

    # ------------------------------------------------------------------
    # Context menu — rename / delete
    # ------------------------------------------------------------------

    def _show_context_menu(self, pos) -> None:
        item = self.itemAt(pos)
        if item is None or self._campaign is None:
            return
        sid = item.data(_ROLE_SESSION_ID)
        session = next((s for s in self._campaign.sessions if s.id == sid), None)
        if session is None:
            return

        menu = QMenu(self)
        rename_action = menu.addAction("Rename…")
        delete_action = menu.addAction("Delete")
        action = menu.exec(self.viewport().mapToGlobal(pos))

        if action == rename_action:
            self._rename_session(session)
        elif action == delete_action:
            self._delete_session(session)

    def _rename_session(self, session: Session) -> None:
        name, ok = QInputDialog.getText(
            self,
            "Rename Session",
            "Session name (leave empty to clear):",
            text=session.name or "",
        )
        if not ok:
            return
        session.name = name.strip() or None
        session.dirty = True
        self.refresh()
        self.session_renamed.emit(session)

    def _delete_session(self, session: Session) -> None:
        label = _session_label(session, self._campaign.date_format)
        resp = QMessageBox.question(
            self,
            "Delete Session",
            f"Permanently delete '{label}'?\nThis cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if resp != QMessageBox.Yes:
            return
        self._campaign.sessions.remove(session)
        self.refresh()
        self.session_deleted.emit(session)
