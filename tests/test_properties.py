import random
try:
    import pytest
except ImportError:
    class _MockPytest:
        class mark:
            @staticmethod
            def parametrize(*args, **kwargs):
                return lambda f: f
    pytest = _MockPytest()

from models.buffer import StringBuffer, GapBuffer, PieceTable, Rope
from models.commands import InsertCommand, DeleteCommand
from models.document import Document

try:
    import hypothesis
    from hypothesis import given, settings, strategies as st
    HAS_HYPOTHESIS = True
except ImportError:
    HAS_HYPOTHESIS = False


@pytest.mark.parametrize("b_cls", [StringBuffer, GapBuffer, PieceTable, Rope])
def test_randomized_insert_delete_roundtrip(b_cls):
    rng = random.Random(42)
    for _ in range(50):
        initial = "".join(rng.choices("abcdefghijklmnopqrstuvwxyz 1234567890\n", k=rng.randint(0, 100)))
        buf = b_cls(initial)

        insert_text = "".join(rng.choices("ABCXYZ!@#$", k=rng.randint(1, 30)))
        pos = rng.randint(0, len(buf))

        buf.insert(pos, insert_text)
        buf.delete(pos, len(insert_text))

        assert buf.get_text() == initial
        assert len(buf) == len(initial)


def test_four_buffers_cross_consistency():
    rng = random.Random(1337)
    buffers = [StringBuffer(), GapBuffer(), PieceTable(), Rope()]

    for step in range(200):
        curr_len = len(buffers[0])
        op = "insert" if curr_len == 0 or rng.random() < 0.65 else "delete"

        if op == "insert":
            text = "".join(rng.choices("abcdefg 123 \n", k=rng.randint(1, 10)))
            pos = rng.randint(0, curr_len)
            for b in buffers:
                b.insert(pos, text)
        else:
            pos = rng.randint(0, curr_len - 1)
            length = rng.randint(1, min(curr_len - pos, 10))
            deleted_results = [b.delete(pos, length) for b in buffers]
            assert len(set(deleted_results)) == 1

        ref_text = buffers[0].get_text()
        for b in buffers[1:]:
            assert len(b) == len(ref_text)
            assert b.get_text() == ref_text


def test_document_undo_redo_roundtrip_property():
    rng = random.Random(999)
    doc = Document(buffer_type=PieceTable, max_history=1000)

    for _ in range(30):
        if len(doc.buffer) == 0 or rng.random() < 0.7:
            pos = rng.randint(0, len(doc.buffer))
            text = "".join(rng.choices("word ", k=rng.randint(1, 5)))
            doc.execute(InsertCommand(doc.buffer, pos, text))
        else:
            pos = rng.randint(0, len(doc.buffer) - 1)
            length = rng.randint(1, min(len(doc.buffer) - pos, 4))
            doc.execute(DeleteCommand(doc.buffer, pos, length))

    final_text = doc.get_text()
    stack_depth = len(doc.undo_stack)

    for _ in range(stack_depth):
        doc.undo()
    assert doc.get_text() == ""

    for _ in range(stack_depth):
        doc.redo()
    assert doc.get_text() == final_text


def test_get_range_invariant():
    rng = random.Random(2024)
    for b_cls in [StringBuffer, GapBuffer, PieceTable, Rope]:
        text = "The quick brown fox jumps over the lazy dog"
        buf = b_cls(text)
        assert buf.get_range(0, len(buf)) == buf.get_text()

        split = rng.randint(0, len(buf))
        left = buf.get_range(0, split)
        right = buf.get_range(split, len(buf))
        assert left + right == text


if HAS_HYPOTHESIS:
    @given(st.text())
    @settings(max_examples=100)
    def test_hypothesis_set_text(text):
        for b_cls in [StringBuffer, GapBuffer, PieceTable, Rope]:
            buf = b_cls()
            buf.set_text(text)
            assert buf.get_text() == text
            assert len(buf) == len(text)
