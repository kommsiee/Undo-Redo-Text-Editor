"""Unit tests for UndoTree branching history."""

from models.buffer import StringBuffer
from models.commands import InsertCommand
from models.undo_tree import UndoTree


def test_undo_tree_linear():
    tree = UndoTree()
    buf = StringBuffer()

    c1 = InsertCommand(buf, 0, "A")
    c1.execute()
    tree.push(c1)

    c2 = InsertCommand(buf, 1, "B")
    c2.execute()
    tree.push(c2)

    assert tree.can_undo
    undone_cmd = tree.undo()
    assert undone_cmd == c2
    undone_cmd.undo()
    assert buf.get_text() == "A"

    redone_cmd = tree.redo()
    assert redone_cmd == c2
    redone_cmd.redo()
    assert buf.get_text() == "AB"


def test_undo_tree_branching():
    tree = UndoTree()
    buf = StringBuffer()

    c1 = InsertCommand(buf, 0, "Base")
    c1.execute()
    tree.push(c1)

    # Branch 1
    c2a = InsertCommand(buf, 4, "-A")
    c2a.execute()
    tree.push(c2a)
    assert buf.get_text() == "Base-A"

    # Undo to Base
    tree.undo().undo()
    assert buf.get_text() == "Base"

    # Branch 2 (instead of discarding Branch 1!)
    c2b = InsertCommand(buf, 4, "-B")
    c2b.execute()
    tree.push(c2b)
    assert buf.get_text() == "Base-B"

    # Undo back to Base
    tree.undo().undo()
    assert buf.get_text() == "Base"

    # We now have 2 branches from Base
    branches = tree.get_branches()
    assert len(branches) == 2

    # Switch to Branch 1 (-A)
    assert tree.switch_branch(0)
    redone = tree.redo()
    redone.redo()
    assert buf.get_text() == "Base-A"

