from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional

from models.buffer import TextBuffer
from models.commands import Command, CompoundCommand, ReplaceCommand


@dataclass
class SearchOptions:
    case_sensitive: bool = False
    regex: bool = False
    whole_word: bool = False


@dataclass
class SearchResult:
    start: int
    end: int
    match_text: str


def _compile_pattern(query: str, options: SearchOptions) -> Optional[re.Pattern]:
    if not query:
        return None

    pattern = query if options.regex else re.escape(query)

    if options.whole_word:
        pattern = rf"\b(?:{pattern})\b"

    flags = re.UNICODE
    if not options.case_sensitive:
        flags |= re.IGNORECASE

    try:
        return re.compile(pattern, flags)
    except re.error:
        return None


class SearchEngine:
    """Pattern matching and replace engine supporting regex and word boundaries."""

    def __init__(self) -> None:
        self._last_query: str = ""
        self._last_options: Optional[SearchOptions] = None
        self._cached_results: List[SearchResult] = []
        self._current_index: int = -1

    def find_all(
        self,
        text: str,
        query: str,
        options: SearchOptions | None = None,
    ) -> List[SearchResult]:
        if options is None:
            options = SearchOptions()

        if query == self._last_query and options == self._last_options:
            return list(self._cached_results)

        results: List[SearchResult] = []

        if not query:
            self._update_cache(query, options, results)
            return results

        compiled = _compile_pattern(query, options)
        if compiled is None:
            self._update_cache(query, options, results)
            return results

        for m in compiled.finditer(text):
            if m.start() == m.end():
                continue
            results.append(
                SearchResult(start=m.start(), end=m.end(), match_text=m.group())
            )

        self._update_cache(query, options, results)
        return list(results)

    def find_next(
        self,
        text: str,
        query: str,
        from_pos: int = 0,
        options: SearchOptions | None = None,
    ) -> Optional[SearchResult]:
        results = self.find_all(text, query, options)
        if not results:
            self._current_index = -1
            return None

        for i, r in enumerate(results):
            if r.start >= from_pos:
                self._current_index = i
                return r

        self._current_index = 0
        return results[0]

    def find_previous(
        self,
        text: str,
        query: str,
        from_pos: int = 0,
        options: SearchOptions | None = None,
    ) -> Optional[SearchResult]:
        results = self.find_all(text, query, options)
        if not results:
            self._current_index = -1
            return None

        for i in range(len(results) - 1, -1, -1):
            if results[i].start < from_pos:
                self._current_index = i
                return results[i]

        self._current_index = len(results) - 1
        return results[-1]

    @property
    def current_match_index(self) -> int:
        return self._current_index

    @property
    def match_count(self) -> int:
        return len(self._cached_results)

    def replace_one(
        self,
        buffer: TextBuffer,
        match: SearchResult,
        replacement: str,
    ) -> ReplaceCommand:
        actual_replacement = self._expand_replacement(match, replacement)
        return ReplaceCommand(buffer, match.start, match.end - match.start, actual_replacement)

    def replace_all(
        self,
        buffer: TextBuffer,
        text: str,
        query: str,
        replacement: str,
        options: SearchOptions | None = None,
    ) -> Optional[CompoundCommand]:
        results = self.find_all(text, query, options)
        if not results:
            return None

        commands: List[Command] = []
        for match in reversed(results):
            actual_replacement = self._expand_replacement(match, replacement)
            cmd = ReplaceCommand(
                buffer,
                match.start,
                match.end - match.start,
                actual_replacement,
            )
            commands.append(cmd)

        return CompoundCommand(commands, description="Replace All")

    def invalidate_cache(self) -> None:
        self._last_query = ""
        self._last_options = None
        self._cached_results = []
        self._current_index = -1

    def _update_cache(
        self,
        query: str,
        options: SearchOptions,
        results: List[SearchResult],
    ) -> None:
        self._last_query = query
        self._last_options = options
        self._cached_results = list(results)
        self._current_index = -1

    def _expand_replacement(
        self,
        match: SearchResult,
        replacement: str,
    ) -> str:
        if (
            self._last_options is not None
            and self._last_options.regex
            and self._last_query
        ):
            compiled = _compile_pattern(self._last_query, self._last_options)
            if compiled is not None:
                try:
                    return compiled.sub(replacement, match.match_text, count=1)
                except re.error:
                    return replacement
        return replacement
