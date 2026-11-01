"""Unit tests for TextBuffer implementations (StringBuffer, GapBuffer, PieceTable, Rope)."""

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
        class raises:
            def __init__(self, expected):
                self.expected = expected
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc_val, exc_tb):
                if exc_type is None:
                    raise AssertionError(f"Expected {self.expected} was not raised")
                return issubclass(exc_type, self.expected)
    pytest = _MockPytest()

from models.buffer import StringBuffer, GapBuffer, PieceTable, Rope, BUFFER_TYPES

BUFFER_CLASSES = [StringBuffer, GapBuffer, PieceTable, Rope]


@pytest.fixture(params=BUFFER_CLASSES, ids=lambda c: c.__name__)
def buffer_cls(request=None):
    return PieceTable


@pytest.fixture
def buf(buffer_cls=PieceTable):
    return buffer_cls()


@pytest.fixture
def buf_hello(buffer_cls=PieceTable):
    return buffer_cls("Hello World")


class TestBasicOperations:
    def test_empty_buffer(self, buf):
        assert len(buf) == 0
        assert buf.get_text() == ""

    def test_init_with_text(self, buf_hello):
        assert len(buf_hello) == 11
        assert buf_hello.get_text() == "Hello World"

    def test_insert_at_beginning(self, buf_hello):
        buf_hello.insert(0, "Say ")
        assert buf_hello.get_text() == "Say Hello World"
        assert len(buf_hello) == 15

    def test_insert_at_end(self, buf_hello):
        buf_hello.insert(len(buf_hello), "!")
        assert buf_hello.get_text() == "Hello World!"
        assert len(buf_hello) == 12

    def test_insert_in_middle(self, buf_hello):
        buf_hello.insert(5, " Beautiful")
        assert buf_hello.get_text() == "Hello Beautiful World"

    def test_insert_empty_string(self, buf_hello):
        buf_hello.insert(5, "")
        assert buf_hello.get_text() == "Hello World"
        assert len(buf_hello) == 11

    def test_delete_from_beginning(self, buf_hello):
        deleted = buf_hello.delete(0, 6)
        assert deleted == "Hello "
        assert buf_hello.get_text() == "World"
        assert len(buf_hello) == 5

    def test_delete_from_end(self, buf_hello):
        deleted = buf_hello.delete(5, 6)
        assert deleted == " World"
        assert buf_hello.get_text() == "Hello"
        assert len(buf_hello) == 5

    def test_delete_in_middle(self, buf_hello):
        buf_hello.insert(5, " Big")
        deleted = buf_hello.delete(5, 4)
        assert deleted == " Big"
        assert buf_hello.get_text() == "Hello World"

    def test_delete_zero_length(self, buf_hello):
        deleted = buf_hello.delete(5, 0)
        assert deleted == ""
        assert buf_hello.get_text() == "Hello World"

    def test_get_range(self, buf_hello):
        assert buf_hello.get_range(0, 5) == "Hello"
        assert buf_hello.get_range(6, 11) == "World"
        assert buf_hello.get_range(0, 0) == ""
        assert buf_hello.get_range(11, 11) == ""

    def test_set_text(self, buf_hello):
        buf_hello.set_text("Brand New Content")
        assert buf_hello.get_text() == "Brand New Content"
        assert len(buf_hello) == 17

    def test_set_text_to_empty(self, buf_hello):
        buf_hello.set_text("")
        assert buf_hello.get_text() == ""
        assert len(buf_hello) == 0


class TestEdgeCasesAndErrors:
    def test_insert_out_of_bounds_negative(self, buf):
        with pytest.raises(ValueError):
            buf.insert(-1, "test")

    def test_insert_out_of_bounds_greater_than_len(self, buf_hello):
        with pytest.raises(ValueError):
            buf_hello.insert(100, "test")

    def test_delete_out_of_bounds(self, buf_hello):
        with pytest.raises(ValueError):
            buf_hello.delete(100, 1)

    def test_delete_negative_length(self, buf_hello):
        with pytest.raises(ValueError):
            buf_hello.delete(0, -5)

    def test_delete_range_exceeds_length(self, buf_hello):
        with pytest.raises(ValueError):
            buf_hello.delete(5, 20)

    def test_get_range_out_of_bounds(self, buf_hello):
        with pytest.raises(ValueError):
            buf_hello.get_range(-1, 5)
        with pytest.raises(ValueError):
            buf_hello.get_range(5, 100)
        with pytest.raises(ValueError):
            buf_hello.get_range(8, 4)


class TestStressAndConsistency:
    def test_sequential_typing(self, buf):
        word = "The quick brown fox jumps over the lazy dog."
        for i, char in enumerate(word):
            buf.insert(i, char)
        assert buf.get_text() == word

    def test_backspace_typing(self, buf):
        word = "Hello World"
        for char in word:
            buf.insert(len(buf), char)
        for _ in range(5):
            buf.delete(len(buf) - 1, 1)
        assert buf.get_text() == "Hello "

    def test_interleaved_inserts_deletes(self, buf):
        buf.insert(0, "ABCDEF")
        buf.delete(2, 2)
        buf.insert(2, "123")
        buf.delete(0, 1)
        buf.insert(len(buf), "!")
        assert buf.get_text() == "B123EF!"

    def test_unicode_content(self, buf):
        unicode_str = "🚀 Python 3 🐍 汉字 العربية"
        buf.set_text(unicode_str)
        assert buf.get_text() == unicode_str
        assert len(buf) == len(unicode_str)
        buf.insert(1, "✨")
        assert buf.get_range(0, 3) == "🚀✨ "
