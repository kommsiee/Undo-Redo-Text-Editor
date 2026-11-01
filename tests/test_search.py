"""Unit tests for SearchEngine, regex matching, and back-to-front Replace All."""

try:
    import pytest
except ImportError:
    class _MockPytest:
        @staticmethod
        def fixture(*args, **kwargs):
            return lambda f: f
    pytest = _MockPytest()

from models.buffer import PieceTable
from models.search import SearchEngine, SearchOptions, SearchResult


@pytest.fixture
def engine():
    return SearchEngine()


class TestSearchFindAll:
    def test_find_all_literal(self, engine):
        text = "apple banana Apple apple"
        results = engine.find_all(text, "apple")
        assert len(results) == 3
        assert [r.start for r in results] == [0, 13, 19]

    def test_find_all_case_sensitive(self, engine):
        text = "apple banana Apple apple"
        options = SearchOptions(case_sensitive=True)
        results = engine.find_all(text, "apple", options)
        assert len(results) == 2
        assert [r.start for r in results] == [0, 19]

    def test_find_all_whole_word(self, engine):
        text = "cat category concatenate cat"
        options = SearchOptions(whole_word=True)
        results = engine.find_all(text, "cat", options)
        assert len(results) == 2
        assert [r.start for r in results] == [0, 25]

    def test_find_all_regex(self, engine):
        text = "order-101 and order-202 and invoice-303"
        options = SearchOptions(regex=True)
        results = engine.find_all(text, r"order-\d+", options)
        assert len(results) == 2
        assert results[0].match_text == "order-101"
        assert results[1].match_text == "order-202"

    def test_find_empty_query_and_invalid_regex(self, engine):
        assert engine.find_all("sample text", "") == []
        options = SearchOptions(regex=True)
        assert engine.find_all("sample text", "[unclosed", options) == []

    def test_find_zero_length_matches_skipped(self, engine):
        options = SearchOptions(regex=True)
        results = engine.find_all("abc", r"^|", options)
        for r in results:
            assert r.start < r.end


class TestNavigation:
    def test_find_next_and_previous_wraparound(self, engine):
        text = "one two one three one"
        m1 = engine.find_next(text, "one", from_pos=0)
        assert m1.start == 0

        m2 = engine.find_next(text, "one", from_pos=1)
        assert m2.start == 8

        m3 = engine.find_next(text, "one", from_pos=9)
        assert m3.start == 18

        m4 = engine.find_next(text, "one", from_pos=19)
        assert m4.start == 0

        prev1 = engine.find_previous(text, "one", from_pos=0)
        assert prev1.start == 18


class TestReplace:
    def test_replace_one_command(self, engine):
        buf = PieceTable("Hello world")
        match = SearchResult(start=6, end=11, match_text="world")
        cmd = engine.replace_one(buf, match, "Antigravity")

        assert buf.get_text() == "Hello world"
        cmd.execute()
        assert buf.get_text() == "Hello Antigravity"
        cmd.undo()
        assert buf.get_text() == "Hello world"

    def test_replace_all_back_to_front_order(self, engine):
        text = "cat cat cat"
        buf = PieceTable(text)
        cmd = engine.replace_all(buf, text, "cat", "elephant")
        assert cmd is not None

        positions = [sub_cmd.pos for sub_cmd in cmd.commands]
        assert positions == [8, 4, 0]

        cmd.execute()
        assert buf.get_text() == "elephant elephant elephant"

        cmd.undo()
        assert buf.get_text() == "cat cat cat"

    def test_replace_with_regex_backreferences(self, engine):
        text = "first: 10, second: 20"
        buf = PieceTable(text)
        options = SearchOptions(regex=True)
        cmd = engine.replace_all(buf, text, r"(\w+):\s*(\d+)", r"\1=\2", options)
        assert cmd is not None
        cmd.execute()
        assert buf.get_text() == "first=10, second=20"
