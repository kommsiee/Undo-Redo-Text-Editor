from __future__ import annotations

import json
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Dict, List, Type
from models.buffer import StringBuffer, GapBuffer, PieceTable, Rope, TextBuffer, BUFFER_TYPES


def benchmark_seq_insert(cls: Type[TextBuffer], n: int = 5000) -> float:
    buf = cls()
    t0 = time.perf_counter()
    for i in range(n):
        buf.insert(i, "a")
    return time.perf_counter() - t0


def benchmark_prepend(cls: Type[TextBuffer], n: int = 3000) -> float:
    buf = cls()
    t0 = time.perf_counter()
    for _ in range(n):
        buf.insert(0, "x")
    return time.perf_counter() - t0


def benchmark_random_insert(cls: Type[TextBuffer], n: int = 3000) -> float:
    rng = random.Random(42)
    buf = cls()
    buf.insert(0, "A" * 1000)
    t0 = time.perf_counter()
    for _ in range(n):
        pos = rng.randint(0, len(buf))
        buf.insert(pos, "z")
    return time.perf_counter() - t0


def benchmark_seq_delete(cls: Type[TextBuffer], n: int = 3000) -> float:
    buf = cls("x" * (n + 100))
    t0 = time.perf_counter()
    for _ in range(n):
        buf.delete(len(buf) - 1, 1)
    return time.perf_counter() - t0


def benchmark_get_text(cls: Type[TextBuffer], size: int = 50000, iterations: int = 200) -> float:
    buf = cls("Hello World! " * (size // 13))
    t0 = time.perf_counter()
    for _ in range(iterations):
        _ = buf.get_text()
    return time.perf_counter() - t0


def benchmark_get_range(cls: Type[TextBuffer], size: int = 50000, iterations: int = 1000) -> float:
    rng = random.Random(42)
    buf = cls("ABCDEFGHIJ" * (size // 10))
    total_len = len(buf)
    t0 = time.perf_counter()
    for _ in range(iterations):
        start = rng.randint(0, total_len - 50)
        _ = buf.get_range(start, start + 40)
    return time.perf_counter() - t0


def run_all_benchmarks() -> Dict[str, Dict[str, float]]:
    benchmarks = [
        ("Seq Insert (5k)", benchmark_seq_insert),
        ("Prepend (3k)", benchmark_prepend),
        ("Random Insert (3k)", benchmark_random_insert),
        ("Seq Delete (3k)", benchmark_seq_delete),
        ("Get Text (200x)", benchmark_get_text),
        ("Get Range (1k)", benchmark_get_range),
    ]

    results: Dict[str, Dict[str, float]] = {}

    print("\n" + "=" * 78)
    print(" BUFFER BENCHMARK SUITE: Baseline vs GapBuffer vs PieceTable vs Rope")
    print("=" * 78)

    header = f"{'Benchmark':<24} | {'StringBuffer':<11} | {'GapBuffer':<11} | {'PieceTable':<11} | {'Rope':<11}"
    print(header)
    print("-" * 78)

    for bench_name, bench_fn in benchmarks:
        results[bench_name] = {}
        row_str = f"{bench_name:<24} | "
        for b_name in ["string", "gap", "piece_table", "rope"]:
            cls = BUFFER_TYPES[b_name]
            times = [bench_fn(cls) for _ in range(3)]
            best_t = min(times)
            results[bench_name][b_name] = round(best_t, 5)
            row_str += f"{best_t * 1000:>8.2f} ms | "
        print(row_str)

    print("=" * 78 + "\n")

    out_dir = os.path.dirname(__file__)
    out_path = os.path.join(out_dir, "results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"Results saved to {out_path}\n")

    return results


if __name__ == "__main__":
    run_all_benchmarks()
