from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt, QPoint, QTimer, Signal
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QMenu,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ttrpg_notes.config import settings
from ttrpg_notes.models.campaign import Session
from ttrpg_notes.ui.collapsible import CollapsibleSection

if TYPE_CHECKING:
    from ttrpg_notes.ui.spellcheck.highlighter import SpellHighlighter


def _make_editor() -> QTextEdit:
    editor = QTextEdit()
    editor.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    editor.setMinimumHeight(80)
    return editor


class _TextSection(CollapsibleSection):
    """CollapsibleSection that embeds a QTextEdit as its body."""

    def __init__(self, title: str, expanded: bool, parent: QWidget | None = None) -> None:
        self._editor = _make_editor()
        super().__init__(title, self._editor, expanded=expanded, parent=parent)

    @property
    def editor(self) -> QTextEdit:
        return self._editor


class SummaryEditor(QWidget):
    """
    Center panel: Pre-Session Notes / Session Notes / Post-Session Notes.

    All three sections are collapsible.  The open/closed state of each
    section is global (persisted via QSettings) so that navigating between
    sessions does not change which panels are open.
    """

    text_changed_by_user = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._session: Session | None = None
        self._updating = False
        self._highlighters: list[SpellHighlighter] = []
        self._ctx_editor: QTextEdit | None = None
        self._custom_context_active = False

        pre_exp = settings.get_section_expanded("pre", False)
        sum_exp = settings.get_section_expanded("summary", True)
        post_exp = settings.get_section_expanded("post", False)

        self._pre = _TextSection("Pre-Session Notes", pre_exp)
        self._summary = _TextSection("Session Notes", sum_exp)
        self._post = _TextSection("Post-Session Notes", post_exp)

        self._pre.editor.setPlaceholderText("Pre-session notes\u2026")
        self._summary.editor.setPlaceholderText("Session notes\u2026")
        self._post.editor.setPlaceholderText("Post-session notes\u2026")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._pre)
        layout.addWidget(self._summary)
        layout.addWidget(self._post)

        self._pre.toggled.connect(lambda v: settings.set_section_expanded("pre", v))
        self._summary.toggled.connect(lambda v: settings.set_section_expanded("summary", v))
        self._post.toggled.connect(lambda v: settings.set_section_expanded("post", v))

        self._pre.editor.textChanged.connect(self._on_pre_changed)
        self._summary.editor.textChanged.connect(self._on_summary_changed)
        self._post.editor.textChanged.connect(self._on_post_changed)

        for section in (self._pre, self._summary, self._post):
            section.editor.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            section.editor.customContextMenuRequested.connect(
                lambda pos, e=section.editor: self._forward_context_menu(e, pos)
            )

        self._highlight_timer = QTimer(self)
        self._highlight_timer.setSingleShot(True)
        self._highlight_timer.setInterval(400)
        self._highlight_timer.timeout.connect(self._on_highlight_timer)

    def setContextMenuPolicy(self, policy: Qt.ContextMenuPolicy) -> None:
        self._custom_context_active = (policy == Qt.ContextMenuPolicy.CustomContextMenu)

    def _forward_context_menu(self, editor: QTextEdit, pos: QPoint) -> None:
        self._ctx_editor = editor
        if self._custom_context_active:
            self.customContextMenuRequested.emit(pos)
        else:
            editor.createStandardContextMenu().exec(
                editor.viewport().mapToGlobal(pos)
            )

    def cursorForPosition(self, pos: QPoint) -> QTextCursor:
        return (self._ctx_editor or self._summary.editor).cursorForPosition(pos)

    def viewport(self) -> QWidget:
        return (self._ctx_editor or self._summary.editor).viewport()

    def createStandardContextMenu(self) -> QMenu:
        return (self._ctx_editor or self._summary.editor).createStandardContextMenu()

    def attach_highlighter(self, highlighter_cls: type[Any]) -> object:
        """Attach a SpellHighlighter to all three editors; returns the first."""
        self._highlighters.clear()
        for section in (self._pre, self._summary, self._post):
            h: SpellHighlighter = highlighter_cls(section.editor.document())
            self._highlighters.append(h)
        return self._highlighters[0] if self._highlighters else None

    def rehighlight(self) -> None:
        """Force an immediate re-highlight (e.g. after adding a word to the dictionary)."""
        self._highlight_timer.stop()
        for h in self._highlighters:
            h.rehighlight_all()

    def _on_highlight_timer(self) -> None:
        for h in self._highlighters:
            h.rehighlight_all()

    def _debounce_highlight(self) -> None:
        for h in self._highlighters:
            h.set_active(False)
        self._highlight_timer.start()

    def load_session(self, session: Session | None) -> None:
        self._session = session
        self._updating = True
        enabled = session is not None
        if session is None:
            self._pre.editor.setPlainText("")
            self._summary.editor.setPlainText("")
            self._post.editor.setPlainText("")
        else:
            self._pre.editor.setPlainText(session.pre_notes)
            self._summary.editor.setPlainText(session.summary)
            self._post.editor.setPlainText(session.post_notes)
        for section in (self._pre, self._summary, self._post):
            section.editor.setEnabled(enabled)
        self._updating = False

    def _on_pre_changed(self) -> None:
        if self._updating or self._session is None:
            return
        new_text = self._pre.editor.toPlainText()
        if new_text == self._session.pre_notes:
            return
        self._session.pre_notes = new_text
        self._session.dirty = True
        self.text_changed_by_user.emit()
        self._debounce_highlight()

    def _on_summary_changed(self) -> None:
        if self._updating or self._session is None:
            return
        new_text = self._summary.editor.toPlainText()
        if new_text == self._session.summary:
            return
        self._session.summary = new_text
        self._session.dirty = True
        self.text_changed_by_user.emit()
        self._debounce_highlight()

    def _on_post_changed(self) -> None:
        if self._updating or self._session is None:
            return
        new_text = self._post.editor.toPlainText()
        if new_text == self._session.post_notes:
            return
        self._session.post_notes = new_text
        self._session.dirty = True
        self.text_changed_by_user.emit()
        self._debounce_highlight()
