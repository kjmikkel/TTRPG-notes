from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGroupBox,
    QMessageBox,
    QRadioButton,
    QVBoxLayout,
)

from ttrpg_notes.models.campaign import Campaign

_log = logging.getLogger(__name__)


class ExportDialog(QDialog):
    """
    Export campaign to plain text or Homebrewery-compatible Markdown.

    Mandatory sections: campaign name, session names, session notes.
    Optional sections (controlled by checkboxes): kill counts per session,
    pre-session notes, post-session notes, total kill count.
    """

    def __init__(self, campaign: Campaign, parent=None) -> None:
        super().__init__(parent)
        self._campaign = campaign
        self.setWindowTitle("Export Campaign")
        self.setMinimumWidth(360)

        layout = QVBoxLayout(self)

        # --- Format selection ---
        fmt_group = QGroupBox("Format")
        fmt_layout = QVBoxLayout(fmt_group)
        self._txt_radio = QRadioButton("Plain text  (.txt)")
        self._md_radio = QRadioButton("Markdown — Homebrewery-compatible  (.md)")
        self._txt_radio.setChecked(True)
        fmt_layout.addWidget(self._txt_radio)
        fmt_layout.addWidget(self._md_radio)
        layout.addWidget(fmt_group)

        # --- Optional sections ---
        opt_group = QGroupBox("Include optional sections")
        opt_layout = QVBoxLayout(opt_group)
        self._kills_cb = QCheckBox("Kill counts per session")
        self._kills_cb.setChecked(True)
        self._pre_cb = QCheckBox("Pre-session notes")
        self._pre_cb.setChecked(True)
        self._post_cb = QCheckBox("Post-session notes")
        self._post_cb.setChecked(True)
        self._total_cb = QCheckBox("Total kill count")
        self._total_cb.setChecked(True)
        for cb in (self._kills_cb, self._pre_cb, self._post_cb, self._total_cb):
            opt_layout.addWidget(cb)
        layout.addWidget(opt_group)

        # --- Buttons ---
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Export…")
        buttons.accepted.connect(self._on_export)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # ------------------------------------------------------------------

    def _on_export(self) -> None:
        is_markdown = self._md_radio.isChecked()
        ext = "md" if is_markdown else "txt"
        filter_str = (
            "Markdown Files (*.md)"
            if is_markdown
            else "Text Files (*.txt)"
        )

        safe_name = self._campaign.name.replace("/", "-").replace("\\", "-")
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Campaign",
            f"{safe_name}.{ext}",
            filter_str,
        )
        if not path:
            return

        from ttrpg_notes.models.exporter import export_markdown, export_text

        kwargs = dict(
            include_kills=self._kills_cb.isChecked(),
            include_pre=self._pre_cb.isChecked(),
            include_post=self._post_cb.isChecked(),
            include_total=self._total_cb.isChecked(),
        )
        fn = export_markdown if is_markdown else export_text
        content = fn(self._campaign, **kwargs)

        try:
            Path(path).write_text(content, encoding="utf-8")
            self.accept()
        except OSError as exc:
            _log.exception("Failed to write export file: %s", path)
            QMessageBox.critical(self, "Export Error", str(exc))
