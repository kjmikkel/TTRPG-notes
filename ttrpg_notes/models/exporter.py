from __future__ import annotations

from datetime import datetime

from ttrpg_notes.models.campaign import Campaign, Session


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _qt_date_format(qt_fmt: str, dt: datetime) -> str:
    """
    Render *dt* using a Qt date format string (e.g. ``"MMMM d, yyyy"``).

    Tokens are processed longest-first so that e.g. ``"MMMM"`` is matched
    before ``"MM"`` or ``"M"``.  Single ``d`` and ``M`` emit the value
    without zero-padding, matching Qt's behaviour.
    """
    result: list[str] = []
    i = 0
    while i < len(qt_fmt):
        if qt_fmt[i] == "'":
            # Quoted literal: scan to closing quote and emit verbatim.
            # Qt's spec: '' (empty) → a literal single-quote character.
            j = i + 1
            while j < len(qt_fmt) and qt_fmt[j] != "'":
                j += 1
            if j == i + 1:
                result.append("'")   # '' → literal apostrophe
            else:
                result.append(qt_fmt[i + 1 : j])
            i = j + 1
        elif qt_fmt[i : i + 4] == "yyyy":
            result.append(dt.strftime("%Y")); i += 4
        elif qt_fmt[i : i + 2] == "yy":
            result.append(dt.strftime("%y")); i += 2
        elif qt_fmt[i : i + 4] == "MMMM":
            result.append(dt.strftime("%B")); i += 4
        elif qt_fmt[i : i + 3] == "MMM":
            result.append(dt.strftime("%b")); i += 3
        elif qt_fmt[i : i + 2] == "MM":
            result.append(dt.strftime("%m")); i += 2
        elif qt_fmt[i] == "M":
            result.append(str(dt.month)); i += 1
        elif qt_fmt[i : i + 4] == "dddd":
            result.append(dt.strftime("%A")); i += 4
        elif qt_fmt[i : i + 3] == "ddd":
            result.append(dt.strftime("%a")); i += 3
        elif qt_fmt[i : i + 2] == "dd":
            result.append(dt.strftime("%d")); i += 2
        elif qt_fmt[i] == "d":
            result.append(str(dt.day)); i += 1
        else:
            result.append(qt_fmt[i]); i += 1
    return "".join(result)


def _format_date(date_str: str, date_format: str) -> str:
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return date_str
    return _qt_date_format(date_format, dt)


def _single_session_kills(session: Session) -> dict[str, dict[str, int]]:
    """Return {char_id: {being: total_count}} for one session only."""
    result: dict[str, dict[str, int]] = {}
    for char_id, kills in session.kills.items():
        bucket: dict[str, int] = {}
        for k in kills:
            bucket[k.being] = bucket.get(k.being, 0) + k.count
        if bucket:
            result[char_id] = bucket
    return result


def _cumulative_kills(campaign: Campaign, up_to_idx: int) -> dict[str, dict[str, int]]:
    """Return {char_id: {being: total_count}} for sessions 0..up_to_idx inclusive."""
    result: dict[str, dict[str, int]] = {}
    for session in campaign.sessions[: up_to_idx + 1]:
        for char_id, kills in session.kills.items():
            bucket = result.setdefault(char_id, {})
            for k in kills:
                bucket[k.being] = bucket.get(k.being, 0) + k.count
    return result


def _kills_lines(
    campaign: Campaign,
    kills_by_char: dict[str, dict[str, int]],
    bullet: str = "  ",
    include_empty: bool = False,
) -> list[str]:
    """
    Return one formatted line per character, ordered by player then character
    as they appear in campaign.players.  Characters with no kills are omitted
    unless *include_empty* is True, in which case they appear as "—".
    """
    lines: list[str] = []
    for player in campaign.players:
        for char in player.characters:
            being_counts = kills_by_char.get(char.id, {})
            if not being_counts:
                if include_empty:
                    lines.append(f"{bullet}{char.name}: —")
                continue
            parts = ", ".join(
                f"{being} x{count}"
                for being, count in sorted(being_counts.items())
            )
            lines.append(f"{bullet}{char.name}: {parts}")
    return lines


