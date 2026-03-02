from __future__ import annotations

import re

from PySide6.QtGui import QColor, QSyntaxHighlighter, QTextCharFormat, QTextDocument

from ttrpg_notes.ui.spellcheck.checker import SpellChecker

_WORD_RE = re.compile(r"\b[a-zA-Z''\u2019]+\b")


def _make_error_format() -> QTextCharFormat:
    fmt = QTextCharFormat()
    fmt.setUnderlineColor(QColor("red"))
    fmt.setUnderlineStyle(QTextCharFormat.UnderlineStyle.SpellCheckUnderline)
    return fmt


class SpellHighlighter(QSyntaxHighlighter):
    """Highlights misspelled words with a red wavy underline."""

    def __init__(self, document: QTextDocument, checker: SpellChecker) -> None:
        super().__init__(document)
        self._checker = checker
        self._error_fmt = _make_error_format()
        # Disabled during active typing; re-enabled after a debounce pause.
        self._active = True

    def set_active(self, active: bool) -> None:
        self._active = active

    def highlightBlock(self, text: str) -> None:
        if not self._active:
            return
        for match in _WORD_RE.finditer(text):
            word = match.group()
            if not self._checker.check(word):
                self.setFormat(match.start(), len(word), self._error_fmt)

    def rehighlight_all(self) -> None:
        self._active = True
        self.rehighlight()
