from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtCore import QLocale
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ttrpg_notes.models.campaign import Campaign

_DATE_PRESETS: list[tuple[str, str]] = [
    ("yyyy-MM-dd", "2024-01-15"),
    ("MM/dd/yyyy", "01/15/2024"),
    ("dd/MM/yyyy", "15/01/2024"),
    ("MMMM d, yyyy", "January 15, 2024"),
    ("d MMMM yyyy", "15 January 2024"),
]


class _Fold(QWidget):
    """Collapsible section with a toggle button header."""

    def __init__(self, title: str, parent=None) -> None:
        super().__init__(parent)
        self._title = title

        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)

        self._toggle = QPushButton(f"▶ {title}")
        self._toggle.setFlat(True)
        self._toggle.setCheckable(True)
        self._toggle.setStyleSheet(
            "QPushButton { text-align: left; font-weight: bold; padding: 4px 2px; }"
        )
        self._toggle.toggled.connect(self._on_toggled)
        vbox.addWidget(self._toggle)

        self._body = QWidget()
        self._body.hide()
        self._body_layout = QVBoxLayout(self._body)
        self._body_layout.setContentsMargins(16, 4, 0, 8)
        vbox.addWidget(self._body)

    def body_layout(self) -> QVBoxLayout:
        return self._body_layout

    def _on_toggled(self, checked: bool) -> None:
        self._body.setVisible(checked)
        self._toggle.setText(f"{'▼' if checked else '▶'} {self._title}")


