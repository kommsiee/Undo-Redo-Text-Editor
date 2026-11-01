"""Unit tests for Command Pattern implementations and coalescing."""

import time
try:
    import pytest
except ImportError:
    class _MockPytest:
        @staticmethod
        def fixture(*args, **kwargs):
            return lambda f: f
    pytest = _MockPytest()

from models.buffer import PieceTable
from models.commands import InsertCommand, DeleteCommand, ReplaceCommand, CompoundCommand


@pytest.fixture
def buffer():
    return PieceTable("Initial Text")


class TestInsertCommand:
    def test_insert_execute_undo_redo(self, buffer):
        cmd = InsertCommand(buffer, 0, "Prefix: ")
        cmd.execute()
        assert buffer.get_text() == "Prefix: Initial Text"
        assert cmd.cursor_pos == len("Prefix: ")

        cmd.undo()
        assert buffer.get_text() == "Initial Text"
        assert cmd.undo_cursor_pos == 0

        cmd.redo()
        assert buffer.get_text() == "Prefix: Initial Text"

    def test_coalescing_consecutive_characters(self, buffer):
        cmd1 = InsertCommand(buffer, 7, "a")
        cmd2 = InsertCommand(buffer, 8, "b")
        assert cmd1.can_merge(cmd2)

        cmd1.merge(cmd2)
        assert cmd1.text == "ab"
        assert cmd1.cursor_pos == 9

    def test_coalescing_word_boundary_whitespace(self, buffer):
        cmd1 = InsertCommand(buffer, 7, "a")
        cmd_space = InsertCommand(buffer, 8, " ")
        assert not cmd1.can_merge(cmd_space)

    def test_coalescing_non_adjacent(self, buffer):
        cmd1 = InsertCommand(buffer, 0, "a")
        cmd2 = InsertCommand(buffer, 5, "b")
        assert not cmd1.can_merge(cmd2)

    def test_coalescing_timeout(self, buffer):
        cmd1 = InsertCommand(buffer, 0, "a")
        cmd2 = InsertCommand(buffer, 1, "b")
        cmd1._timestamp = time.time() - 3.0
        assert not cmd1.can_merge(cmd2)


class TestDeleteCommand:
    def test_delete_execute_undo_redo(self, buffer):
        cmd = DeleteCommand(buffer, 0, 7)
        cmd.execute()
        assert buffer.get_text() == " Text"
        assert cmd.cursor_pos == 0

        cmd.undo()
        assert buffer.get_text() == "Initial Text"
        assert cmd.undo_cursor_pos == 7

        cmd.redo()
        assert buffer.get_text() == " Text"

    def test_coalescing_backspace(self, buffer):
        cmd1 = DeleteCommand(buffer, 4, 1)
        cmd1.execute()
        cmd2 = DeleteCommand(buffer, 3, 1)
        cmd2.execute()

        assert cmd1.can_merge(cmd2)
        cmd1.merge(cmd2)
        assert cmd1.pos == 3
        assert cmd1.length == 2

        cmd1.undo()
        assert buffer.get_text() == "Initial Text"


class TestReplaceCommand:
    def test_replace_execute_undo_redo(self, buffer):
        cmd = ReplaceCommand(buffer, 8, 4, "Data")
        cmd.execute()
        assert buffer.get_text() == "Initial Data"
        assert cmd.cursor_pos == 12

        cmd.undo()
        assert buffer.get_text() == "Initial Text"
        assert cmd.undo_cursor_pos == 12

        cmd.redo()
        assert buffer.get_text() == "Initial Data"


class TestCompoundCommand:
    def test_compound_execute_undo_redo(self, buffer):
        cmd1 = InsertCommand(buffer, 0, "[START] ")
        cmd2 = InsertCommand(buffer, len(buffer) + len("[START] "), " [END]")
        compound = CompoundCommand([cmd1, cmd2], description="Wrap text")

        compound.execute()
        assert buffer.get_text() == "[START] Initial Text [END]"

        compound.undo()
        assert buffer.get_text() == "Initial Text"

        compound.redo()
        assert buffer.get_text() == "[START] Initial Text [END]"

    def test_compound_already_executed_guard(self, buffer):
        cmd1 = InsertCommand(buffer, 0, "A")
        cmd1.execute()
        compound = CompoundCommand([cmd1])
        compound._executed = True

        compound.execute()
        assert buffer.get_text() == "AInitial Text"
