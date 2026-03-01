"""
dropbox_setup.py — DropboxSetupDialog and its background auth worker.

Opened from Options → Dropbox Integration… in the main window.
"""
from __future__ import annotations

import logging
import webbrowser

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from ttrpg_notes.config import settings

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Background worker
# ---------------------------------------------------------------------------

class _AuthWorker(QThread):
    """Runs the full Dropbox OAuth2 PKCE flow on a background thread."""

    auth_success = Signal(str, str)  # access_token, refresh_token
    auth_failed = Signal(str)        # error message

    def __init__(self, app_key: str) -> None:
        super().__init__()
        self._app_key = app_key

    def run(self) -> None:
        try:
            from ttrpg_notes.integrations.dropbox_client import run_auth_flow
            result = run_auth_flow(self._app_key, open_browser_fn=webbrowser.open)
            self.auth_success.emit(result.access_token, result.refresh_token)
        except Exception as exc:
            _log.exception("Dropbox auth flow failed")
            self.auth_failed.emit(str(exc))


# ---------------------------------------------------------------------------
# Dialog
# ---------------------------------------------------------------------------

class DropboxSetupDialog(QDialog):
    """
    Configure Dropbox integration.

    Guides the user through:
    1. Entering their Dropbox App Key (obtained from the developer console).
    2. Clicking Connect, which opens the browser for OAuth2 authentication.
    3. Setting the upload folder and auto-upload preference.

    Settings are written to QSettings immediately — there is no Cancel.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Dropbox Integration")
        self.setMinimumWidth(460)

        self._worker: _AuthWorker | None = None

        outer = QVBoxLayout(self)
        outer.setSpacing(12)

        # --- Status group ---
        status_group = QGroupBox("Connection")
        status_layout = QFormLayout(status_group)
        self._status_label = QLabel()
        status_layout.addRow("Status:", self._status_label)
        outer.addWidget(status_group)

        # --- App key group ---
        app_group = QGroupBox("Dropbox App")
        app_layout = QVBoxLayout(app_group)

        help_label = QLabel(
            "Register an app at "
            '<a href="https://www.dropbox.com/developers/apps">dropbox.com/developers/apps</a>,'
            " set the redirect URI to <b>http://localhost</b>, then paste your App Key below."
        )
        help_label.setWordWrap(True)
        help_label.setOpenExternalLinks(True)
        app_layout.addWidget(help_label)

        app_key_row = QFormLayout()
        self._app_key_edit = QLineEdit()
        self._app_key_edit.setPlaceholderText("e.g. abc123xyz456")
        self._app_key_edit.setText(settings.get_dropbox_app_key())
        app_key_row.addRow("App Key:", self._app_key_edit)
        app_layout.addLayout(app_key_row)
        outer.addWidget(app_group)

        # --- Upload settings group ---
        upload_group = QGroupBox("Upload Settings")
        upload_layout = QFormLayout(upload_group)

        self._folder_edit = QLineEdit()
        self._folder_edit.setPlaceholderText("/TTRPG Notes")
        self._folder_edit.setText(settings.get_dropbox_upload_folder())
        upload_layout.addRow("Dropbox folder:", self._folder_edit)

        self._auto_upload_cb = QCheckBox("Upload automatically after saving")
        self._auto_upload_cb.setChecked(settings.get_dropbox_auto_upload())
        self._auto_upload_cb.toggled.connect(settings.set_dropbox_auto_upload)
        upload_layout.addRow(self._auto_upload_cb)
        outer.addWidget(upload_group)

        # --- Connect / Disconnect button ---
        self._connect_btn = QPushButton()
        self._connect_btn.clicked.connect(self._on_connect_clicked)
        outer.addWidget(self._connect_btn)

        # --- Close ---
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self._on_close)
        outer.addWidget(buttons)

        self._refresh_ui()

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------

    def _is_connected(self) -> bool:
        return bool(settings.get_dropbox_refresh_token())

    def _refresh_ui(self) -> None:
        connected = self._is_connected()
        if connected:
            self._status_label.setText("Connected")
            self._connect_btn.setText("Disconnect")
            self._app_key_edit.setEnabled(False)
        else:
            self._status_label.setText("Not connected")
            self._connect_btn.setText("Connect to Dropbox…")
            self._app_key_edit.setEnabled(True)
        self._auto_upload_cb.setEnabled(connected)
        self._connect_btn.setEnabled(True)

    # ------------------------------------------------------------------
    # Button handler
    # ------------------------------------------------------------------

    def _on_connect_clicked(self) -> None:
        if self._is_connected():
            self._disconnect()
        else:
            self._start_connect()

    def _disconnect(self) -> None:
        settings.set_dropbox_access_token("")
        settings.set_dropbox_refresh_token("")
        settings.set_dropbox_auto_upload(False)
        self._auto_upload_cb.setChecked(False)
        self._refresh_ui()

    def _start_connect(self) -> None:
        app_key = self._app_key_edit.text().strip()
        if not app_key:
            QMessageBox.warning(
                self,
                "App Key Required",
                "Please enter your Dropbox App Key before connecting.",
            )
            return

        # Persist settings before auth so they survive a crash/close.
        settings.set_dropbox_app_key(app_key)
        settings.set_dropbox_upload_folder(
            self._folder_edit.text().strip() or "/TTRPG Notes"
        )

        self._connect_btn.setEnabled(False)
        self._connect_btn.setText("Authenticating…")
        self._status_label.setText("Browser opened — please log in and authorise.")

        self._worker = _AuthWorker(app_key)
        self._worker.auth_success.connect(self._on_auth_success)
        self._worker.auth_failed.connect(self._on_auth_failed)
        self._worker.start()

    def _on_auth_success(self, access_token: str, refresh_token: str) -> None:
        settings.set_dropbox_access_token(access_token)
        settings.set_dropbox_refresh_token(refresh_token)
        self._refresh_ui()

    def _on_auth_failed(self, error: str) -> None:
        self._refresh_ui()
        QMessageBox.critical(
            self,
            "Authentication Failed",
            f"Could not connect to Dropbox:\n\n{error}",
        )

    # ------------------------------------------------------------------
    # Close
    # ------------------------------------------------------------------

    def _on_close(self) -> None:
        # Persist folder (user may have edited it without re-connecting).
        settings.set_dropbox_upload_folder(
            self._folder_edit.text().strip() or "/TTRPG Notes"
        )
        # Persist app key (user may have typed it but not yet connected).
        key = self._app_key_edit.text().strip()
        if key:
            settings.set_dropbox_app_key(key)
        self.accept()
