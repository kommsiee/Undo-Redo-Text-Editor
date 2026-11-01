"""Unit tests for Document model, undo/redo stacks, and coalescing."""

try:
    import pytest
except ImportError:
    class _MockPytest:
        @staticmethod
        def fixture(*args, **kwargs):
            return lambda f: f
        class mark:
            @staticmethod
            def parametrize(*args, **kwargs):
                return lambda f: f
    pytest = _MockPytest()

from models.buffer import StringBuffer, GapBuffer, PieceTable, Rope
from models.commands import InsertCommand, DeleteCommand
from models.document import Document


@pytest.fixture
def doc():
    return Document(buffer_type=PieceTable, max_history=10)


class TestDocumentUndoRedo:
    def test_basic_undo_redo(self, doc):
        cmd = InsertCommand(doc.buffer, 0, "Hello")
        doc.execute(cmd)
        assert doc.get_text() == "Hello"
        assert doc.can_undo
        assert not doc.can_redo

        doc.undo()
        assert doc.get_text() == ""
        assert not doc.can_undo
        assert doc.can_redo

        doc.redo()
        assert doc.get_text() == "Hello"

    def test_new_edit_clears_redo(self, doc):
        doc.execute(InsertCommand(doc.buffer, 0, "First"))
        doc.undo()
        assert doc.can_redo

        doc.execute(InsertCommand(doc.buffer, 0, "Second"))
        assert not doc.can_redo
        assert doc.get_text() == "Second"

    def test_empty_stack_returns_false(self, doc):
        assert not doc.undo()
        assert not doc.redo()

    def test_coalesced_typing_single_undo(self, doc):
        doc.execute(InsertCommand(doc.buffer, 0, "c"))
        doc.execute(InsertCommand(doc.buffer, 1, "a"))
        doc.execute(InsertCommand(doc.buffer, 2, "t"))

        assert doc.get_text() == "cat"
        assert len(doc.undo_stack) == 1

        doc.undo()
        assert doc.get_text() == ""

    def test_whitespace_breaks_coalescing(self, doc):
        doc.execute(InsertCommand(doc.buffer, 0, "h"))
        doc.execute(InsertCommand(doc.buffer, 1, "i"))
        doc.execute(InsertCommand(doc.buffer, 2, " "))
        doc.execute(InsertCommand(doc.buffer, 3, "!"))

        assert len(doc.undo_stack) >= 2

    def test_compound_context_manager(self, doc):
        with doc.compound("Batch insert"):
            doc.execute(InsertCommand(doc.buffer, 0, "A"))
            doc.execute(InsertCommand(doc.buffer, 1, "B"))
            doc.execute(InsertCommand(doc.buffer, 2, "C"))

        assert doc.get_text() == "ABC"
        assert len(doc.undo_stack) == 1

        doc.undo()
        assert doc.get_text() == ""

        doc.redo()
        assert doc.get_text() == "ABC"

    def test_bounded_history_capacity(self):
        doc = Document(max_history=5)
        for i in range(10):
            doc.execute(InsertCommand(doc.buffer, 0, f"{i} "))

        assert len(doc.undo_stack) == 5
        assert len(doc.redo_stack) == 0

    def test_save_modified_tracking(self, doc):
        assert not doc.is_modified
        doc.execute(InsertCommand(doc.buffer, 0, "Saved text"))
        assert doc.is_modified

        doc.mark_saved()
        assert not doc.is_modified

        doc.undo()
        assert doc.is_modified

        doc.redo()
        assert not doc.is_modified

    def test_macro_recording_and_replay(self, doc):
        doc.start_macro_recording()
        doc.execute(InsertCommand(doc.buffer, 0, "Line 1\n"))
        doc.execute(InsertCommand(doc.buffer, len(doc.buffer), "Line 2\n"))
        macro = doc.stop_macro_recording()

        assert len(macro) == 2

        doc.replay_macro(macro)
        assert doc.get_text() == "Line 1\nLine 2\nLine 1\nLine 2\n"

        doc.undo()
        assert doc.get_text() == "Line 1\nLine 2\n"

    def test_listeners_notification(self, doc):
        called = []
        doc.add_listener(lambda: called.append(True))

        doc.execute(InsertCommand(doc.buffer, 0, "Test"))
        assert len(called) == 1

        doc.undo()
        assert len(called) == 2

        doc.redo()
        assert len(called) == 3

    @pytest.mark.parametrize("b_cls", [StringBuffer, GapBuffer, PieceTable, Rope])
    def test_document_with_all_buffer_types(self, b_cls):
        doc = Document(buffer_type=b_cls)
        doc.execute(InsertCommand(doc.buffer, 0, "Universal"))
        assert doc.get_text() == "Universal"
        doc.undo()
        assert doc.get_text() == ""
        doc.redo()
        assert doc.get_text() == "Universal"
