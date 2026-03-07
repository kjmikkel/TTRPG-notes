from __future__ import annotations

from PySide6.QtCore import QSettings

_ORG = "ttrpg-notes"
_APP = "ttrpg-notes"


def _qs() -> QSettings:
    return QSettings(_ORG, _APP)


def get_last_campaign_path() -> str | None:
    val = _qs().value("last_campaign_path", None)
    return str(val) if val else None


def set_last_campaign_path(path: str) -> None:
    _qs().setValue("last_campaign_path", path)


def get_splitter_sizes() -> list[int] | None:
    val = _qs().value("splitter_sizes")
    if val is None:
        return None
    try:
        return [int(x) for x in val]
    except (TypeError, ValueError):
        return None


def set_splitter_sizes(sizes: list[int]) -> None:
    _qs().setValue("splitter_sizes", sizes)


def get_section_expanded(key: str, default: bool) -> bool:
    val = _qs().value(f"section_expanded/{key}", default)
    if isinstance(val, bool):
        return val
    return str(val).lower() == "true"


def set_section_expanded(key: str, value: bool) -> None:
    _qs().setValue(f"section_expanded/{key}", value)


# ---------------------------------------------------------------------------
# Dropbox integration
# ---------------------------------------------------------------------------

def get_dropbox_app_key() -> str:
    val = _qs().value("dropbox/app_key", "")
    return str(val) if val else ""


def set_dropbox_app_key(key: str) -> None:
    _qs().setValue("dropbox/app_key", key)


def get_dropbox_access_token() -> str:
    val = _qs().value("dropbox/access_token", "")
    return str(val) if val else ""


def set_dropbox_access_token(token: str) -> None:
    _qs().setValue("dropbox/access_token", token)


def get_dropbox_refresh_token() -> str:
    val = _qs().value("dropbox/refresh_token", "")
    return str(val) if val else ""


def set_dropbox_refresh_token(token: str) -> None:
    _qs().setValue("dropbox/refresh_token", token)


def get_dropbox_auto_upload() -> bool:
    val = _qs().value("dropbox/auto_upload", False)
    if isinstance(val, bool):
        return val
    return str(val).lower() == "true"


def set_dropbox_auto_upload(enabled: bool) -> None:
    _qs().setValue("dropbox/auto_upload", enabled)


def get_dropbox_upload_folder() -> str:
    val = _qs().value("dropbox/upload_folder", "/TTRPG Notes")
    return str(val) if val else "/TTRPG Notes"


def set_dropbox_upload_folder(folder: str) -> None:
    _qs().setValue("dropbox/upload_folder", folder)
