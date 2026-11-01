from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional, Type


class TextBuffer(ABC):
    """Abstract base class for text buffer implementations."""

    @abstractmethod
    def insert(self, pos: int, text: str) -> None:
        pass

    @abstractmethod
    def delete(self, pos: int, length: int) -> str:
        pass

    @abstractmethod
    def get_text(self) -> str:
        pass

    @abstractmethod
    def get_range(self, start: int, end: int) -> str:
        pass

    @abstractmethod
    def __len__(self) -> int:
        pass

    def set_text(self, text: str) -> None:
        if len(self) > 0:
            self.delete(0, len(self))
        if text:
            self.insert(0, text)


class StringBuffer(TextBuffer):
    """Reference buffer using contiguous Python string."""

    def __init__(self, text: str = "") -> None:
        self._text: str = text

    def insert(self, pos: int, text: str) -> None:
        if not (0 <= pos <= len(self._text)):
            raise ValueError(f"Insert position {pos} out of bounds")
        if not text:
            return
        self._text = self._text[:pos] + text + self._text[pos:]

    def delete(self, pos: int, length: int) -> str:
        if length < 0 or not (0 <= pos <= len(self._text)) or pos + length > len(self._text):
            raise ValueError("Delete range out of bounds")
        if length == 0:
            return ""
        deleted = self._text[pos : pos + length]
        self._text = self._text[:pos] + self._text[pos + length :]
        return deleted

    def get_text(self) -> str:
        return self._text

    def get_range(self, start: int, end: int) -> str:
        if not (0 <= start <= end <= len(self._text)):
            raise ValueError(f"Range [{start}, {end}) out of bounds")
        return self._text[start:end]

    def __len__(self) -> int:
        return len(self._text)


_GAP_MIN = 64


class GapBuffer(TextBuffer):
    """Gap buffer backed by character list with movable edit cursor."""

    def __init__(self, text: str = "") -> None:
        gap_size = max(_GAP_MIN, len(text))
        self._buf: list[str] = list(text) + [""] * gap_size
        self._gap_start: int = len(text)
        self._gap_end: int = len(text) + gap_size

    @property
    def _gap_size(self) -> int:
        return self._gap_end - self._gap_start

    @property
    def _text_length(self) -> int:
        return len(self._buf) - self._gap_size

    def _move_gap(self, pos: int) -> None:
        if pos == self._gap_start:
            return
        if pos < self._gap_start:
            count = self._gap_start - pos
            self._buf[self._gap_end - count : self._gap_end] = self._buf[pos : pos + count]
            self._gap_start = pos
            self._gap_end -= count
        else:
            count = pos - self._gap_start
            self._buf[self._gap_start : self._gap_start + count] = (
                self._buf[self._gap_end : self._gap_end + count]
            )
            self._gap_start += count
            self._gap_end += count

    def _expand_gap(self, needed: int) -> None:
        if self._gap_size >= needed:
            return
        grow = max(_GAP_MIN, needed, self._gap_size * 2)
        filler = [""] * grow
        self._buf = self._buf[: self._gap_end] + filler + self._buf[self._gap_end :]
        self._gap_end += grow

    def insert(self, pos: int, text: str) -> None:
        text_len = self._text_length
        if not (0 <= pos <= text_len):
            raise ValueError(f"Insert position {pos} out of bounds")
        if not text:
            return
        self._move_gap(pos)
        self._expand_gap(len(text))
        for ch in text:
            self._buf[self._gap_start] = ch
            self._gap_start += 1

    def delete(self, pos: int, length: int) -> str:
        text_len = self._text_length
        if length < 0 or not (0 <= pos <= text_len) or pos + length > text_len:
            raise ValueError("Delete range out of bounds")
        if length == 0:
            return ""
        self._move_gap(pos)
        deleted = "".join(self._buf[self._gap_end : self._gap_end + length])
        self._gap_end += length
        return deleted

    def get_text(self) -> str:
        return "".join(self._buf[: self._gap_start]) + "".join(self._buf[self._gap_end :])

    def get_range(self, start: int, end: int) -> str:
        text_len = self._text_length
        if not (0 <= start <= end <= text_len):
            raise ValueError(f"Range [{start}, {end}) out of bounds")
        result: list[str] = []
        for i in range(start, end):
            if i < self._gap_start:
                result.append(self._buf[i])
            else:
                result.append(self._buf[i + self._gap_size])
        return "".join(result)

    def __len__(self) -> int:
        return self._text_length


@dataclass
class Piece:
    source: str
    start: int
    length: int


