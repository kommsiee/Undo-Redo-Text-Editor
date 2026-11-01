import inspect
import sys
import time
import traceback
from typing import Callable, List, Tuple

import tests.test_buffer as tb
import tests.test_commands as tc
import tests.test_document as td
import tests.test_search as ts
import tests.test_undo_tree as tu
import tests.test_properties as tp
from models.buffer import StringBuffer, GapBuffer, PieceTable, Rope, PieceTable
from models.document import Document
from models.search import SearchEngine

BUFFER_CLASSES = [StringBuffer, GapBuffer, PieceTable, Rope]


def run_buffer_tests() -> Tuple[int, int, List[str]]:
    passed = 0
    failed = 0
    errors = []

    test_classes = [tb.TestBasicOperations, tb.TestEdgeCasesAndErrors, tb.TestStressAndConsistency]
    for cls in test_classes:
        instance = cls()
        methods = [m for m in dir(instance) if m.startswith("test_")]
        for m_name in methods:
            method = getattr(instance, m_name)
            sig = inspect.signature(method)
            for b_cls in BUFFER_CLASSES:
                try:
                    kwargs = {}
                    if "buf" in sig.parameters:
                        kwargs["buf"] = b_cls()
                    if "buf_hello" in sig.parameters:
                        kwargs["buf_hello"] = b_cls("Hello World")
                    if "buffer_cls" in sig.parameters:
                        kwargs["buffer_cls"] = b_cls

                    method(**kwargs)
                    passed += 1
                except Exception as e:
                    failed += 1
                    errors.append(f"{cls.__name__}.{m_name} [{b_cls.__name__}]: {e}\n{traceback.format_exc()}")

    return passed, failed, errors


def run_class_tests(test_cls, fixture_factory=None) -> Tuple[int, int, List[str]]:
    passed = 0
    failed = 0
    errors = []
    instance = test_cls()
    methods = [m for m in dir(instance) if m.startswith("test_")]

    for m_name in methods:
        method = getattr(instance, m_name)
        sig = inspect.signature(method)
        try:
            kwargs = {}
            if fixture_factory:
                for param in sig.parameters:
                    if param in fixture_factory:
                        kwargs[param] = fixture_factory[param]()
            if "b_cls" in sig.parameters:
                for b_cls in BUFFER_CLASSES:
                    method(b_cls)
                    passed += 1
                continue

            method(**kwargs)
            passed += 1
        except Exception as e:
            failed += 1
            errors.append(f"{test_cls.__name__}.{m_name}: {e}\n{traceback.format_exc()}")

    return passed, failed, errors


def run_standalone_functions(module) -> Tuple[int, int, List[str]]:
    passed = 0
    failed = 0
    errors = []
    funcs = [getattr(module, name) for name in dir(module) if name.startswith("test_") and callable(getattr(module, name))]

    for f in funcs:
        sig = inspect.signature(f)
        try:
            if "b_cls" in sig.parameters:
                for b_cls in BUFFER_CLASSES:
                    f(b_cls)
                    passed += 1
            else:
                f()
                passed += 1
        except Exception as e:
            failed += 1
            errors.append(f"{f.__name__}: {e}\n{traceback.format_exc()}")

    return passed, failed, errors


def main() -> None:
    print("=" * 70)
    print(" RUNNING FULL TEXT EDITOR TEST SUITE")
    print("=" * 70)
    t0 = time.time()

    total_passed = 0
    total_failed = 0
    all_errors = []

    p, f, errs = run_buffer_tests()
    total_passed += p
    total_failed += f
    all_errors.extend(errs)
    print(f"[{'PASS' if f == 0 else 'FAIL'}] tests/test_buffer.py: {p} passed, {f} failed")

    p1, f1, e1 = run_class_tests(tc.TestInsertCommand, {"buffer": lambda: PieceTable("Initial Text")})
    p2, f2, e2 = run_class_tests(tc.TestDeleteCommand, {"buffer": lambda: PieceTable("Initial Text")})
    p3, f3, e3 = run_class_tests(tc.TestReplaceCommand, {"buffer": lambda: PieceTable("Initial Text")})
    p4, f4, e4 = run_class_tests(tc.TestCompoundCommand, {"buffer": lambda: PieceTable("Initial Text")})
    cmd_p = p1 + p2 + p3 + p4
    cmd_f = f1 + f2 + f3 + f4
    total_passed += cmd_p
    total_failed += cmd_f
    all_errors.extend(e1 + e2 + e3 + e4)
    print(f"[{'PASS' if cmd_f == 0 else 'FAIL'}] tests/test_commands.py: {cmd_p} passed, {cmd_f} failed")

    p_doc, f_doc, e_doc = run_class_tests(td.TestDocumentUndoRedo, {"doc": lambda: Document(buffer_type=PieceTable, max_history=10)})
    total_passed += p_doc
    total_failed += f_doc
    all_errors.extend(e_doc)
    print(f"[{'PASS' if f_doc == 0 else 'FAIL'}] tests/test_document.py: {p_doc} passed, {f_doc} failed")

    p_s1, f_s1, e_s1 = run_class_tests(ts.TestSearchFindAll, {"engine": lambda: SearchEngine()})
    p_s2, f_s2, e_s2 = run_class_tests(ts.TestNavigation, {"engine": lambda: SearchEngine()})
    p_s3, f_s3, e_s3 = run_class_tests(ts.TestReplace, {"engine": lambda: SearchEngine()})
    s_p = p_s1 + p_s2 + p_s3
    s_f = f_s1 + f_s2 + f_s3
    total_passed += s_p
    total_failed += s_f
    all_errors.extend(e_s1 + e_s2 + e_s3)
    print(f"[{'PASS' if s_f == 0 else 'FAIL'}] tests/test_search.py: {s_p} passed, {s_f} failed")

    p_u, f_u, e_u = run_standalone_functions(tu)
    total_passed += p_u
    total_failed += f_u
    all_errors.extend(e_u)
    print(f"[{'PASS' if f_u == 0 else 'FAIL'}] tests/test_undo_tree.py: {p_u} passed, {f_u} failed")

    p_pr, f_pr, e_pr = run_standalone_functions(tp)
    total_passed += p_pr
    total_failed += f_pr
    all_errors.extend(e_pr)
    print(f"[{'PASS' if f_pr == 0 else 'FAIL'}] tests/test_properties.py: {p_pr} passed, {f_pr} failed")

    dt = time.time() - t0
    print("-" * 70)
    print(f"TOTAL: {total_passed} passed, {total_failed} failed in {dt:.3f}s")
    print("=" * 70)

    if all_errors:
        print("\nERRORS:")
        for err in all_errors:
            print("-" * 40)
            print(err)
        sys.exit(1)
    else:
        print("\nALL TESTS PASSED SUCCESSFULLY! ✓")


if __name__ == "__main__":
    main()
