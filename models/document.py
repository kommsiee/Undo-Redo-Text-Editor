from collections import deque
from contextlib import contextmanager
from typing import Optional, Callable, List

from models.buffer import TextBuffer, PieceTable
from models.commands import Command, CompoundCommand


class Document:
    """Document model managing text buffer and command-based undo/redo stacks."""

    def __init__(self, buffer_type=None, max_history: int = 500) -> None:
        if buffer_type is None:
            buffer_type = PieceTable

        self.buffer: TextBuffer = buffer_type()
        self.undo_stack: deque = deque(maxlen=max_history)
        self.redo_stack: deque = deque(maxlen=max_history)
        self.history: deque = deque(maxlen=max_history)

        self._modified: bool = False
        self._save_point: Optional[int] = 0
        self._listeners: List[Callable] = []

        self._compound_depth: int = 0
        self._compound_commands: List[Command] = []
        self._compound_description: str = ""

        self._macro_recording: bool = False
        self._macro_commands: List[Command] = []

    def execute(self, command: Command) -> None:
        if self._compound_depth > 0:
            command.execute()
            self._compound_commands.append(command)
            if self._macro_recording:
                self._macro_commands.append(command)
            return

        if self.undo_stack and self.undo_stack[-1].can_merge(command):
            command.execute()
            self.undo_stack[-1].merge(command)
            if self.history:
                self.history[-1] = self.undo_stack[-1].description
        else:
            command.execute()
            self.undo_stack.append(command)
            self.redo_stack.clear()
            self.history.append(command.description)

        self._modified = True
        if self._macro_recording:
            self._macro_commands.append(command)

        self._notify()

    def undo(self) -> bool:
        if not self.undo_stack:
            return False

        command = self.undo_stack.pop()
        command.undo()
        self.redo_stack.append(command)

        self.history.append(f"Undo: {command.description}")
        self._update_modified()
        self._notify()
        return True

    def redo(self) -> bool:
        if not self.redo_stack:
            return False

        command = self.redo_stack.pop()
        command.redo()
        self.undo_stack.append(command)

        self.history.append(f"Redo: {command.description}")
        self._update_modified()
        self._notify()
        return True

    @property
    def can_undo(self) -> bool:
        return len(self.undo_stack) > 0

    @property
    def can_redo(self) -> bool:
        return len(self.redo_stack) > 0

    def begin_compound(self, description: str = "") -> None:
        self._compound_depth += 1
        if self._compound_depth == 1:
            self._compound_commands = []
            self._compound_description = description

    def end_compound(self) -> None:
        if self._compound_depth <= 0:
            return

        self._compound_depth -= 1
        if self._compound_depth == 0 and self._compound_commands:
            compound = CompoundCommand(
                list(self._compound_commands),
                self._compound_description,
            )
            compound._executed = True
            self.undo_stack.append(compound)
            self.redo_stack.clear()
            self.history.append(compound.description)
            self._modified = True
            self._compound_commands = []
            self._notify()

    @contextmanager
    def compound(self, description: str = ""):
        self.begin_compound(description)
        try:
            yield
        finally:
            self.end_compound()

    def get_text(self) -> str:
        return self.buffer.get_text()

    def set_text(self, text: str) -> None:
        from models.commands import InsertCommand, DeleteCommand

        current = self.buffer.get_text()
        with self.compound("Set text"):
            if current:
                self.execute(DeleteCommand(self.buffer, 0, len(current)))
            if text:
                self.execute(InsertCommand(self.buffer, 0, text))

    def mark_saved(self) -> None:
        self._save_point = len(self.undo_stack)
        self._modified = False
        self._notify()

    @property
    def is_modified(self) -> bool:
        return self._modified

    def _update_modified(self) -> None:
        if self._save_point is None:
            self._modified = True
        else:
            self._modified = len(self.undo_stack) != self._save_point

    def add_listener(self, callback: Callable) -> None:
        if callback not in self._listeners:
            self._listeners.append(callback)

    def remove_listener(self, callback: Callable) -> None:
        try:
            self._listeners.remove(callback)
        except ValueError:
            pass

    def _notify(self) -> None:
        for listener in self._listeners:
            listener()

    def start_macro_recording(self) -> None:
        self._macro_recording = True
        self._macro_commands = []

    def stop_macro_recording(self) -> List[Command]:
        self._macro_recording = False
        commands = list(self._macro_commands)
        self._macro_commands = []
        return commands

    def replay_macro(self, commands: List[Command]) -> None:
        with self.compound("Macro replay"):
            for cmd in commands:
                cmd.redo()
                self._compound_commands.append(cmd)

    def get_history(self) -> List[str]:
        return list(self.history)
