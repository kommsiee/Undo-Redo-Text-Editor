"""Tab state management for multi-tab text editing."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List
from models.document import Document
from models.search import SearchEngine
from models.commands import Command


@dataclass
class TabState:
    """Encapsulates state for an open editor tab."""
    document: Document
    filepath: Optional[str] = None
    title: str = "Untitled"
    search_engine: SearchEngine = field(default_factory=SearchEngine)
    macro_commands: Optional[List[Command]] = None
    is_recording_macro: bool = False

