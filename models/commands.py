import time
from abc import ABC, abstractmethod
from typing import Optional, List

from models.buffer import TextBuffer


class Command(ABC):
    """Abstract base class for reversible editing commands."""

    def __init__(self) -> None:
        self._timestamp: float = time.time()

    @abstractmethod
    def execute(self) -> None:
        pass

    @abstractmethod
    def undo(self) -> None:
        pass

    def redo(self) -> None:
        self.execute()

    @property
    @abstractmethod
    def description(self) -> str:
        pass

    @property
    def cursor_pos(self) -> Optional[int]:
        return None

    @property
    def undo_cursor_pos(self) -> Optional[int]:
        return None

    def can_merge(self, other: 'Command') -> bool:
        return False

    def merge(self, other: 'Command') -> None:
        raise NotImplementedError

    @property
    def timestamp(self) -> float:
        return self._timestamp


class InsertCommand(Command):
    _COALESCE_WINDOW: float = 2.0

    def __init__(self, buffer: TextBuffer, pos: int, text: str) -> None:
        super().__init__()
        self.buffer = buffer
        self.pos = pos
        self.text = text

    def execute(self) -> None:
        self.buffer.insert(self.pos, self.text)

    def undo(self) -> None:
        self.buffer.delete(self.pos, len(self.text))

    @property
    def cursor_pos(self) -> Optional[int]:
        return self.pos + len(self.text)

    @property
    def undo_cursor_pos(self) -> Optional[int]:
        return self.pos

    def can_merge(self, other: 'Command') -> bool:
        if not isinstance(other, InsertCommand):
            return False
        if len(self.text) == 0 or len(other.text) != 1:
            return False
        if other.text[0] in (' ', '\t', '\n', '\r'):
            return False
        if other.pos != self.pos + len(self.text):
            return False
        if other.timestamp - self._timestamp > self._COALESCE_WINDOW:
            return False
        return True

    def merge(self, other: 'Command') -> None:
        if not isinstance(other, InsertCommand):
            raise TypeError("Can only merge with another InsertCommand")
        self.text += other.text
        self._timestamp = other.timestamp

    @property
    def description(self) -> str:
        return "Type" if len(self.text) == 1 else "Insert"


class DeleteCommand(Command):
    _COALESCE_WINDOW: float = 2.0

    def __init__(self, buffer: TextBuffer, pos: int, length: int) -> None:
        super().__init__()
        self.buffer = buffer
        self.pos = pos
        self.length = length
        self._deleted_text: str = ""

    def execute(self) -> None:
        self._deleted_text = self.buffer.delete(self.pos, self.length)

    def undo(self) -> None:
        self.buffer.insert(self.pos, self._deleted_text)

    @property
    def cursor_pos(self) -> Optional[int]:
        return self.pos

    @property
    def undo_cursor_pos(self) -> Optional[int]:
        return self.pos + self.length

    def can_merge(self, other: 'Command') -> bool:
        if not isinstance(other, DeleteCommand):
            return False
        if other.pos != self.pos - other.length:
            return False
        if other.timestamp - self._timestamp > self._COALESCE_WINDOW:
            return False
        return True

    def merge(self, other: 'Command') -> None:
        if not isinstance(other, DeleteCommand):
            raise TypeError("Can only merge with another DeleteCommand")
        self._deleted_text = other._deleted_text + self._deleted_text
        self.pos = other.pos
        self.length += other.length
        self._timestamp = other.timestamp

    @property
    def description(self) -> str:
        return "Delete"


class ReplaceCommand(Command):
    def __init__(self, buffer: TextBuffer, pos: int, length: int, new_text: str) -> None:
        super().__init__()
        self.buffer = buffer
        self.pos = pos
        self.length = length
        self.new_text = new_text
        self._old_text: str = ""

    def execute(self) -> None:
        self._old_text = self.buffer.delete(self.pos, self.length)
        self.buffer.insert(self.pos, self.new_text)

    def undo(self) -> None:
        self.buffer.delete(self.pos, len(self.new_text))
        self.buffer.insert(self.pos, self._old_text)

    @property
    def cursor_pos(self) -> Optional[int]:
        return self.pos + len(self.new_text)

    @property
    def undo_cursor_pos(self) -> Optional[int]:
        return self.pos + self.length

    @property
    def description(self) -> str:
        return "Replace"


class CompoundCommand(Command):
    """Groups multiple commands into a single atomic undo/redo unit."""

    def __init__(self, commands: List[Command], description: str = "") -> None:
        super().__init__()
        self.commands = list(commands)
        self._description = description
        self._executed: bool = False

    def execute(self) -> None:
        if self._executed:
            return
        for cmd in self.commands:
            cmd.execute()
        self._executed = True

    def undo(self) -> None:
        for cmd in reversed(self.commands):
            cmd.undo()
        self._executed = False

    def redo(self) -> None:
        for cmd in self.commands:
            cmd.redo()
        self._executed = True

    @property
    def cursor_pos(self) -> Optional[int]:
        return self.commands[-1].cursor_pos if self.commands else None

    @property
    def undo_cursor_pos(self) -> Optional[int]:
        return self.commands[0].undo_cursor_pos if self.commands else None

    def can_merge(self, other: 'Command') -> bool:
        return False

    @property
    def description(self) -> str:
        return self._description or "Compound edit"
