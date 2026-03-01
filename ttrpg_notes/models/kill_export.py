"""
kill_export.py — standalone kill-data export module.

This module has no UI dependencies and can be imported by external systems
that only have access to the data model (``ttrpg_notes.models.campaign``).

Public API
----------
``build_kill_report(campaign)``
    Return a plain dict describing all kill statistics for every session.

``export_kills_json(campaign, path)``
    Serialise that dict to a UTF-8 JSON file.

JSON shape
----------
::

    {
      "campaign_id": "...",
      "campaign_name": "...",
      "sessions": [
        {
          "session_id": "...",
          "session_number": 1,
          "session_name": null,
          "session_date": "2026-01-01",
          "by_player": [
            {
              "player_id": "...",
              "player_name": "Alice",
              "session_kills":    { "total": 5, "by_type": {"goblin": 3, "orc": 2} },
              "cumulative_kills": { "total": 9, "by_type": {"goblin": 6, "orc": 3} }
            }
          ],
          "by_character": [
            {
              "character_id": "...",
              "character_name": "Aldric",
              "player_id": "...",
              "player_name": "Alice",
              "session_kills":    { "total": 5, "by_type": {"goblin": 3, "orc": 2} },
              "cumulative_kills": { "total": 9, "by_type": {"goblin": 6, "orc": 3} }
            }
          ]
        }
      ]
    }

For each session entry:

* ``session_kills``   – kills recorded in *that session only*.
* ``cumulative_kills`` – running total from session 1 through this session.

Both carry a ``total`` (integer) and a ``by_type`` dict (creature → count).
Player totals are the sum across all characters belonging to that player.
"""
from __future__ import annotations

import json
from pathlib import Path

from ttrpg_notes.models.campaign import Campaign, Session


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _char_session_kills(session: Session, char_id: str) -> dict[str, int]:
    """Return ``{being: count}`` for one character in one session."""
    result: dict[str, int] = {}
    for k in session.kills.get(char_id, []):
        result[k.being] = result.get(k.being, 0) + k.count
    return result


def _char_cumulative_kills(campaign: Campaign, char_id: str, up_to_idx: int) -> dict[str, int]:
    """Return ``{being: count}`` for one character across sessions 0..up_to_idx."""
    result: dict[str, int] = {}
    for session in campaign.sessions[: up_to_idx + 1]:
        for k in session.kills.get(char_id, []):
            result[k.being] = result.get(k.being, 0) + k.count
    return result


def _merge(*dicts: dict[str, int]) -> dict[str, int]:
    """Sum multiple ``{being: count}`` dicts into one."""
    result: dict[str, int] = {}
    for d in dicts:
        for being, count in d.items():
            result[being] = result.get(being, 0) + count
    return result


def _kills_entry(by_type: dict[str, int]) -> dict[str, object]:
    return {"total": sum(by_type.values()), "by_type": by_type}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_kill_report(campaign: Campaign) -> dict[str, object]:
    """
    Build a comprehensive kill report for *campaign*.

    Returns a plain ``dict`` (no PySide6 or other UI types) that can be
    serialised directly with :func:`json.dumps`.
    """
    sessions_out: list[dict] = []

    for idx, session in enumerate(campaign.sessions):
        # --- by character ---
        by_character: list[dict] = []
        for player in campaign.players:
            for char in player.characters:
                sess_by_type = _char_session_kills(session, char.id)
                cum_by_type = _char_cumulative_kills(campaign, char.id, idx)
                by_character.append({
                    "character_id": char.id,
                    "character_name": char.name,
                    "player_id": player.id,
                    "player_name": player.name,
                    "session_kills": _kills_entry(sess_by_type),
                    "cumulative_kills": _kills_entry(cum_by_type),
                })

        # --- by player (sum across all characters) ---
        by_player: list[dict] = []
        for player in campaign.players:
            sess_by_type = _merge(
                *(_char_session_kills(session, c.id) for c in player.characters)
            )
            cum_by_type = _merge(
                *(_char_cumulative_kills(campaign, c.id, idx) for c in player.characters)
            )
            by_player.append({
                "player_id": player.id,
                "player_name": player.name,
                "session_kills": _kills_entry(sess_by_type),
                "cumulative_kills": _kills_entry(cum_by_type),
            })

        sessions_out.append({
            "session_id": session.id,
            "session_number": session.number,
            "session_name": session.name,
            "session_date": session.date,
            "by_player": by_player,
            "by_character": by_character,
        })

    return {
        "campaign_id": campaign.id,
        "campaign_name": campaign.name,
        "sessions": sessions_out,
    }


def export_kills_json(campaign: Campaign, path: str | Path) -> None:
    """Serialise the kill report for *campaign* to a JSON file at *path*."""
    report = build_kill_report(campaign)
    Path(path).write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