# ---------------------------------------------------------------------------
# Text export
# ---------------------------------------------------------------------------

def export_text(
    campaign: Campaign,
    *,
    include_kills: bool,
    include_pre: bool,
    include_post: bool,
    include_total: bool,
) -> str:
    out: list[str] = [campaign.name, ""]

    for idx, session in enumerate(campaign.sessions):
        # Session heading
        date_str = _format_date(session.date, campaign.date_format) if session.date else ""
        if session.name and date_str:
            label = f"{session.name} - {date_str}"
        elif session.name:
            label = session.name
        elif date_str:
            label = date_str
        else:
            label = f"Session {session.number}"

        out.append(f"{label}:")
        out.append("")

        # Kill count (optional)
        if include_kills:
            kills = _single_session_kills(session)
            lines = _kills_lines(campaign, kills, bullet="  ")
            if lines:
                out.append("Kill count:")
                out.extend(lines)
                out.append("")

        # Pre-session notes (optional)
        pre = session.pre_notes.strip()
        if include_pre and pre:
            out.append(pre)
            out.append("")

        # Session notes (mandatory)
        summary = session.summary.strip()
        if include_pre and pre and summary:
            out.append("---")
            out.append("")
        if summary:
            out.append(summary)
            out.append("")

        # Post-session notes (optional)
        post = session.post_notes.strip()
        if include_post and post:
            if summary:
                out.append("---")
                out.append("")
            out.append(post)
            out.append("")

    # Total kill count (optional)
    if include_total and campaign.sessions:
        total = _cumulative_kills(campaign, len(campaign.sessions) - 1)
        lines = _kills_lines(campaign, total, bullet="  ", include_empty=True)
        if lines:
            out.append("---")
            out.append("")
            out.append("Total kill count:")
            out.extend(lines)
            out.append("")

    return "\n".join(out)


# ---------------------------------------------------------------------------
# Markdown export  (Homebrewery-compatible)
# ---------------------------------------------------------------------------

def export_markdown(
    campaign: Campaign,
    *,
    include_kills: bool,
    include_pre: bool,
    include_post: bool,
    include_total: bool,
) -> str:
    out: list[str] = [f"# {campaign.name}", ""]

    for idx, session in enumerate(campaign.sessions):
        # Session heading
        date_str = _format_date(session.date, campaign.date_format) if session.date else ""
        if session.name:
            out.append(f"## {session.name}")
            if date_str:
                out.append(f"### {date_str}")
        elif date_str:
            out.append(f"## {date_str}")
        else:
            out.append(f"## Session {session.number}")
        out.append("")

        # Kill count as Homebrewery {{note}} (optional)
        if include_kills:
            kills = _single_session_kills(session)
            lines = _kills_lines(campaign, kills, bullet="- ")
            if lines:
                out.append("{{note")
                out.append("**Kill count**")
                out.append("")
                out.extend(lines)
                out.append("}}")
                out.append("")

        # Pre-session notes (optional)
        pre = session.pre_notes.strip()
        if include_pre and pre:
            out.append(pre)
            out.append("")

        # Session notes (mandatory)
        summary = session.summary.strip()
        if include_pre and pre and summary:
            out.append("---")
            out.append("")
        if summary:
            out.append(summary)
            out.append("")

        # Post-session notes (optional)
        post = session.post_notes.strip()
        if include_post and post:
            if summary:
                out.append("---")
                out.append("")
            out.append(post)
            out.append("")

    # Total kill count on a new page as Homebrewery {{note}} (optional)
    if include_total and campaign.sessions:
        total = _cumulative_kills(campaign, len(campaign.sessions) - 1)
        lines = _kills_lines(campaign, total, bullet="- ", include_empty=True)
        if lines:
            out.append("\\page")
            out.append("")
            out.append("{{note")
            out.append("**Total kill count**")
            out.append("")
            out.extend(lines)
            out.append("}}")
            out.append("")

    return "\n".join(out)