class OptionsDialog(QDialog):
    """
    Options dialog: date format, active dictionary, custom word lists.

    After exec(), check:
    - new_date_format  (str | None) — set if user changed the format
    - new_dict_path    (Path | None) — set if user downloaded a new dictionary
    """

    def __init__(
        self,
        campaign: Campaign | None,
        checker,
        rehighlight_fn: Callable[[], None],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._campaign = campaign
        self._checker = checker
        self._rehighlight = rehighlight_fn
        self.new_date_format: str | None = None
        self.new_dict_path: Path | None = None
        self.dict_deleted: bool = False

        self.setWindowTitle("Options")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)

        outer = QVBoxLayout(self)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        content = QWidget()
        self._vbox = QVBoxLayout(content)
        self._vbox.setSpacing(12)
        scroll.setWidget(content)
        outer.addWidget(scroll)

        self._build_date_format()
        self._build_dictionary()

        if checker is not None:
            self._build_word_fold(
                "Custom Dictionary",
                get_fn=checker.words,
                add_fn=checker.add_to_dictionary,
                remove_fn=checker.remove_from_dictionary,
                update_fn=checker.update_in_dictionary,
            )
            self._build_word_fold(
                "Ignore List",
                get_fn=checker.ignored_words,
                add_fn=checker.add_to_ignore,
                remove_fn=checker.remove_from_ignore,
                update_fn=checker.update_in_ignore,
            )
        else:
            note = QLabel("No dictionary loaded — word lists unavailable.")
            note.setEnabled(False)
            self._vbox.addWidget(note)

        self._vbox.addStretch()

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

    # ------------------------------------------------------------------
    # Date format
    # ------------------------------------------------------------------

    def _build_date_format(self) -> None:
        group = QGroupBox("Date Format")
        vbox = QVBoxLayout(group)

        sys_fmt = QLocale.system().dateFormat(QLocale.FormatType.ShortFormat)

        # Build (label, format_string) pairs; "CUSTOM" is a sentinel
        self._fmt_items: list[tuple[str, str]] = [
            (f"System Default  ({sys_fmt})", sys_fmt),
        ]
        for fmt, example in _DATE_PRESETS:
            self._fmt_items.append((f"{example}  ({fmt})", fmt))
        self._fmt_items.append(("Custom…", "CUSTOM"))

        self._fmt_combo = QComboBox()
        for label, _ in self._fmt_items:
            self._fmt_combo.addItem(label)

        current_fmt = self._campaign.date_format if self._campaign else ""
        matched_idx = 0
        for i, (_, fmt) in enumerate(self._fmt_items):
            if fmt == current_fmt and fmt != "CUSTOM":
                matched_idx = i
                break
        else:
            # No preset matched — select Custom and pre-fill
            matched_idx = len(self._fmt_items) - 1

        self._fmt_combo.setCurrentIndex(matched_idx)
        self._fmt_combo.currentIndexChanged.connect(self._on_fmt_changed)
        vbox.addWidget(self._fmt_combo)

        self._custom_edit = QLineEdit()
        self._custom_edit.setPlaceholderText("Qt date format string, e.g. dd-MM-yyyy")
        is_custom = self._fmt_items[matched_idx][1] == "CUSTOM"
        self._custom_edit.setText(current_fmt if is_custom else "")
        self._custom_edit.setVisible(is_custom)
        vbox.addWidget(self._custom_edit)

        self._vbox.addWidget(group)

    def _on_fmt_changed(self, idx: int) -> None:
        is_custom = self._fmt_items[idx][1] == "CUSTOM"
        self._custom_edit.setVisible(is_custom)

    def _selected_date_format(self) -> str:
        idx = self._fmt_combo.currentIndex()
        _, fmt = self._fmt_items[idx]
        if fmt == "CUSTOM":
            return self._custom_edit.text().strip()
        return fmt

    # ------------------------------------------------------------------
    # Dictionary
    # ------------------------------------------------------------------

    def _build_dictionary(self) -> None:
        group = QGroupBox("Dictionary")
        hbox = QHBoxLayout(group)

        self._dict_label = QLabel()
        self._refresh_dict_label()
        hbox.addWidget(self._dict_label, 1)

        btn = QPushButton("Manage Dictionaries…")
        btn.clicked.connect(self._manage_dicts)
        hbox.addWidget(btn)

        self._vbox.addWidget(group)

    def _refresh_dict_label(self) -> None:
        dict_dir = Path.home() / ".ttrpg_notes" / "dicts"
        dic_files = sorted(dict_dir.glob("*.dic")) if dict_dir.exists() else []
        names = ", ".join(f.stem for f in dic_files) if dic_files else "None"
        self._dict_label.setText(f"Downloaded: {names}")

    def _manage_dicts(self) -> None:
        from ttrpg_notes.ui.spellcheck.downloader import DownloaderDialog

        dict_dir = Path.home() / ".ttrpg_notes" / "dicts"
        dlg = DownloaderDialog(dict_dir, self)
        dlg.downloaded.connect(lambda p: setattr(self, "new_dict_path", p))
        dlg.deleted.connect(self._on_dict_deleted)
        dlg.exec()
        self._refresh_dict_label()

    def _on_dict_deleted(self, _stem: str) -> None:
        self.dict_deleted = True

    # ------------------------------------------------------------------
    # Word list folds (custom dict / ignore list)
    # ------------------------------------------------------------------

    def _build_word_fold(
        self, title: str, get_fn, add_fn, remove_fn, update_fn
    ) -> None:
        fold = _Fold(title)
        fold.body_layout().addWidget(
            self._make_word_editor(get_fn, add_fn, remove_fn, update_fn)
        )
        self._vbox.addWidget(fold)

    def _make_word_editor(self, get_fn, add_fn, remove_fn, update_fn) -> QWidget:
        widget = QWidget()
        hbox = QHBoxLayout(widget)
        hbox.setContentsMargins(0, 0, 0, 0)

        lst = QListWidget()
        lst.setMaximumHeight(160)
        for word in get_fn():
            lst.addItem(word)
        hbox.addWidget(lst, 1)

        def refresh() -> None:
            lst.clear()
            for word in get_fn():
                lst.addItem(word)
            self._rehighlight()

        def add() -> None:
            word, ok = QInputDialog.getText(widget, "Add Word", "Word:")
            word = word.strip()
            if ok and word:
                add_fn(word)
                refresh()

        def edit() -> None:
            item = lst.currentItem()
            if not item:
                return
            old = item.text()
            word, ok = QInputDialog.getText(widget, "Edit Word", "Word:", text=old)
            word = word.strip()
            if ok and word and word != old:
                update_fn(old, word)
                refresh()

        def delete() -> None:
            item = lst.currentItem()
            if not item:
                return
            remove_fn(item.text())
            refresh()

        btn_col = QVBoxLayout()
        for label, fn in [("Add", add), ("Edit", edit), ("Delete", delete)]:
            btn = QPushButton(label)
            btn.clicked.connect(fn)
            btn_col.addWidget(btn)
        btn_col.addStretch()
        hbox.addLayout(btn_col)

        return widget

    # ------------------------------------------------------------------
    # OK
    # ------------------------------------------------------------------

    def _on_ok(self) -> None:
        if self._campaign is not None:
            new_fmt = self._selected_date_format()
            if new_fmt and new_fmt != self._campaign.date_format:
                self.new_date_format = new_fmt
        self.accept()
