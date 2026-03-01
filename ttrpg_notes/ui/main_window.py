from __future__ import annotations

import logging
import uuid
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QAction, QKeySequence, QTextCursor
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QInputDialog,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from ttrpg_notes.config import settings
from ttrpg_notes.models.campaign import Campaign, Session
from ttrpg_notes.models.persistence import load_campaign, save_campaign, save_dirty_sessions
from ttrpg_notes.ui.kill_panel import KillPanel
from ttrpg_notes.ui.session_list import SessionList
from ttrpg_notes.ui.summary_editor import SummaryEditor

_log = logging.getLogger(__name__)


class _SuggestWorker(QThread):
    """Fetches spellcheck suggestions off the main thread."""

    suggestions_ready = Signal(list)

    def __init__(self, word: str, checker) -> None:
        super().__init__()
        self._word = word
        self._checker = checker

    def run(self) -> None:
        suggestions = self._checker.suggest(self._word)[:8]
        self.suggestions_ready.emit(suggestions)


class _UploadWorker(QThread):
    """Uploads the campaign JSON to Dropbox in the background."""

    upload_success = Signal(str, str)  # new access_token, new refresh_token
    upload_failed = Signal(str)        # error message

    def __init__(
        self,
        local_path: str,
        dropbox_folder: str,
        access_token: str,
        app_key: str,
        refresh_token: str,
    ) -> None:
        super().__init__()
        self._local_path = local_path
        self._dropbox_folder = dropbox_folder
        self._access_token = access_token
        self._app_key = app_key
        self._refresh_token = refresh_token

    def run(self) -> None:
        from ttrpg_notes.integrations.dropbox_client import upload_file
        try:
            result = upload_file(
                self._local_path,
                self._dropbox_folder,
                self._access_token,
                self._app_key,
                self._refresh_token,
            )
            self.upload_success.emit(result.access_token, result.refresh_token)
        except Exception as exc:
            _log.exception("Dropbox upload failed")
            self.upload_failed.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("TTRPG Notes")
        self.resize(1100, 700)

        self._campaign: Campaign | None = None
        self._campaign_path: str | None = None
        self._current_session: Session | None = None
        self._spell_checker = None
        self._highlighter = None
        self._suggest_workers: list = []  # keeps running workers alive until finished
        self._upload_workers: list = []   # keeps upload workers alive until finished

        self._build_ui()
        self._build_menu()
        self.setStatusBar(QStatusBar())

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self._splitter = QSplitter(Qt.Horizontal)
        self.setCentralWidget(self._splitter)
        splitter = self._splitter

        # Left panel: session list + "+" button
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        self._session_list = SessionList()
        self._session_list.session_selected.connect(self._on_session_selected)
        self._session_list.session_renamed.connect(self._on_session_renamed)
        self._session_list.session_deleted.connect(self._on_session_deleted)
        left_layout.addWidget(self._session_list)

        add_btn = QPushButton("+ New Session")
        add_btn.setFixedHeight(28)
        add_btn.setToolTip("Add a new session  (right-click a session to rename/delete)")
        add_btn.clicked.connect(self._action_new_session)
        left_layout.addWidget(add_btn)

        splitter.addWidget(left_panel)

        self._summary_editor = SummaryEditor()
        self._summary_editor.text_changed_by_user.connect(self._on_summary_changed)
        splitter.addWidget(self._summary_editor)

        self._kill_panel = KillPanel()
        self._kill_panel.session_dirty.connect(self._on_kill_changed)
        # Minimum width: 20 average characters + scrollbar/padding
        char_w = self._kill_panel.fontMetrics().horizontalAdvance("n")
        self._kill_panel.setMinimumWidth(char_w * 20 + 24)
        splitter.addWidget(self._kill_panel)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setStretchFactor(2, 2)

        # Restore saved splitter sizes (if they exist and look valid)
        saved = settings.get_splitter_sizes()
        if saved and len(saved) == 3 and sum(saved) > 0:
            splitter.setSizes(saved)

    def _build_menu(self) -> None:
        menu = self.menuBar()

        # File menu
        file_menu = menu.addMenu("&File")

        new_action = QAction("&New Campaign…", self)
        new_action.setShortcut(QKeySequence.New)
        new_action.triggered.connect(self._action_new_campaign)
        file_menu.addAction(new_action)

        open_action = QAction("&Open…", self)
        open_action.setShortcut(QKeySequence.Open)
        open_action.triggered.connect(self._action_open)
        file_menu.addAction(open_action)

        self._rename_action = QAction("Rename Campaign…", self)
        self._rename_action.triggered.connect(self._action_rename_campaign)
        self._rename_action.setEnabled(False)
        file_menu.addAction(self._rename_action)

        file_menu.addSeparator()

        self._save_action = QAction("&Save", self)
        self._save_action.setShortcut(QKeySequence.Save)
        self._save_action.triggered.connect(self._action_save)
        self._save_action.setEnabled(False)
        file_menu.addAction(self._save_action)

        self._save_all_action = QAction("Save &All", self)
        self._save_all_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        self._save_all_action.triggered.connect(self._action_save_all)
        self._save_all_action.setEnabled(False)
        file_menu.addAction(self._save_all_action)

        self._upload_action = QAction("Save && Upload to &Dropbox", self)
        self._upload_action.setShortcut(QKeySequence("Ctrl+Shift+D"))
        self._upload_action.triggered.connect(self._action_save_and_upload)
        self._upload_action.setEnabled(False)
        file_menu.addAction(self._upload_action)

        file_menu.addSeparator()

        self._export_action = QAction("&Export…", self)
        self._export_action.triggered.connect(self._action_export)
        self._export_action.setEnabled(False)
        file_menu.addAction(self._export_action)

        self._export_kills_action = QAction("Export &Kill Data…", self)
        self._export_kills_action.triggered.connect(self._action_export_kills)
        self._export_kills_action.setEnabled(False)
        file_menu.addAction(self._export_kills_action)

        file_menu.addSeparator()

        manage_players_action = QAction("Manage &Players…", self)
        manage_players_action.triggered.connect(self._action_manage_players)
        file_menu.addAction(manage_players_action)

        file_menu.addSeparator()

        search_action = QAction("&Search…", self)
        search_action.setShortcut(QKeySequence("Ctrl+F"))
        search_action.triggered.connect(self._action_search)
        file_menu.addAction(search_action)

        # Options menu
        options_menu = menu.addMenu("&Options")
        options_action = QAction("&Options…", self)
        options_action.triggered.connect(self._action_options)
        options_menu.addAction(options_action)

        options_menu.addSeparator()

        dropbox_action = QAction("Dropbox Integration…", self)
        dropbox_action.triggered.connect(self._action_dropbox_setup)
        options_menu.addAction(dropbox_action)

    # ------------------------------------------------------------------
    # Campaign loading
    # ------------------------------------------------------------------

    def load_campaign(self, path: str) -> None:
        try:
            campaign = load_campaign(path)
        except Exception as exc:
            _log.exception("Failed to load campaign: %s", path)
            QMessageBox.critical(self, "Error", f"Failed to load campaign:\n{exc}")
            return
        self._campaign = campaign
        self._campaign_path = path
        settings.set_last_campaign_path(path)
        self.setWindowTitle(f"TTRPG Notes — {campaign.name}")
        self._session_list.load_campaign(campaign)
        self._save_action.setEnabled(True)
        self._save_all_action.setEnabled(True)
        self._rename_action.setEnabled(True)
        self._export_action.setEnabled(True)
        self._export_kills_action.setEnabled(True)
        self._upload_action.setEnabled(True)
        self._init_spellcheck()

    def _init_spellcheck(self) -> None:
        from ttrpg_notes.ui.spellcheck.checker import SpellChecker
        from ttrpg_notes.ui.spellcheck.downloader import DownloaderDialog
        from ttrpg_notes.ui.spellcheck.highlighter import SpellHighlighter

        data_dir = Path.home() / ".ttrpg_notes"
        dict_dir = data_dir / "dicts"
        dic_files = list(dict_dir.glob("*.dic")) if dict_dir.exists() else []

        if not dic_files:
            dlg = DownloaderDialog(dict_dir, self)
            dlg.downloaded.connect(lambda p: self._load_spellcheck(p, SpellChecker, SpellHighlighter))
            dlg.exec()
        else:
            self._load_spellcheck(dic_files[0], SpellChecker, SpellHighlighter)

    def _load_spellcheck(self, dic_path: Path, checker_cls, highlighter_cls) -> None:
        try:
            self._spell_checker = checker_cls(dic_path)

            class _BoundHighlighter(highlighter_cls):
                def __init__(self_, document):
                    super().__init__(document, self._spell_checker)

            self._highlighter = self._summary_editor.attach_highlighter(_BoundHighlighter)
            self._summary_editor.setContextMenuPolicy(Qt.CustomContextMenu)
            self._summary_editor.customContextMenuRequested.connect(
                self._on_summary_context_menu
            )
        except Exception as exc:
            _log.exception("Failed to load spellcheck dictionary")
            self.statusBar().showMessage(f"Spellcheck unavailable: {exc}", 5000)

    def _on_summary_context_menu(self, pos) -> None:
        if self._spell_checker is None:
            return
        cursor = self._summary_editor.cursorForPosition(pos)
        cursor.select(QTextCursor.SelectionType.WordUnderCursor)
        word = cursor.selectedText()
        if not word or self._spell_checker.check(word):
            self._summary_editor.createStandardContextMenu().exec(
                self._summary_editor.viewport().mapToGlobal(pos)
            )
            return

        from PySide6.QtWidgets import QMenu
        menu = QMenu(self._summary_editor)

        # Placeholder shown while the background thread fetches suggestions.
        # Replaced in-place once _SuggestWorker emits suggestions_ready.
        # menu.exec() runs a nested event loop so the signal is delivered
        # and the menu repaints while it is already visible.
        placeholder = menu.addAction("Fetching suggestions…")
        placeholder.setEnabled(False)
        sep = menu.addSeparator()

        menu.addAction(f'Add "{word}" to dictionary').triggered.connect(
            lambda: self._add_to_dict(word)
        )
        menu.addAction(f'Ignore "{word}"').triggered.connect(
            lambda: self._ignore_word(word)
        )
        menu.addSeparator()
        menu.addActions(self._summary_editor.createStandardContextMenu().actions())

        def _apply(suggestions: list) -> None:
            menu.removeAction(placeholder)
            if suggestions:
                for s in reversed(suggestions):
                    act = QAction(s, menu)
                    act.triggered.connect(
                        lambda checked=False, s=s, c=cursor: c.insertText(s)
                    )
                    menu.insertAction(sep, act)
            else:
                no_sugg = QAction("(No suggestions)", menu)
                no_sugg.setEnabled(False)
                menu.insertAction(sep, no_sugg)

        worker = _SuggestWorker(word, self._spell_checker)
        self._suggest_workers.append(worker)

        def _cleanup() -> None:
            try:
                self._suggest_workers.remove(worker)
            except ValueError:
                pass

        worker.finished.connect(_cleanup)
        worker.suggestions_ready.connect(_apply)
        worker.start()

        menu.exec(self._summary_editor.viewport().mapToGlobal(pos))

    def _add_to_dict(self, word: str) -> None:
        if self._spell_checker:
            self._spell_checker.add_to_dictionary(word)
            self._summary_editor.rehighlight()

    def _ignore_word(self, word: str) -> None:
        if self._spell_checker:
            self._spell_checker.add_to_ignore(word)
            self._summary_editor.rehighlight()

    # ------------------------------------------------------------------
    # Session selection & event handlers
    # ------------------------------------------------------------------

    def _on_session_selected(self, session: Session | None) -> None:
        self._current_session = session
        self._summary_editor.load_session(session)
        if self._campaign and session:
            self._kill_panel.load_session(self._campaign, session)
        else:
            self._kill_panel.load_session(self._campaign, None)

    def _on_session_renamed(self, _session: Session) -> None:
        self._update_title_dirty()

    def _on_session_deleted(self, session: Session) -> None:
        if self._current_session is not None and self._current_session.id == session.id:
            self._current_session = None
            self._summary_editor.load_session(None)
            self._kill_panel.load_session(self._campaign, None)
        # Deletion must be committed with a full save (partial save can't remove sessions).
        if self._campaign_path:
            try:
                save_campaign(self._campaign, self._campaign_path)
                self.statusBar().showMessage("Session deleted and saved.", 2000)
            except Exception as exc:
                _log.exception("Failed to save after session deletion")
                QMessageBox.critical(self, "Save Error", str(exc))
        self._update_title_dirty()

    def _on_summary_changed(self) -> None:
        self._update_title_dirty()

    def _on_kill_changed(self) -> None:
        self._update_title_dirty()

    def _update_title_dirty(self) -> None:
        if self._campaign is None:
            return
        any_dirty = any(s.dirty for s in self._campaign.sessions)
        self.setWindowTitle(f"TTRPG Notes — {self._campaign.name}{'*' if any_dirty else ''}")
        self._session_list.refresh_dirty()

    # ------------------------------------------------------------------
    # Menu actions
    # ------------------------------------------------------------------

    def _action_new_campaign(self) -> None:
        if not self._confirm_discard():
            return
        from ttrpg_notes.ui.dialogs.new_campaign import NewCampaignDialog

        dlg = NewCampaignDialog(self)
        if dlg.exec() != QDialog.Accepted:
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Save Campaign As", "", "Campaign Files (*.json)"
        )
        if not path:
            return

        campaign = Campaign(
            id=str(uuid.uuid4()),
            name=dlg.campaign_name,
            date_format=dlg.date_format,
        )
        try:
            save_campaign(campaign, path)
        except Exception as exc:
            _log.exception("Failed to save new campaign")
            QMessageBox.critical(self, "Error", f"Could not save: {exc}")
            return
        self.load_campaign(path)

    def _action_open(self) -> None:
        if not self._confirm_discard():
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Campaign", "", "Campaign Files (*.json)"
        )
        if path:
            self.load_campaign(path)

    def _action_save(self) -> None:
        if self._campaign is None or self._campaign_path is None:
            return
        try:
            save_dirty_sessions(self._campaign, self._campaign_path)
            self._update_title_dirty()
            self.statusBar().showMessage("Saved.", 2000)
        except Exception as exc:
            _log.exception("Failed to save dirty sessions")
            QMessageBox.critical(self, "Save Error", str(exc))
            return
        if settings.get_dropbox_auto_upload() and settings.get_dropbox_refresh_token():
            self.statusBar().showMessage("Saved. Uploading to Dropbox…", 0)
            self._start_dropbox_upload()

    def _action_save_all(self) -> None:
        if self._campaign is None or self._campaign_path is None:
            return
        try:
            save_campaign(self._campaign, self._campaign_path)
            self._update_title_dirty()
            self.statusBar().showMessage("All saved.", 2000)
        except Exception as exc:
            _log.exception("Failed to save all sessions")
            QMessageBox.critical(self, "Save Error", str(exc))
            return
        if settings.get_dropbox_auto_upload() and settings.get_dropbox_refresh_token():
            self.statusBar().showMessage("All saved. Uploading to Dropbox…", 0)
            self._start_dropbox_upload()

    def _action_rename_campaign(self) -> None:
        if self._campaign is None:
            return
        name, ok = QInputDialog.getText(
            self, "Rename Campaign", "Campaign name:", text=self._campaign.name
        )
        name = name.strip()
        if not ok or not name or name == self._campaign.name:
            return
        self._campaign.name = name
        any_dirty = any(s.dirty for s in self._campaign.sessions)
        self.setWindowTitle(f"TTRPG Notes — {name}{'*' if any_dirty else ''}")
        if self._campaign_path:
            try:
                save_campaign(self._campaign, self._campaign_path)
                self.statusBar().showMessage("Campaign renamed.", 2000)
            except Exception as exc:
                _log.exception("Failed to save campaign after rename")
                QMessageBox.critical(self, "Save Error", str(exc))

    def _action_export(self) -> None:
        if self._campaign is None:
            return
        from ttrpg_notes.ui.dialogs.export import ExportDialog

        ExportDialog(self._campaign, self).exec()

    def _action_export_kills(self) -> None:
        if self._campaign is None:
            return
        safe_name = self._campaign.name.replace("/", "-").replace("\\", "-")
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Kill Data",
            f"{safe_name}_kills.json",
            "JSON Files (*.json)",
        )
        if not path:
            return
        from ttrpg_notes.models.kill_export import export_kills_json

        try:
            export_kills_json(self._campaign, path)
            self.statusBar().showMessage("Kill data exported.", 2000)
        except OSError as exc:
            _log.exception("Failed to export kill data")
            QMessageBox.critical(self, "Export Error", str(exc))

    def _action_dropbox_setup(self) -> None:
        from ttrpg_notes.ui.dialogs.dropbox_setup import DropboxSetupDialog

        DropboxSetupDialog(self).exec()

    def _action_save_and_upload(self) -> None:
        if self._campaign is None or self._campaign_path is None:
            return
        if not settings.get_dropbox_refresh_token():
            QMessageBox.warning(
                self,
                "Dropbox Not Connected",
                "Configure Dropbox in Options → Dropbox Integration… first.",
            )
            return
        try:
            save_campaign(self._campaign, self._campaign_path)
            self._update_title_dirty()
        except Exception as exc:
            _log.exception("Failed to save campaign before Dropbox upload")
            QMessageBox.critical(self, "Save Error", str(exc))
            return
        self.statusBar().showMessage("Saved. Uploading to Dropbox…", 0)
        self._start_dropbox_upload()

    def _start_dropbox_upload(self) -> None:
        """Start a background Dropbox upload of the current campaign file."""
        if self._campaign_path is None:
            return
        app_key = settings.get_dropbox_app_key()
        access_token = settings.get_dropbox_access_token()
        refresh_token = settings.get_dropbox_refresh_token()
        folder = settings.get_dropbox_upload_folder()

        if not (app_key and refresh_token):
            self.statusBar().showMessage("Dropbox not configured.", 4000)
            return

        worker = _UploadWorker(
            self._campaign_path, folder, access_token, app_key, refresh_token
        )
        self._upload_workers.append(worker)

        def _on_success(new_access: str, new_refresh: str) -> None:
            settings.set_dropbox_access_token(new_access)
            settings.set_dropbox_refresh_token(new_refresh)
            self.statusBar().showMessage("Uploaded to Dropbox.", 4000)

        def _on_failed(error: str) -> None:
            self.statusBar().showMessage("Dropbox upload failed.", 4000)
            QMessageBox.critical(self, "Dropbox Upload Error", error)

        def _cleanup() -> None:
            try:
                self._upload_workers.remove(worker)
            except ValueError:
                pass

        worker.upload_success.connect(_on_success)
        worker.upload_failed.connect(_on_failed)
        worker.finished.connect(_cleanup)
        worker.start()

    def _action_new_session(self) -> None:
        if self._campaign is None:
            return
        from ttrpg_notes.ui.dialogs.new_session import NewSessionDialog

        dlg = NewSessionDialog(self)
        if dlg.exec() != QDialog.Accepted:
            return
        session = Session(
            id=str(uuid.uuid4()),
            number=len(self._campaign.sessions) + 1,
            name=dlg.session_name,
            date=dlg.session_date,
            summary="",
            dirty=True,
        )
        self._campaign.sessions.append(session)
        self._session_list.refresh()
        self._session_list.select_session(session)

    def _action_manage_players(self) -> None:
        if self._campaign is None:
            return
        from ttrpg_notes.ui.dialogs.manage_players import ManagePlayersDialog

        dlg = ManagePlayersDialog(self._campaign, self)
        dlg.exec()
        if dlg.changed:
            if self._campaign_path:
                try:
                    save_campaign(self._campaign, self._campaign_path)
                    self.statusBar().showMessage("Players saved.", 2000)
                except Exception as exc:
                    _log.exception("Failed to save campaign after managing players")
                    QMessageBox.critical(self, "Save Error", str(exc))
            if self._current_session:
                self._kill_panel.load_session(self._campaign, self._current_session)

    def _action_search(self) -> None:
        if self._campaign is None:
            return
        from ttrpg_notes.ui.dialogs.search import SearchDialog

        dlg = SearchDialog(self._campaign, self)
        dlg.session_selected.connect(self._session_list.select_session)
        dlg.show()

    def _action_options(self) -> None:
        from ttrpg_notes.ui.dialogs.options import OptionsDialog

        dlg = OptionsDialog(
            self._campaign,
            self._spell_checker,
            self._summary_editor.rehighlight,
            self,
        )
        dlg.exec()

        if dlg.new_date_format is not None and self._campaign is not None:
            self._campaign.date_format = dlg.new_date_format
            self._session_list.refresh()
            if self._campaign_path:
                try:
                    save_campaign(self._campaign, self._campaign_path)
                    self.statusBar().showMessage("Date format saved.", 2000)
                except Exception as exc:
                    _log.exception("Failed to save campaign after changing date format")
                    QMessageBox.critical(self, "Save Error", str(exc))

        if dlg.new_dict_path is not None:
            from ttrpg_notes.ui.spellcheck.checker import SpellChecker
            from ttrpg_notes.ui.spellcheck.highlighter import SpellHighlighter
            self._load_spellcheck(dlg.new_dict_path, SpellChecker, SpellHighlighter)
        elif dlg.dict_deleted:
            # A dictionary was removed; re-scan to pick another or clear the checker.
            self._spell_checker = None
            self._highlighter = None
            self._init_spellcheck()

    # ------------------------------------------------------------------
    # Close / dirty check
    # ------------------------------------------------------------------

    def _confirm_discard(self) -> bool:
        if self._campaign is None:
            return True
        dirty = [s for s in self._campaign.sessions if s.dirty]
        if not dirty:
            return True
        resp = QMessageBox.question(
            self,
            "Unsaved Changes",
            f"{len(dirty)} session(s) have unsaved changes. Discard?",
            QMessageBox.Discard | QMessageBox.Cancel,
        )
        return resp == QMessageBox.Discard

    def closeEvent(self, event) -> None:
        settings.set_splitter_sizes(self._splitter.sizes())
        if self._campaign is None:
            event.accept()
            return
        dirty = [s for s in self._campaign.sessions if s.dirty]
        if not dirty:
            event.accept()
            return
        resp = QMessageBox.question(
            self,
            "Unsaved Changes",
            f"{len(dirty)} session(s) have unsaved changes.",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
        )
        if resp == QMessageBox.Save:
            self._action_save()
            event.accept()
        elif resp == QMessageBox.Discard:
            event.accept()
        else:
            event.ignore()
