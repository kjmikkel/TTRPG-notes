from __future__ import annotations

import logging
from pathlib import Path

_log = logging.getLogger(__name__)

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QVBoxLayout,
)

_B = "https://raw.githubusercontent.com/LibreOffice/dictionaries/master"

# Full list sourced from the LibreOffice dictionaries repository.
# Format: (display_name, base_url_without_extension)
# Sorted alphabetically by display name.
_DICTIONARIES: list[tuple[str, str]] = [
    ("Afrikaans",               f"{_B}/af_ZA/af_ZA"),
    ("Albanian",                f"{_B}/sq_AL/sq_AL"),
    ("Arabic",                  f"{_B}/ar/ar"),
    ("Armenian",                f"{_B}/hy_AM/hy_AM"),
    ("Basque",                  f"{_B}/eu/eu"),
    ("Belarusian",              f"{_B}/be_BY/be_BY"),
    ("Bengali",                 f"{_B}/bn_BD/bn_BD"),
    ("Breton",                  f"{_B}/br_FR/br_FR"),
    ("Bulgarian",               f"{_B}/bg_BG/bg_BG"),
    ("Catalan",                 f"{_B}/ca/ca"),
    ("Catalan (Valencia)",      f"{_B}/ca/ca-valencia"),
    ("Croatian",                f"{_B}/hr_HR/hr_HR"),
    ("Czech",                   f"{_B}/cs_CZ/cs_CZ"),
    ("Danish",                  f"{_B}/da_DK/da_DK"),
    ("Dutch",                   f"{_B}/nl_NL/nl_NL"),
    ("English (Australia)",     f"{_B}/en/en_AU"),
    ("English (GB)",            f"{_B}/en/en_GB"),
    ("English (South Africa)",  f"{_B}/en/en_ZA"),
    ("English (US)",            f"{_B}/en/en_US"),
    ("Esperanto",               f"{_B}/eo/eo"),
    ("Estonian",                f"{_B}/et_EE/et_EE"),
    ("Finnish",                 f"{_B}/fi_FI/fi_FI"),
    ("French",                  f"{_B}/fr_FR/fr"),
    ("Galician",                f"{_B}/gl/gl_ES"),
    ("German (Austria)",        f"{_B}/de/de_AT"),
    ("German (Germany)",        f"{_B}/de/de_DE"),
    ("German (Switzerland)",    f"{_B}/de/de_CH"),
    ("Greek",                   f"{_B}/el_GR/el_GR"),
    ("Gujarati",                f"{_B}/gu_IN/gu_IN"),
    ("Hebrew",                  f"{_B}/he_IL/he_IL"),
    ("Hindi",                   f"{_B}/hi_IN/hi_IN"),
    ("Hungarian",               f"{_B}/hu_HU/hu_HU"),
    ("Icelandic",               f"{_B}/is/is"),
    ("Indonesian",              f"{_B}/id_ID/id_ID"),
    ("Irish",                   f"{_B}/ga_IE/ga_IE"),
    ("Italian",                 f"{_B}/it_IT/it_IT"),
    ("Kurdish (Northern)",      f"{_B}/kmr_Latn/kmr_Latn"),
    ("Lao",                     f"{_B}/lo_LA/lo_LA"),
    ("Latvian",                 f"{_B}/lv_LV/lv_LV"),
    ("Lithuanian",              f"{_B}/lt_LT/lt_LT"),
    ("Macedonian",              f"{_B}/mk_MK/mk_MK"),
    ("Malay",                   f"{_B}/ms_MY/ms_MY"),
    ("Mongolian",               f"{_B}/mn_MN/mn_MN"),
    ("Nepali",                  f"{_B}/ne_NP/ne_NP"),
    ("Norwegian Bokmål",        f"{_B}/no/nb_NO"),
    ("Norwegian Nynorsk",       f"{_B}/no/nn_NO"),
    ("Occitan",                 f"{_B}/oc_FR/oc_FR"),
    ("Persian",                 f"{_B}/fa_IR/fa_IR"),
    ("Polish",                  f"{_B}/pl_PL/pl_PL"),
    ("Portuguese (Brazil)",     f"{_B}/pt_BR/pt_BR"),
    ("Portuguese (Portugal)",   f"{_B}/pt_PT/pt_PT"),
    ("Romanian",                f"{_B}/ro/ro_RO"),
    ("Russian",                 f"{_B}/ru_RU/ru_RU"),
    ("Scottish Gaelic",         f"{_B}/gd_GB/gd_GB"),
    ("Serbian (Cyrillic)",      f"{_B}/sr/sr"),
    ("Serbian (Latin)",         f"{_B}/sr/sr-Latn"),
    ("Sinhalese",               f"{_B}/si_LK/si_LK"),
    ("Slovak",                  f"{_B}/sk_SK/sk_SK"),
    ("Slovenian",               f"{_B}/sl_SI/sl_SI"),
    ("Spanish (Any)",           f"{_B}/es/es_ANY"),
    ("Spanish (Spain)",         f"{_B}/es/es_ES"),
    ("Swahili",                 f"{_B}/sw_TZ/sw_TZ"),
    ("Swedish",                 f"{_B}/sv_SE/sv_SE"),
    ("Tamil",                   f"{_B}/ta_IN/ta_IN"),
    ("Telugu",                  f"{_B}/te_IN/te_IN"),
    ("Thai",                    f"{_B}/th_TH/th_TH"),
    ("Turkish",                 f"{_B}/tr_TR/tr_TR"),
    ("Ukrainian",               f"{_B}/uk_UA/uk_UA"),
    ("Vietnamese",              f"{_B}/vi_VN/vi_VN"),
]

