from __future__ import annotations

import json
from pathlib import Path


_USER_DICT_FILENAME = "user_dict.json"


class SpellChecker:
    """
    Thin wrapper around spylls.  Loads a .dic/.aff pair and maintains a
    user dictionary (added words) and an ignore list, both persisted to
    ~/.ttrpg_notes/user_dict.json.
    """

    def __init__(self, dic_path: Path) -> None:
        from spylls.hunspell import Dictionary  # type: ignore[import]

        # spylls expects the path without extension
        stem = dic_path.with_suffix("")
        self._dictionary = Dictionary.from_files(str(stem))
        self._data_dir = dic_path.parent.parent  # ~/.ttrpg_notes
        self._user_words: set[str] = set()
        self._ignore_list: set[str] = set()
        self._load_user_dict()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check(self, word: str) -> bool:
        """Return True if word is correctly spelled (or in user dict / ignore)."""
        if word in self._user_words or word in self._ignore_list:
            return True
        return self._dictionary.lookup(word)

    def suggest(self, word: str) -> list[str]:
        return list(self._dictionary.suggest(word))

    def add_to_dictionary(self, word: str) -> None:
        """Persist word to user dictionary."""
        self._user_words.add(word)
        self._save_user_dict()

    def add_to_ignore(self, word: str) -> None:
        """Add word to ignore list (persisted)."""
        self._ignore_list.add(word)
        self._save_user_dict()

    def words(self) -> list[str]:
        return sorted(self._user_words)

    def ignored_words(self) -> list[str]:
        return sorted(self._ignore_list)

    def remove_from_dictionary(self, word: str) -> None:
        self._user_words.discard(word)
        self._save_user_dict()

    def remove_from_ignore(self, word: str) -> None:
        self._ignore_list.discard(word)
        self._save_user_dict()

    def update_in_dictionary(self, old: str, new: str) -> None:
        self._user_words.discard(old)
        if new:
            self._user_words.add(new)
        self._save_user_dict()

    def update_in_ignore(self, old: str, new: str) -> None:
        self._ignore_list.discard(old)
        if new:
            self._ignore_list.add(new)
        self._save_user_dict()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _user_dict_path(self) -> Path:
        return self._data_dir / _USER_DICT_FILENAME

    def _load_user_dict(self) -> None:
        p = self._user_dict_path()
        if not p.exists():
            return
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            self._user_words = set(data.get("words", []))
            self._ignore_list = set(data.get("ignore", []))
        except (json.JSONDecodeError, OSError):
            pass

    def _save_user_dict(self) -> None:
        p = self._user_dict_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            json.dumps(
                {"words": sorted(self._user_words), "ignore": sorted(self._ignore_list)},
                indent=2,
            ),
            encoding="utf-8",
        )