class PieceTable(TextBuffer):
    """Piece table with immutable original and append-only add buffer."""

    def __init__(self, text: str = "") -> None:
        self._original: str = text
        self._add: str = ""
        self._pieces: list[Piece] = []
        if text:
            self._pieces.append(Piece(source="original", start=0, length=len(text)))

    def _source_text(self, piece: Piece) -> str:
        buf = self._original if piece.source == "original" else self._add
        return buf[piece.start : piece.start + piece.length]

    def _find_piece(self, pos: int) -> tuple[int, int]:
        offset = 0
        for idx, piece in enumerate(self._pieces):
            if offset + piece.length > pos:
                return idx, pos - offset
            offset += piece.length
        return len(self._pieces), 0

    def insert(self, pos: int, text: str) -> None:
        total = len(self)
        if not (0 <= pos <= total):
            raise ValueError(f"Insert position {pos} out of bounds")
        if not text:
            return

        new_piece = Piece(source="add", start=len(self._add), length=len(text))
        self._add += text

        if not self._pieces:
            self._pieces.append(new_piece)
            return

        pi, offset = self._find_piece(pos)

        if pi == len(self._pieces):
            self._pieces.append(new_piece)
        elif offset == 0:
            self._pieces.insert(pi, new_piece)
        else:
            old = self._pieces[pi]
            left = Piece(source=old.source, start=old.start, length=offset)
            right = Piece(
                source=old.source,
                start=old.start + offset,
                length=old.length - offset,
            )
            self._pieces[pi : pi + 1] = [left, new_piece, right]

    def delete(self, pos: int, length: int) -> str:
        total = len(self)
        if length < 0 or not (0 <= pos <= total) or pos + length > total:
            raise ValueError("Delete range out of bounds")
        if length == 0:
            return ""

        deleted = self.get_range(pos, pos + length)
        start_pi, start_off = self._find_piece(pos)
        end_pi, end_off = self._find_piece(pos + length)

        new_pieces: list[Piece] = []

        if start_off > 0:
            old = self._pieces[start_pi]
            new_pieces.append(Piece(source=old.source, start=old.start, length=start_off))

        if end_pi < len(self._pieces) and end_off > 0:
            old = self._pieces[end_pi]
            remaining = old.length - end_off
            if remaining > 0:
                new_pieces.append(
                    Piece(
                        source=old.source,
                        start=old.start + end_off,
                        length=remaining,
                    )
                )
            replace_end = end_pi + 1
        else:
            replace_end = end_pi

        self._pieces[start_pi:replace_end] = new_pieces
        return deleted

    def get_text(self) -> str:
        return "".join(self._source_text(p) for p in self._pieces)

    def get_range(self, start: int, end: int) -> str:
        total = len(self)
        if not (0 <= start <= end <= total):
            raise ValueError(f"Range [{start}, {end}) out of bounds")
        if start == end:
            return ""
        parts: list[str] = []
        offset = 0
        for piece in self._pieces:
            piece_end = offset + piece.length
            if piece_end <= start:
                offset = piece_end
                continue
            if offset >= end:
                break
            lo = max(start, offset) - offset
            hi = min(end, piece_end) - offset
            buf = self._original if piece.source == "original" else self._add
            parts.append(buf[piece.start + lo : piece.start + hi])
            offset = piece_end
        return "".join(parts)

    def __len__(self) -> int:
        return sum(p.length for p in self._pieces)


_ROPE_LEAF_MAX = 1024


@dataclass
class _RopeNode:
    text: Optional[str] = None
    left: Optional["_RopeNode"] = None
    right: Optional["_RopeNode"] = None
    weight: int = 0

    @property
    def is_leaf(self) -> bool:
        return self.left is None and self.right is None


def _rope_length(node: Optional[_RopeNode]) -> int:
    if node is None:
        return 0
    if node.is_leaf:
        return len(node.text) if node.text else 0
    return node.weight + _rope_length(node.right)


def _rope_collect(node: Optional[_RopeNode], parts: list[str]) -> None:
    if node is None:
        return
    if node.is_leaf:
        if node.text:
            parts.append(node.text)
        return
    _rope_collect(node.left, parts)
    _rope_collect(node.right, parts)


def _rope_split(node: Optional[_RopeNode], pos: int) -> tuple[Optional[_RopeNode], Optional[_RopeNode]]:
    if node is None:
        return None, None

    if node.is_leaf:
        txt = node.text or ""
        if pos <= 0:
            return None, node if txt else None
        if pos >= len(txt):
            return node if txt else None, None
        return (
            _RopeNode(text=txt[:pos]),
            _RopeNode(text=txt[pos:]),
        )

    if pos < node.weight:
        left_l, left_r = _rope_split(node.left, pos)
        return left_l, _rope_concat(left_r, node.right)
    elif pos > node.weight:
        right_l, right_r = _rope_split(node.right, pos - node.weight)
        return _rope_concat(node.left, right_l), right_r
    else:
        return node.left, node.right