# Item data roles
_ROLE_URL  = 256   # base URL without extension
_ROLE_STEM = 257   # filename stem (e.g. "en_US")
_ROLE_DL   = 258   # bool — is already downloaded
_ROLE_NAME = 259   # display name


class _DownloadWorker(QThread):
    progress = Signal(str)
    finished = Signal(bool, str)  # success, stem-or-error

    def __init__(self, base_url: str, dest_dir: Path) -> None:
        super().__init__()
        self._base_url = base_url
        self._dest_dir = dest_dir

    def run(self) -> None:
        try:
            import requests  # type: ignore[import]

            self._dest_dir.mkdir(parents=True, exist_ok=True)
            stem = self._base_url.rsplit("/", 1)[-1]

            for ext in (".dic", ".aff"):
                url = self._base_url + ext
                self.progress.emit(f"Downloading {stem}{ext}…")
                resp = requests.get(url, timeout=30)
                resp.raise_for_status()
                (self._dest_dir / (stem + ext)).write_bytes(resp.content)

            self.finished.emit(True, stem)
        except Exception as exc:
            _log.exception("Failed to download dictionary from %s", self._base_url)
            self.finished.emit(False, str(exc))


class DownloaderDialog(QDialog):
    """
    Dictionary manager: browse the full LibreOffice dictionary list,
    download missing ones, and delete installed ones.

    Signals:
      downloaded(Path)  — emitted after a successful download (.dic path)
      deleted(str)      — emitted after deletion (stem, e.g. "en_US")
    """

    downloaded = Signal(Path)
    deleted = Signal(str)

    def __init__(self, dest_dir: Path, parent=None) -> None:
        super().__init__(parent)
        self._dest_dir = dest_dir
        self.setWindowTitle("Manage Dictionaries")
        self.setMinimumSize(500, 460)

        layout = QVBoxLayout(self)

        # Filter row
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Filter:"))
        self._filter = QLineEdit()
        self._filter.setPlaceholderText("Type to filter languages…")
        self._filter.textChanged.connect(self._rebuild_list)
        filter_row.addWidget(self._filter)
        layout.addLayout(filter_row)

        # List
        self._list = QListWidget()
        self._list.currentItemChanged.connect(self._update_buttons)
        layout.addWidget(self._list)

        # Button row
        btn_row = QHBoxLayout()
        self._download_btn = QPushButton("Download")
        self._download_btn.setEnabled(False)
        self._download_btn.clicked.connect(self._download_selected)
        self._delete_btn = QPushButton("Delete")
        self._delete_btn.setEnabled(False)
        self._delete_btn.clicked.connect(self._delete_selected)
        btn_row.addWidget(self._download_btn)
        btn_row.addWidget(self._delete_btn)
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        self._worker: _DownloadWorker | None = None
        self._rebuild_list()

    # ------------------------------------------------------------------
    # List management
    # ------------------------------------------------------------------

    def _downloaded_stems(self) -> set[str]:
        if not self._dest_dir.exists():
            return set()
        return {f.stem for f in self._dest_dir.glob("*.dic")}

    def _rebuild_list(self) -> None:
        stems = self._downloaded_stems()
        query = self._filter.text().lower()

        # Remember current selection so we can restore it after rebuild
        cur = self._list.currentItem()
        current_url = cur.data(_ROLE_URL) if cur else None

        self._list.clear()
        restore_row = 0
        visible_row = 0
        for name, url in _DICTIONARIES:
            if query and query not in name.lower():
                continue
            stem = url.rsplit("/", 1)[-1]
            is_dl = stem in stems
            label = f"✓  {name}" if is_dl else f"    {name}"
            item = QListWidgetItem(label)
            item.setData(_ROLE_URL,  url)
            item.setData(_ROLE_STEM, stem)
            item.setData(_ROLE_DL,   is_dl)
            item.setData(_ROLE_NAME, name)
            if is_dl:
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            self._list.addItem(item)
            if url == current_url:
                restore_row = visible_row
            visible_row += 1

        if self._list.count() > 0:
            self._list.setCurrentRow(restore_row)
        self._update_buttons()

    def _update_buttons(self) -> None:
        item = self._list.currentItem()
        if item is None:
            self._download_btn.setEnabled(False)
            self._delete_btn.setEnabled(False)
            return
        is_dl = bool(item.data(_ROLE_DL))
        self._download_btn.setEnabled(not is_dl)
        self._delete_btn.setEnabled(is_dl)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _download_selected(self) -> None:
        item = self._list.currentItem()
        if item is None:
            return
        base_url = item.data(_ROLE_URL)

        self._progress = QProgressDialog("Downloading…", None, 0, 0, self)
        self._progress.setWindowModality(Qt.WindowModal)
        self._progress.setWindowTitle("Downloading Dictionary")
        self._progress.show()

        self._worker = _DownloadWorker(base_url, self._dest_dir)
        self._worker.progress.connect(self._progress.setLabelText)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _delete_selected(self) -> None:
        item = self._list.currentItem()
        if item is None:
            return
        stem = item.data(_ROLE_STEM)
        name = item.data(_ROLE_NAME)

        resp = QMessageBox.question(
            self,
            "Delete Dictionary",
            f"Delete the '{name}' dictionary files from disk?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if resp != QMessageBox.Yes:
            return

        for ext in (".dic", ".aff"):
            p = self._dest_dir / (stem + ext)
            if p.exists():
                p.unlink()

        self.deleted.emit(stem)
        self._rebuild_list()

    def _on_finished(self, success: bool, message: str) -> None:
        self._progress.close()
        if success:
            dic_path = self._dest_dir / (message + ".dic")
            self.downloaded.emit(dic_path)
            self._rebuild_list()   # show ✓ on the newly downloaded entry
        else:
            QMessageBox.critical(
                self, "Download Failed", f"Could not download dictionary:\n{message}"
            )
