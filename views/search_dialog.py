from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Optional, Callable
from models.search import SearchOptions


class SearchDialog(tk.Toplevel):
    def __init__(self, parent: tk.Widget, mode: str = "find") -> None:
        super().__init__(parent)
        self.title("Find" if mode == "find" else "Find & Replace")
        self.resizable(True, False)
        self.geometry("450x230" if mode == "replace" else "450x170")
        self.transient(parent.winfo_toplevel())

        self.mode = mode
        self._find_next_cb: Optional[Callable] = None
        self._find_prev_cb: Optional[Callable] = None
        self._replace_one_cb: Optional[Callable] = None
        self._replace_all_cb: Optional[Callable] = None
        self._query_changed_cb: Optional[Callable] = None
        self._close_cb: Optional[Callable] = None

        self._create_widgets()
        self._setup_bindings()
        self.find_entry.focus_set()

    def _create_widgets(self) -> None:
        container = ttk.Frame(self, padding=10)
        container.pack(fill="both", expand=True)

        grid_frame = ttk.Frame(container)
        grid_frame.pack(fill="x", pady=4)

        ttk.Label(grid_frame, text="Find:").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self.query_var = tk.StringVar()
        self.query_var.trace_add("write", self._on_query_var_changed)
        self.find_entry = ttk.Entry(grid_frame, textvariable=self.query_var, width=30)
        self.find_entry.grid(row=0, column=1, sticky="ew", padx=4, pady=4)

        if self.mode == "replace":
            ttk.Label(grid_frame, text="Replace:").grid(row=1, column=0, sticky="w", padx=4, pady=4)
            self.replace_var = tk.StringVar()
            self.replace_entry = ttk.Entry(grid_frame, textvariable=self.replace_var, width=30)
            self.replace_entry.grid(row=1, column=1, sticky="ew", padx=4, pady=4)

        grid_frame.columnconfigure(1, weight=1)

        opts_frame = ttk.Frame(container)
        opts_frame.pack(fill="x", pady=4)

        self.case_var = tk.BooleanVar(value=False)
        self.regex_var = tk.BooleanVar(value=False)
        self.word_var = tk.BooleanVar(value=False)

        self.case_cb = ttk.Checkbutton(opts_frame, text="Match Case", variable=self.case_var, command=self._trigger_query_change)
        self.case_cb.pack(side="left", padx=4)

        self.regex_cb = ttk.Checkbutton(opts_frame, text="Regex", variable=self.regex_var, command=self._trigger_query_change)
        self.regex_cb.pack(side="left", padx=4)

        self.word_cb = ttk.Checkbutton(opts_frame, text="Whole Word", variable=self.word_var, command=self._trigger_query_change)
        self.word_cb.pack(side="left", padx=4)

        btn_frame = ttk.Frame(container)
        btn_frame.pack(fill="x", pady=6)

        self.prev_btn = ttk.Button(btn_frame, text="Previous", command=self._handle_find_prev)
        self.prev_btn.pack(side="left", padx=4)

        self.next_btn = ttk.Button(btn_frame, text="Next", command=self._handle_find_next)
        self.next_btn.pack(side="left", padx=4)

        if self.mode == "replace":
            self.replace_btn = ttk.Button(btn_frame, text="Replace", command=self._handle_replace_one)
            self.replace_btn.pack(side="left", padx=4)

            self.replace_all_btn = ttk.Button(btn_frame, text="Replace All", command=self._handle_replace_all)
            self.replace_all_btn.pack(side="left", padx=4)

        self.status_var = tk.StringVar(value="")
        self.status_label = ttk.Label(container, textvariable=self.status_var, foreground="#555555")
        self.status_label.pack(fill="x", pady=2)

    def _setup_bindings(self) -> None:
        self.bind("<Return>", lambda e: self._handle_find_next())
        self.bind("<Shift-Return>", lambda e: self._handle_find_prev())
        self.bind("<Escape>", lambda e: self._handle_close())
        self.protocol("WM_DELETE_WINDOW", self._handle_close)

    def _on_query_var_changed(self, *args) -> None:
        self._trigger_query_change()

    def _trigger_query_change(self) -> None:
        if self._query_changed_cb:
            self._query_changed_cb()

    def _handle_find_next(self) -> None:
        if self._find_next_cb:
            self._find_next_cb()

    def _handle_find_prev(self) -> None:
        if self._find_prev_cb:
            self._find_prev_cb()

    def _handle_replace_one(self) -> None:
        if self._replace_one_cb:
            self._replace_one_cb()

    def _handle_replace_all(self) -> None:
        if self._replace_all_cb:
            self._replace_all_cb()

    def _handle_close(self) -> None:
        if self._close_cb:
            self._close_cb()
        self.destroy()

    def on_find_next(self, callback: Callable) -> None:
        self._find_next_cb = callback

    def on_find_prev(self, callback: Callable) -> None:
        self._find_prev_cb = callback

    def on_replace_one(self, callback: Callable) -> None:
        self._replace_one_cb = callback

    def on_replace_all(self, callback: Callable) -> None:
        self._replace_all_cb = callback

    def on_query_changed(self, callback: Callable) -> None:
        self._query_changed_cb = callback

    def on_close(self, callback: Callable) -> None:
        self._close_cb = callback

    def get_query(self) -> str:
        return self.query_var.get()

    def get_replacement(self) -> str:
        if hasattr(self, "replace_var"):
            return self.replace_var.get()
        return ""

    def get_options(self) -> SearchOptions:
        return SearchOptions(
            case_sensitive=self.case_var.get(),
            regex=self.regex_var.get(),
            whole_word=self.word_var.get(),
        )

    def set_match_info(self, current: int, total: int) -> None:
        if total == 0:
            self.status_var.set("No matches found")
            self.status_label.configure(foreground="red")
        else:
            display_idx = (current + 1) if current >= 0 else 1
            self.status_var.set(f"Match {display_idx} of {total}")
            self.status_label.configure(foreground="#006600")

    def set_no_matches(self) -> None:
        self.status_var.set("No matches found")
        self.status_label.configure(foreground="red")

    def set_error(self, message: str) -> None:
        self.status_var.set(f"Error: {message}")
        self.status_label.configure(foreground="red")

    def clear_status(self) -> None:
        self.status_var.set("")
