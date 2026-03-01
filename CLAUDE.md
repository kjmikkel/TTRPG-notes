# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**TTRPG-notes** is a Python utility to record notes from tabletop RPG sessions, including kill counts per player.

## Project Status

Core application implemented. Tech stack: PySide6 (GUI), spylls (spellcheck), requests (dict download), JSON (data), QSettings (prefs).

## Package Structure

```
ttrpg_notes/
├── __main__.py              # Entry point
├── models/campaign.py       # Dataclasses: Campaign, Player, Character, Session, Kill
├── models/persistence.py    # load_campaign(), save_campaign(), save_dirty_sessions()
├── config/settings.py       # QSettings wrapper (last_campaign_path, dict_dir)
├── ui/
│   ├── app.py               # run_startup(): load last file or show open dialog
│   ├── main_window.py       # QMainWindow with 3-panel layout + menu
│   ├── session_list.py      # SessionList(QListWidget)
│   ├── summary_editor.py    # SummaryEditor(QTextEdit) with spellcheck hook
│   ├── kill_entry.py        # KillEntry (editable), ReadonlyKillEntry
│   ├── kill_panel.py        # KillPanel(QScrollArea), CharacterKillSection
│   └── spellcheck/
│       ├── checker.py       # SpellChecker wrapping spylls
│       ├── highlighter.py   # SpellHighlighter(QSyntaxHighlighter)
│       └── downloader.py    # DownloaderDialog — fetch .dic/.aff from LibreOffice
│   └── dialogs/
│       ├── new_campaign.py  # NewCampaignDialog
│       ├── new_player.py    # NewPlayerDialog
│       ├── new_session.py   # NewSessionDialog
│       └── search.py        # SearchDialog (non-modal)
```

## Conventions

- **Package manager**: `pip` with `pyproject.toml`
- **Linting**: `ruff` (`line-length = 100`)
- **Type checking**: `mypy` (strict)
- **Data format**: JSON, schema version 1

## Commands

```bash
# Install dependencies
pip install -e .

# Run the app
python -m ttrpg_notes

# Lint
ruff check .

# Type check
mypy .
```

## Key Design Notes

- `Session.dirty` tracks unsaved changes (not persisted to JSON)
- Kill panel: readonly rows = aggregated kills from sessions before current; editable rows = current session only; no merging
- Spellcheck dicts live in `~/.ttrpg_notes/dicts/`; user dict at `~/.ttrpg_notes/user_dict.json`
- Right-click on misspelled word → "Add to dictionary" or "Ignore"
- On startup, if no `.dic` file found → DownloaderDialog shown automatically
