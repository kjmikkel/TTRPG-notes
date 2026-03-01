# TTRPG Notes

A desktop application for recording tabletop RPG session notes and kill counts per player.

## Features

- **Session management** — create, rename, and delete sessions; navigate with a persistent session list
- **Rich note editor** — per-session summary, pre-session, and post-session notes with live spellchecking
- **Kill tracking** — log kills by creature type per character; readonly aggregate view of prior sessions alongside editable entries for the current one
- **Export** — export the full campaign to plain text or Homebrewery-compatible Markdown, with configurable sections (kill counts, pre/post notes, total kill summary)
- **Kill data export** — export structured kill statistics to JSON for use by external tools (per-session and cumulative counts, broken down by player, character, and creature type)
- **Dropbox integration** — OAuth2 PKCE authentication (browser-based, 2FA-friendly), optional auto-upload on save, and a dedicated Save & Upload menu action
- **Spellcheck** — hunspell-compatible dictionaries downloaded on demand from the LibreOffice repository; custom user dictionary with add/ignore support
- **Persistent preferences** — last opened campaign, splitter layout, dictionary directory, and Dropbox settings are all saved across sessions

## Requirements

- Python 3.11+
- PySide6
- spylls
- requests

## Installation

```bash
pip install -e .
```

## Usage

```bash
python -m ttrpg_notes
# or, after pip install -e .:
ttrpg-notes
```

On first launch the application will prompt you to download a spellcheck dictionary. This step can be skipped; the app works fully without one.

## Dropbox Integration

1. Register an app at [dropbox.com/developers/apps](https://www.dropbox.com/developers/apps)
2. Add `http://localhost` as a redirect URI in your app's settings
3. In TTRPG Notes, open **Options → Dropbox Integration…**, enter your App Key, and click **Connect to Dropbox…**
4. Complete the browser-based OAuth flow (2FA is supported)
5. Optionally enable **Upload automatically after saving** in the same dialog

Once connected, use **File → Save & Upload to Dropbox** (Ctrl+Shift+D) to save and upload in one step.

## Data

Campaigns are stored as JSON files (schema version 1). The file path is chosen by the user on campaign creation and remembered across sessions.

Logs are written to `~/.ttrpg_notes/ttrpg_notes.log` (rotating, up to 3 × 1 MB).

## Development

```bash
# Lint
ruff check .

# Type check
mypy .
```
