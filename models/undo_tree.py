from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional, List
from models.commands import Command


@dataclass
class UndoNode:
    command: Optional[Command] = None
    parent: Optional[UndoNode] = None
    children: List[UndoNode] = field(default_factory=list)
    active_child_index: int = 0
    timestamp: float = field(default_factory=time.time)

    @property
    def description(self) -> str:
        return self.command.description if self.command else "Root"


class UndoTree:
    """Branching undo/redo history tree."""

    def __init__(self) -> None:
        self.root: UndoNode = UndoNode()
        self.current: UndoNode = self.root

    def push(self, command: Command) -> UndoNode:
        node = UndoNode(command=command, parent=self.current)
        self.current.children.append(node)
        self.current.active_child_index = len(self.current.children) - 1
        self.current = node
        return node

    def undo(self) -> Optional[Command]:
        if self.current.parent is None:
            return None
        cmd = self.current.command
        self.current = self.current.parent
        return cmd

    def redo(self) -> Optional[Command]:
        if not self.current.children:
            return None
        idx = self.current.active_child_index
        if not (0 <= idx < len(self.current.children)):
            idx = 0
            self.current.active_child_index = 0
        node = self.current.children[idx]
        self.current = node
        return node.command

    def switch_branch(self, branch_index: int) -> bool:
        if 0 <= branch_index < len(self.current.children):
            self.current.active_child_index = branch_index
            return True
        return False

    def get_branches(self) -> List[UndoNode]:
        return list(self.current.children)

    @property
    def can_undo(self) -> bool:
        return self.current.parent is not None

    @property
    def can_redo(self) -> bool:
        return len(self.current.children) > 0
