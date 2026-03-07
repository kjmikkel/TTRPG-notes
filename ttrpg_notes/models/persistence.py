from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ttrpg_notes.models.campaign import Campaign, Character, Kill, Player, Session

_SCHEMA_VERSION = 1


def load_campaign(path: str | Path) -> Campaign:
    """Load a campaign from a JSON file."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("version", 1) != _SCHEMA_VERSION:
        raise ValueError(f"Unsupported campaign file version: {data.get('version')}")
    return _campaign_from_dict(data)


def save_campaign(campaign: Campaign, path: str | Path) -> None:
    """Serialise the entire campaign to JSON, marks all sessions clean."""
    Path(path).write_text(
        json.dumps(_campaign_to_dict(campaign), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    for session in campaign.sessions:
        session.dirty = False


def save_dirty_sessions(campaign: Campaign, path: str | Path) -> None:
    """Re-serialise only dirty sessions inside the existing JSON file."""
    p = Path(path)
    if not p.exists():
        save_campaign(campaign, path)
        return

    data = json.loads(p.read_text(encoding="utf-8"))
    session_map = {s["id"]: s for s in data.get("sessions", [])}

    for session in campaign.sessions:
        if session.dirty or session.id not in session_map:
            # Write dirty sessions and any clean sessions missing from the file
            # (e.g. created during a session that was never fully saved).
            session_map[session.id] = _session_to_dict(session)
            session.dirty = False

    # Write in campaign order; preserve any file-only sessions at the end.
    in_memory_ids = {s.id for s in campaign.sessions}
    data["sessions"] = (
        [session_map[s.id] for s in campaign.sessions]
        + [v for k, v in session_map.items() if k not in in_memory_ids]
    )
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ---------- serialisation helpers ----------

def _campaign_to_dict(c: Campaign) -> dict[str, Any]:
    return {
        "version": _SCHEMA_VERSION,
        "id": c.id,
        "name": c.name,
        "date_format": c.date_format,
        "players": [_player_to_dict(p) for p in c.players],
        "sessions": [_session_to_dict(s) for s in c.sessions],
    }


def _player_to_dict(p: Player) -> dict[str, Any]:
    return {
        "id": p.id,
        "name": p.name,
        "characters": [{"id": ch.id, "name": ch.name} for ch in p.characters],
    }


def _session_to_dict(s: Session) -> dict[str, Any]:
    return {
        "id": s.id,
        "number": s.number,
        "name": s.name,
        "date": s.date,
        "pre_notes": s.pre_notes,
        "summary": s.summary,
        "post_notes": s.post_notes,
        "kills": {
            char_id: [{"being": k.being, "count": k.count} for k in kills]
            for char_id, kills in s.kills.items()
        },
    }


# ---------- deserialisation helpers ----------

def _campaign_from_dict(d: dict[str, Any]) -> Campaign:
    return Campaign(
        id=d["id"],
        name=d["name"],
        date_format=d.get("date_format", "yyyy-MM-dd"),
        players=[_player_from_dict(p) for p in d.get("players", [])],
        sessions=[_session_from_dict(s) for s in d.get("sessions", [])],
    )


def _player_from_dict(d: dict[str, Any]) -> Player:
    return Player(
        id=d["id"],
        name=d["name"],
        characters=[Character(id=ch["id"], name=ch["name"]) for ch in d.get("characters", [])],
    )


def _session_from_dict(d: dict[str, Any]) -> Session:
    kills: dict[str, list[Kill]] = {}
    for char_id, kill_list in d.get("kills", {}).items():
        kills[char_id] = [Kill(being=k["being"], count=k["count"]) for k in kill_list]
    return Session(
        id=d["id"],
        number=d["number"],
        name=d.get("name"),
        date=d["date"],
        pre_notes=d.get("pre_notes", ""),
        summary=d.get("summary", ""),
        post_notes=d.get("post_notes", ""),
        kills=kills,
        dirty=False,
    )