def _rope_concat(left: Optional[_RopeNode], right: Optional[_RopeNode]) -> Optional[_RopeNode]:
    if left is None:
        return right
    if right is None:
        return left
    return _RopeNode(
        left=left,
        right=right,
        weight=_rope_length(left),
    )


def _rope_height(node: Optional[_RopeNode]) -> int:
    if node is None:
        return 0
    if node.is_leaf:
        return 1
    return 1 + max(_rope_height(node.left), _rope_height(node.right))


def _rope_leaf_count(node: Optional[_RopeNode]) -> int:
    if node is None:
        return 0
    if node.is_leaf:
        return 1
    return _rope_leaf_count(node.left) + _rope_leaf_count(node.right)


def _rope_collect_leaves(node: Optional[_RopeNode], leaves: list[_RopeNode]) -> None:
    if node is None:
        return
    if node.is_leaf:
        if node.text:
            leaves.append(node)
        return
    _rope_collect_leaves(node.left, leaves)
    _rope_collect_leaves(node.right, leaves)


def _rope_build_balanced(leaves: list[_RopeNode]) -> Optional[_RopeNode]:
    if not leaves:
        return None
    if len(leaves) == 1:
        return leaves[0]
    mid = len(leaves) // 2
    left = _rope_build_balanced(leaves[:mid])
    right = _rope_build_balanced(leaves[mid:])
    return _rope_concat(left, right)


def _rope_needs_rebalance(node: Optional[_RopeNode]) -> bool:
    if node is None:
        return False
    lc = _rope_leaf_count(node)
    if lc <= 1:
        return False
    max_height = 1.44 * math.log2(lc) + 2
    return _rope_height(node) > max_height


def _rope_rebalance(node: Optional[_RopeNode]) -> Optional[_RopeNode]:
    if node is None:
        return None
    leaves: list[_RopeNode] = []
    _rope_collect_leaves(node, leaves)
    return _rope_build_balanced(leaves) if leaves else None


def _rope_from_text(text: str) -> Optional[_RopeNode]:
    if not text:
        return None
    if len(text) <= _ROPE_LEAF_MAX:
        return _RopeNode(text=text)
    chunks: list[_RopeNode] = []
    for i in range(0, len(text), _ROPE_LEAF_MAX):
        chunks.append(_RopeNode(text=text[i : i + _ROPE_LEAF_MAX]))
    return _rope_build_balanced(chunks)


class Rope(TextBuffer):
    """Balanced binary tree text buffer with chunked leaf nodes."""

    def __init__(self, text: str = "") -> None:
        self._root: Optional[_RopeNode] = _rope_from_text(text) if text else None
        self._len: int = len(text)

    def insert(self, pos: int, text: str) -> None:
        if not (0 <= pos <= self._len):
            raise ValueError(f"Insert position {pos} out of bounds")
        if not text:
            return

        new_node = _rope_from_text(text)
        if self._root is None:
            self._root = new_node
        else:
            left, right = _rope_split(self._root, pos)
            self._root = _rope_concat(_rope_concat(left, new_node), right)

        self._len += len(text)
        if _rope_needs_rebalance(self._root):
            self._root = _rope_rebalance(self._root)

    def delete(self, pos: int, length: int) -> str:
        if length < 0 or not (0 <= pos <= self._len) or pos + length > self._len:
            raise ValueError("Delete range out of bounds")
        if length == 0:
            return ""

        deleted = self.get_range(pos, pos + length)
        left, rest = _rope_split(self._root, pos)
        _, right = _rope_split(rest, length)
        self._root = _rope_concat(left, right)
        self._len -= length

        if _rope_needs_rebalance(self._root):
            self._root = _rope_rebalance(self._root)

        return deleted

    def get_text(self) -> str:
        if self._root is None:
            return ""
        parts: list[str] = []
        _rope_collect(self._root, parts)
        return "".join(parts)

    def get_range(self, start: int, end: int) -> str:
        if not (0 <= start <= end <= self._len):
            raise ValueError(f"Range [{start}, {end}) out of bounds")
        if start == end:
            return ""
        _, rest = _rope_split(self._root, start)
        mid, _ = _rope_split(rest, end - start)
        if mid is None:
            return ""
        parts: list[str] = []
        _rope_collect(mid, parts)
        return "".join(parts)

    def __len__(self) -> int:
        return self._len


BUFFER_TYPES: Dict[str, Type[TextBuffer]] = {
    "string": StringBuffer,
    "gap": GapBuffer,
    "piece_table": PieceTable,
    "rope": Rope,
}

BUFFER_CLASSES = [StringBuffer, GapBuffer, PieceTable, Rope]
